from django.contrib.auth import get_user_model
from django.test import TestCase

from registration.forms import EmailForm, ProfileForm, UserCreationFormWithEmail

User = get_user_model()


class RegistrationFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="ana", email="ana@example.com")
        User.objects.create_user(username="luis", email="luis@example.com")

    def signup_data(self, **changes):
        return {
            "username": "nuevo",
            "email": "nuevo@example.com",
            "password1": "Roca-Verde-5729!",
            "password2": "Roca-Verde-5729!",
        } | changes

    def test_valid_signup_creates_user_with_email_and_hashed_password(self):
        form = UserCreationFormWithEmail(data=self.signup_data())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, "nuevo@example.com")
        self.assertTrue(user.check_password("Roca-Verde-5729!"))
        self.assertIsNotNone(user.profile.pk)

    def test_signup_rejects_duplicate_email_case_insensitively(self):
        for email in ("ana@example.com", "ANA@EXAMPLE.COM"):
            with self.subTest(email=email):
                form = UserCreationFormWithEmail(data=self.signup_data(email=email))
                self.assertFalse(form.is_valid())
                self.assertEqual(
                    form.errors.as_data()["email"][0].code, "duplicate_email"
                )

    def test_signup_requires_valid_email(self):
        for email in ("", "invalido"):
            with self.subTest(email=email):
                form = UserCreationFormWithEmail(data=self.signup_data(email=email))
                self.assertFalse(form.is_valid())
                self.assertIn("email", form.errors)

    def test_signup_rejects_mismatched_passwords(self):
        form = UserCreationFormWithEmail(
            data=self.signup_data(password2="Otra-Clave-5931!")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_email_form_rejects_another_users_email(self):
        form = EmailForm(data={"email": "LUIS@EXAMPLE.COM"}, instance=self.user)

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["email"][0].code, "duplicate_email")

    def test_email_form_accepts_own_email(self):
        for email in ("ana@example.com", "ANA@example.com"):
            with self.subTest(email=email):
                form = EmailForm(data={"email": email}, instance=self.user)
                self.assertTrue(form.is_valid(), form.errors)

    def test_email_form_requires_email(self):
        form = EmailForm(data={"email": ""}, instance=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_profile_form_cannot_edit_email_or_owner(self):
        form = ProfileForm(instance=self.user.profile)

        self.assertEqual(set(form.fields), {"avatar", "bio"})
