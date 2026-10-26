from django.contrib.auth import get_user_model
from django.test import TestCase

from registration.models import Profile

User = get_user_model()


class ProfileModelTests(TestCase):
    def test_creating_user_creates_profile(self):
        user = User.objects.create_user(username="ana")

        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(user.profile.user, user)
        self.assertEqual(user.profile.bio, "")
        self.assertFalse(user.profile.avatar)

    def test_profile_contains_only_current_fields(self):
        self.assertEqual(
            {field.name for field in Profile._meta.fields},
            {"id", "user", "avatar", "bio"},
        )

    def test_profile_string_is_username(self):
        user = User.objects.create_user(username="ana")

        self.assertEqual(str(user.profile), "ana")

    def test_saving_user_saves_existing_profile_without_duplicates(self):
        user = User.objects.create_user(username="ana")
        user.profile.bio = "Mi biografia"
        user.save()
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.bio, "Mi biografia")
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_saving_user_without_profile_recreates_it(self):
        user = User.objects.create_user(username="ana")
        Profile.objects.filter(user=user).delete()
        user = User.objects.get(pk=user.pk)
        user.save()

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_deleting_user_deletes_profile(self):
        user = User.objects.create_user(username="ana")
        profile_id = user.profile.pk
        user.delete()

        self.assertFalse(Profile.objects.filter(pk=profile_id).exists())
