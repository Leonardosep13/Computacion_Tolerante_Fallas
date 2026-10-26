from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from registration.models import Profile

User = get_user_model()


class ProfileViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="ana", email="ana@example.com")
        cls.other_user = User.objects.create_user(
            username="luis", email="luis@example.com"
        )

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def image_upload(self, filename="avatar.png"):
        image = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image, format="PNG")
        return SimpleUploadedFile(filename, image.getvalue(), content_type="image/png")

    def upload_avatar(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"), {"avatar": self.image_upload(), "bio": ""}
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.profile.refresh_from_db()
        return self.user.profile.avatar

    def test_profile_requires_login(self):
        for method in (self.client.get, self.client.post):
            response = method(reverse("profile"))
            self.assertRedirects(
                response, f"{reverse('login')}?next={reverse('profile')}"
            )

    def test_profile_get_uses_own_profile_without_avatar(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/profile_form.html")
        self.assertEqual(response.context["object"].user_id, self.user.pk)
        self.assertFalse(response.context["object"].avatar)
        self.assertNotIn("email", response.context["form"].fields)
        self.assertEqual(response.context["request"].user.email, self.user.email)
        self.assertContains(response, 'aria-label="Sin avatar"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'id="profile-email"')
        self.assertContains(response, f'value="{self.user.email}" readonly')
        self.assertContains(response, f'href="{reverse("profile_email")}"')
        self.assertContains(response, f'href="{reverse("password_change")}"')
        self.assertNotContains(response, 'name="link"')

    def test_profile_updates_bio_but_not_email_or_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"),
            {
                "bio": "Finanzas personales",
                "email": "cambio@example.com",
                "user": self.other_user.pk,
                "pk": self.other_user.profile.pk,
            },
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Finanzas personales")
        self.assertEqual(self.user.email, "ana@example.com")
        self.other_user.profile.refresh_from_db()
        self.assertEqual(self.other_user.profile.bio, "")

    def test_profile_recovers_missing_profile_for_existing_user(self):
        self.client.force_login(self.user)
        Profile.objects.filter(user=self.user).delete()
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_avatar_upload_is_saved(self):
        avatar = self.upload_avatar()

        self.assertTrue(avatar.name.startswith("profiles/"))
        self.assertTrue(avatar.storage.exists(avatar.name))
        response = self.client.get(reverse("profile"))
        self.assertContains(response, f'src="{avatar.url}"')
        self.assertContains(response, 'name="avatar-clear"')
        self.assertNotContains(response, 'aria-label="Sin avatar"')

    def test_profile_save_shows_success_message(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"), {"bio": "Nueva biografia"}, follow=True
        )

        self.assertContains(response, "Tu perfil se actualizó correctamente.")

    def test_avatar_clear_removes_field_and_file(self):
        avatar = self.upload_avatar()
        previous_name = avatar.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("profile"), {"avatar-clear": "on", "bio": ""}
            )

        self.assertRedirects(response, reverse("profile"))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)
        self.assertFalse(avatar.storage.exists(previous_name))

    def test_avatar_replacement_removes_previous_file(self):
        avatar = self.upload_avatar()
        previous_name = avatar.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("profile"),
                {"avatar": self.image_upload(), "bio": ""},
            )

        self.assertRedirects(response, reverse("profile"))
        self.user.profile.refresh_from_db()
        self.assertNotEqual(self.user.profile.avatar.name, previous_name)
        self.assertTrue(
            self.user.profile.avatar.storage.exists(self.user.profile.avatar.name)
        )
        self.assertFalse(avatar.storage.exists(previous_name))

    def test_invalid_image_is_rejected_without_losing_previous_avatar(self):
        avatar = self.upload_avatar()
        response = self.client.post(
            reverse("profile"),
            {
                "avatar": SimpleUploadedFile(
                    "invalid.png", b"not an image", content_type="image/png"
                ),
                "bio": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("avatar", response.context["form"].errors)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar.name, avatar.name)
        self.assertTrue(avatar.storage.exists(avatar.name))

    def test_upload_and_clear_together_do_not_remove_existing_avatar(self):
        avatar = self.upload_avatar()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("profile"),
                {
                    "avatar-clear": "on",
                    "avatar": self.image_upload(),
                    "bio": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("avatar", response.context["form"].errors)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar.name, avatar.name)
        self.assertTrue(avatar.storage.exists(avatar.name))

    def test_profile_email_requires_login(self):
        for method in (self.client.get, self.client.post):
            response = method(reverse("profile_email"))
            self.assertRedirects(
                response, f"{reverse('login')}?next={reverse('profile_email')}"
            )

    def test_profile_email_get_uses_current_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile_email"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/profile_email_form.html")
        self.assertEqual(response.context["form"].instance.pk, self.user.pk)

    def test_profile_email_updates_only_current_user_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_email"),
            {"email": "nuevo@example.com", "pk": self.other_user.pk},
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.other_user.refresh_from_db()
        self.assertEqual(self.user.email, "nuevo@example.com")
        self.assertEqual(self.other_user.email, "luis@example.com")

    def test_profile_email_rejects_duplicate(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_email"), {"email": self.other_user.email.upper()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@example.com")
