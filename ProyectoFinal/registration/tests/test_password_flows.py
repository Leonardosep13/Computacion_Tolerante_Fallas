import re
from urllib.parse import urlsplit

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
)
class PasswordFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Roca-Verde-5729!"
        cls.new_password = "Nube-Azul-8462!"
        cls.user = User.objects.create_user(
            username="ana", email="ana@example.com", password=cls.password
        )

    def reset_url(self, token=None):
        return reverse(
            "password_reset_confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
                "token": token or default_token_generator.make_token(self.user),
            },
        )

    def test_password_change_requires_login(self):
        response = self.client.get(reverse("password_change"))

        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('password_change')}"
        )

    def test_password_change_get_uses_existing_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("password_change"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/password_change_form.html")
        self.assertContains(response, 'name="old_password"')
        self.assertContains(response, 'name="new_password1"')
        self.assertContains(response, 'name="new_password2"')
        self.assertEqual(
            set(response.context["form"].fields),
            {"old_password", "new_password1", "new_password2"},
        )

    def test_password_change_changes_password_and_keeps_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password1": self.new_password,
                "new_password2": self.new_password,
            },
        )

        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
        done = self.client.get(reverse("password_change_done"))
        self.assertEqual(done.status_code, 200)
        self.assertTemplateUsed(done, "registration/password_change_done.html")
        self.assertContains(done, "Contraseña actualizada.")
        self.assertContains(done, f'href="{reverse("profile")}"')

    def test_password_change_rejects_wrong_old_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "incorrecta",
                "new_password1": self.new_password,
                "new_password2": self.new_password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_reset_get(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/password_reset_form.html")
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'type="submit"')
        self.assertEqual(set(response.context["form"].fields), {"email"})

    def test_password_reset_sends_email_and_redirects_to_done(self):
        response = self.client.post(
            reverse("password_reset"), {"email": self.user.email}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("http://testserver/accounts/password/reset/", mail.outbox[0].body)
        self.assertNotIn(self.password, mail.outbox[0].body)
        done = self.client.get(reverse("password_reset_done"))
        self.assertTemplateUsed(done, "registration/password_reset_done.html")
        self.assertContains(done, "Si existe una cuenta con ese correo")

    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "unknown@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_rejects_malformed_email(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "invalido"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_reset_token_allows_new_password_and_login(self):
        token = default_token_generator.make_token(self.user)
        response = self.client.get(self.reset_url(token))

        self.assertEqual(response.status_code, 302)
        confirm_url = response.url
        self.assertIn("set-password", confirm_url)
        confirm = self.client.get(confirm_url)
        self.assertEqual(confirm.status_code, 200)
        self.assertTemplateUsed(confirm, "registration/password_reset_confirm.html")
        self.assertTrue(confirm.context["validlink"])
        self.assertContains(confirm, 'name="new_password1"')
        self.assertContains(confirm, 'name="new_password2"')
        self.assertEqual(
            set(confirm.context["form"].fields), {"new_password1", "new_password2"}
        )

        response = self.client.post(
            confirm_url,
            {"new_password1": self.new_password, "new_password2": self.new_password},
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(default_token_generator.check_token(self.user, token))
        self.assertFalse(self.client.login(username="ana", password=self.password))
        self.assertTrue(self.client.login(username="ana", password=self.new_password))
        self.client.logout()
        response = self.client.post(
            reverse("login"), {"username": "ana", "password": self.new_password}
        )
        self.assertRedirects(response, reverse("profile"))

    def test_link_in_reset_email_opens_confirmation_form(self):
        self.client.post(reverse("password_reset"), {"email": self.user.email})
        match = re.search(r"https?://[^\s]+", mail.outbox[0].body)

        self.assertIsNotNone(match)
        response = self.client.get(urlsplit(match.group()).path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["validlink"])

    def test_invalid_token_renders_error_state(self):
        response = self.client.get(self.reset_url("invalid-token"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/password_reset_confirm.html")
        self.assertFalse(response.context["validlink"])
        self.assertIsNone(response.context["form"])
        self.assertContains(response, "El enlace no es válido.")
        self.assertContains(response, f'href="{reverse("password_reset")}"')
        self.assertNotContains(response, 'name="new_password1"')

    def test_invalid_uid_renders_error_state(self):
        response = self.client.get(
            reverse(
                "password_reset_confirm",
                kwargs={"uidb64": "invalido", "token": "invalid-token"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])

    def test_reset_rejects_mismatched_new_passwords(self):
        response = self.client.get(self.reset_url())
        response = self.client.post(
            response.url,
            {"new_password1": self.new_password, "new_password2": "Otra-Clave-6821!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("new_password2", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_reset_complete_get(self):
        response = self.client.get(reverse("password_reset_complete"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/password_reset_complete.html")
        self.assertContains(response, "Tu contraseña se restableció correctamente.")
        self.assertContains(response, f'href="{reverse("login")}"')
