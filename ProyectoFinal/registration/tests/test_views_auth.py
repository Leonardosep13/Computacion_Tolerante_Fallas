from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class AuthViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Roca-Verde-5729!"
        cls.user = User.objects.create_user(
            username="ana", email="ana@example.com", password=cls.password
        )

    def test_signup_get(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signup.html")
        self.assertTemplateUsed(response, "core/base.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(
            set(response.context["form"].fields),
            {"username", "email", "password1", "password2"},
        )

    def test_signup_post_creates_user_and_redirects_to_login_with_register(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "nuevo",
                "email": "nuevo@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(response, f"{reverse('login')}?register")
        user = User.objects.get(username="nuevo")
        self.assertTrue(user.check_password(self.password))
        self.assertIsNotNone(user.profile.pk)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_invalid_signup_does_not_create_user(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "nuevo",
                "email": self.user.email.upper(),
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    def test_anonymous_login_get(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertEqual(set(response.context["form"].fields), {"username", "password"})

    def test_registration_flag_is_available_to_login_template(self):
        response = self.client.get(f"{reverse('login')}?register")

        self.assertIn("register", response.context["request"].GET)
        self.assertContains(response, "Tu cuenta se creó correctamente.")

    def test_authenticated_login_redirects_to_profile_even_with_next(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("login"), {"next": reverse("home")})

        self.assertRedirects(response, reverse("profile"))

    def test_login_with_invalid_credentials_has_non_field_error(self):
        response = self.client.post(
            reverse("login"), {"username": "ana", "password": "incorrecta"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(
            response, str(response.context["form"].non_field_errors()[0])
        )
        self.assertEqual(
            response.context["form"].non_field_errors().as_data()[0].code,
            "invalid_login",
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_successful_login_redirects_to_profile(self):
        response = self.client.post(
            reverse("login"), {"username": "ana", "password": self.password}
        )

        self.assertRedirects(response, reverse("profile"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_login_honors_safe_next_and_rejects_external_redirects(self):
        for next_url, expected in (
            (reverse("home"), reverse("home")),
            ("https://example.org/", reverse("profile")),
        ):
            with self.subTest(next_url=next_url):
                self.client.logout()
                response = self.client.post(
                    reverse("login"),
                    {"username": "ana", "password": self.password, "next": next_url},
                )
                self.assertRedirects(response, expected)

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(
            response, reverse("home"), fetch_redirect_response=False
        )
        login = self.client.get(reverse("home"), follow=True)
        self.assertTemplateUsed(login, "registration/login.html")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_public_account_pages_have_forms_and_no_private_navigation(self):
        for name, fields in (
            ("login", ("username", "password")),
            ("signup", ("username", "email", "password1", "password2")),
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, '<header class="app-header">')
                self.assertContains(response, '<footer class="app-footer">')
                self.assertContains(response, 'registration/css/account.css')
                self.assertNotContains(response, 'id="sidebar"')
                self.assertNotContains(response, 'aria-controls="sidebar"')
                for field in fields:
                    self.assertContains(response, f'name="{field}"')
                    self.assertContains(response, f'for="id_{field}"')
                self.assertContains(response, 'type="submit"')

    def test_login_has_signup_and_password_reset_links(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, f'href="{reverse("signup")}"')
        self.assertContains(response, f'href="{reverse("password_reset")}"')

    def test_login_form_preserves_next_and_returns_to_requested_page(self):
        response = self.client.get(reverse("chat"), follow=True)
        self.assertContains(
            response, f'name="next" value="{reverse("chat")}"'
        )
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
                "next": reverse("chat"),
            },
        )

        self.assertRedirects(response, reverse("chat"))

    def test_signup_renders_duplicate_email_error_without_losing_username(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "nuevo",
                "email": self.user.email,
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertContains(response, "El email ya está registrado")
        self.assertContains(response, 'value="nuevo"')
        self.assertContains(response, 'id="id_email_error"')
        self.assertNotContains(response, f'value="{self.password}"')

    def test_login_and_logout_enforce_csrf_with_real_forms(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("login"))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        credentials = {"username": self.user.username, "password": self.password}
        self.assertEqual(client.post(reverse("login"), credentials).status_code, 403)

        response = client.post(
            reverse("login"),
            credentials | {"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertRedirects(response, reverse("profile"))
        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        response = client.post(
            reverse("logout"),
            {"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, client.session)
