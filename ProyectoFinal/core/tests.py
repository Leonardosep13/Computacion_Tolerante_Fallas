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
