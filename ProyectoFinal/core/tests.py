from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LayoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="layout-user")

    def setUp(self):
        self.client.force_login(self.user)

    def test_application_pages_require_login(self):
        self.client.logout()
        for name in ("home", "chat", "gastos"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response, f"{reverse('login')}?next={reverse(name)}"
                )

    def test_opening_app_shows_login_for_anonymous_user(self):
        self.client.logout()
        response = self.client.get(reverse("home"), follow=True)

        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="next" value="/"')
        self.assertContains(response, f'href="{reverse("signup")}"')

    def test_shared_layout_on_every_page(self):
        for name, title in (("home", "Inicio"), ("chat", "Chat"), ("gastos", "Gastos")):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "core/base.html")
                self.assertContains(response, f"<title>{title} | SpendingAdmin</title>", html=True)
                self.assertContains(response, '<header class="app-header">')
                self.assertContains(response, '<footer class="app-footer">')
                self.assertContains(response, 'id="sidebar"')
                self.assertContains(response, 'aria-controls="sidebar"')
                self.assertContains(response, f'href="{reverse(name)}" title="{title}" aria-current="page"')
                self.assertContains(response, 'aria-current="page"', count=1)
                for destination in ("home", "chat", "gastos"):
                    self.assertContains(response, f'href="{reverse(destination)}"')
                self.assertContains(response, f'href="{reverse("profile")}"')
                self.assertContains(response, f'action="{reverse("logout")}" method="post"')

    def test_chat_is_no_longer_a_placeholder(self):
        response = self.client.get(reverse("chat"))
        self.assertTemplateUsed(response, "chat/chat.html")
        self.assertNotContains(response, "PRÓXIMAMENTE")

    def test_floating_chat_is_shared_on_application_and_account_pages(self):
        for name in ("home", "chat", "gastos", "profile", "profile_email",
                     "password_change", "password_change_done"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "chat/widget.html")
                self.assertContains(response, 'id="chat-widget-toggle"', count=1)
                self.assertContains(response, 'aria-controls="chat-widget-window"')
                self.assertContains(response, f'data-panel-url="{reverse("chat_panel")}"')
                self.assertContains(response, 'id="chat-widget-window" role="dialog"')
                self.assertContains(response, "chat/js/chat.js", count=1)
                self.assertContains(response, "chat/js/widget.js", count=1)
                self.assertNotContains(response, 'id="chat-widget-app"')

    def test_public_account_pages_do_not_offer_private_chat(self):
        self.client.logout()
        for name in ("login", "signup", "password_reset", "password_reset_complete"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, 'id="chat-widget-toggle"')
                self.assertNotContains(response, "chat/js/widget.js")

    def test_static_assets_are_discoverable(self):
        from django.contrib.staticfiles import finders

        for asset in ("css/variables.css", "core/css/layout.css", "core/js/layout.js"):
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))


class AdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.user = users.objects.create_user(username="regular-user")
        cls.staff = users.objects.create_user(username="staff-user", is_staff=True)
        cls.admin = users.objects.create_superuser(
            username="admin-user", email="admin@example.com", password="Admin-Secret-219!"
        )

    def test_sidebar_offers_admin_only_to_staff(self):
        for user in (self.user, self.staff, self.admin):
            with self.subTest(username=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("home"))
                if user.is_staff:
                    self.assertContains(response, f'href="{reverse("admin:index")}"')
                else:
                    self.assertNotContains(response, f'href="{reverse("admin:index")}"')
        self.client.logout()
        self.assertNotContains(
            self.client.get(reverse("login")), f'href="{reverse("admin:index")}"'
        )

    def test_anonymous_and_regular_users_cannot_enter_admin(self):
        for user in (None, self.user):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                response = self.client.get(reverse("admin:index"))
                self.assertRedirects(
                    response,
                    f'{reverse("admin:login")}?next={reverse("admin:index")}',
                )

    def test_staff_can_open_the_native_admin_but_has_no_implicit_model_permissions(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/index.html")
        self.assertNotContains(
            response, f'href="{reverse("admin:spending_gasto_changelist")}"'
        )
        self.assertEqual(
            self.client.get(reverse("admin:spending_gasto_changelist")).status_code, 403
        )

    def test_superuser_can_open_registered_models(self):
        self.client.force_login(self.admin)
        for name in (
            "admin:index", "admin:spending_gasto_changelist",
            "admin:registration_profile_changelist", "admin:auth_user_changelist",
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
