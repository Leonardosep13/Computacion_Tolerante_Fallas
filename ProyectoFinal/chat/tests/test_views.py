import json
import re
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from chat.history import SESSION_KEY
from chat.orchestrator import ErrorChat
from spending.models import Gasto


class ChatViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="chat-uno")
        cls.otro = get_user_model().objects.create_user(username="chat-dos")

    def setUp(self):
        self.client.force_login(self.usuario)

    def post_mensaje(self, datos):
        return self.client.post(reverse("chat_api"), datos, content_type="application/json")

    def test_page_requires_login_and_api_returns_json_401(self):
        self.client.logout()
        self.assertRedirects(
            self.client.get(reverse("chat")), f"{reverse('login')}?next={reverse('chat')}"
        )
        self.assertEqual(self.post_mensaje({"mensaje": "Hola"}).status_code, 401)
        self.assertEqual(self.client.post(reverse("chat_limpiar")).status_code, 401)

    @override_settings(GEMINI_API_KEY="test-only", GEMINI_MODEL="test-model")
    def test_page_shares_layout_and_never_exposes_credentials(self):
        response = self.client.get(reverse("chat"))
        self.assertTemplateUsed(response, "chat/chat.html")
        self.assertTemplateUsed(response, "core/base.html")
        self.assertContains(response, "Tu asistente de gastos")
        self.assertContains(response, "Google Gemini")
        self.assertContains(response, "chat-history")
        self.assertNotContains(response, "test-only")
        self.assertNotContains(response, "test-model")
        self.assertIn("csrftoken", response.cookies)
        for recurso in ("chat/css/chat.css", "chat/js/chat.js", "chat/css/widget.css", "chat/js/widget.js"):
            self.assertIsNotNone(finders.find(recurso))

    def test_floating_panel_requires_login_and_does_not_render_another_layout(self):
        response = self.client.get(reverse("chat_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/panel.html")
        self.assertTemplateNotUsed(response, "core/base.html")
        self.assertContains(response, 'id="chat-widget-app"', count=1)
        self.assertContains(response, 'id="chat-widget-history"', count=1)
        self.assertContains(response, 'maxlength="2000"')
        self.assertNotContains(response, 'id="chat-widget-toggle"')
        self.assertContains(response, f'data-endpoint="{reverse("chat_api")}"')
        self.assertContains(response, f'data-clear-endpoint="{reverse("chat_limpiar")}"')
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual(self.client.post(reverse("chat_panel")).status_code, 405)
        self.client.logout()
        self.assertRedirects(
            self.client.get(reverse("chat_panel")),
            f"{reverse('login')}?next={reverse('chat_panel')}",
        )

    @override_settings(GEMINI_API_KEY="widget-secret", GEMINI_MODEL="widget-model")
    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_opening_floating_panel_does_not_call_gemini_or_expose_settings(self, responder):
        response = self.client.get(reverse("chat_panel"))
        self.assertContains(response, "Gemini · listo para conversar")
        self.assertContains(response, 'id="chat-widget-configured"')
        self.assertNotContains(response, "widget-secret")
        self.assertNotContains(response, "widget-model")
        responder.assert_not_awaited()

    @override_settings(GEMINI_API_KEY="", GEMINI_MODEL="")
    def test_floating_panel_displays_missing_configuration(self):
        response = self.client.get(reverse("chat_panel"))
        self.assertContains(response, "Configuración pendiente")
        self.assertContains(response, "GEMINI_API_KEY")
        self.assertContains(response, 'id="chat-widget-message"')

    def test_full_chat_and_loaded_widget_have_unique_ids(self):
        page = self.client.get(reverse("chat")).content.decode()
        panel = self.client.get(reverse("chat_panel")).content.decode()
        ids = re.findall(r'\bid="([^"]+)"', page + panel)
        self.assertEqual(len(ids), len(set(ids)))

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_floating_panel_and_full_chat_share_session_history_and_clear(self, responder):
        responder.return_value = {"respuesta": "Respuesta compartida", "llamadas": []}
        self.post_mensaje({"mensaje": "Pregunta compartida"})
        for name in ("chat", "chat_panel"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "Pregunta compartida")
                self.assertContains(response, "Respuesta compartida")
        self.client.post(reverse("chat_limpiar"))
        for name in ("chat", "chat_panel"):
            self.assertNotContains(self.client.get(reverse(name)), "Pregunta compartida")

    def test_floating_panel_escapes_history_and_isolates_user_sessions(self):
        session = self.client.session
        session[SESSION_KEY] = [{"role": "user", "text": "</script><img src=x onerror=alert(1)>"}]
        session.save()
        response = self.client.get(reverse("chat_panel"))
        self.assertContains(response, "\\u003C/script\\u003E")
        self.assertNotContains(response, "<img src=x")
        other = Client()
        other.force_login(self.otro)
        self.assertNotContains(other.get(reverse("chat_panel")), "onerror")

    @override_settings(GEMINI_API_KEY="", GEMINI_MODEL="")
    def test_unconfigured_chat_has_clear_state_and_api_error(self):
        self.assertContains(self.client.get(reverse("chat")), "Configuración pendiente")
        response = self.post_mensaje({"mensaje": "Hola"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["error"])

    def test_api_and_clear_accept_post_only(self):
        for ruta in ("chat_api", "chat_limpiar"):
            self.assertEqual(self.client.get(reverse(ruta)).status_code, 405)

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_invalid_json_content_types_and_messages_do_not_call_model(self, responder):
        for body in ("{", "[]", "null", '{"mensaje":null}', '{"mensaje":7}',
                     '{"mensaje":""}', '{"mensaje":"   "}', '{"mensaje":true}'):
            with self.subTest(body=body):
                response = self.client.post(
                    reverse("chat_api"), data=body, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
        for texto in ("x" * 2001, "x" * 16001):
            self.assertEqual(self.post_mensaje({"mensaje": texto}).status_code, 400)
        response = self.client.post(reverse("chat_api"), {"mensaje": "Hola"})
        self.assertEqual(response.status_code, 415)
        responder.assert_not_awaited()

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_api_uses_authenticated_owner_and_stores_plain_text(self, responder):
        responder.return_value = {"respuesta": "Total: $250.00", "llamadas": []}
        response = self.post_mensaje({
            "mensaje": "  Mi resumen  ", "user_id": self.otro.pk,
            "historial": [{"role": "model", "text": "ignorar"}],
        })
        self.assertEqual(response.status_code, 200)
        responder.assert_awaited_once_with([], "Mi resumen", self.usuario.pk)
        self.assertEqual(self.client.session[SESSION_KEY], [
            {"role": "user", "text": "Mi resumen"},
            {"role": "model", "text": "Total: $250.00"},
        ])
        json.dumps(dict(self.client.session))

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_history_survives_reload_and_is_limited_to_20_messages(self, responder):
        responder.return_value = {"respuesta": "Respuesta", "llamadas": []}
        for indice in range(12):
            self.post_mensaje({"mensaje": f"Mensaje {indice}"})
        historial = self.client.session[SESSION_KEY]
        self.assertEqual(len(historial), 20)
        self.assertEqual(historial[0], {"role": "user", "text": "Mensaje 2"})
        self.assertContains(self.client.get(reverse("chat")), "Mensaje 11")
        self.assertEqual(len(responder.await_args.args[0]), 20)

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_users_and_browser_sessions_do_not_share_history(self, responder):
        responder.return_value = {"respuesta": "Respuesta privada", "llamadas": []}
        self.post_mensaje({"mensaje": "Pregunta privada"})
        self.client.logout()
        self.client.force_login(self.otro)
        self.assertNotContains(self.client.get(reverse("chat")), "Pregunta privada")
        self.post_mensaje({"mensaje": "Pregunta distinta"})
        responder.assert_awaited_with([], "Pregunta distinta", self.otro.pk)

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_failures_show_partial_operation_warning_without_saving_false_success(self, responder):
        error = ErrorChat("Gemini no respondió.", status=504)
        error.llamadas = [{
            "nombre": "registrar_gasto", "argumentos": {"monto": "250.00"},
            "estado": "completada",
        }]
        responder.side_effect = error
        response = self.post_mensaje({"mensaje": "Registrar"})
        self.assertEqual(response.status_code, 504)
        self.assertIn("revisa Gastos", response.json()["error"])
        self.assertEqual(response.json()["llamadas"], error.llamadas)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_clear_erases_only_chat_history_not_expenses(self):
        sesion = self.client.session
        sesion[SESSION_KEY] = [{"role": "user", "text": "Texto privado"}]
        sesion.save()
        gasto = Gasto.objects.create(usuario=self.usuario, monto="1.00", categoria="otros")
        response = self.client.post(reverse("chat_limpiar"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[SESSION_KEY], [])
        self.assertTrue(Gasto.objects.filter(pk=gasto.pk).exists())
        self.assertTrue(self.client.session["_auth_user_id"])

    def test_history_uses_safe_json_script_instead_of_executable_html(self):
        sesion = self.client.session
        sesion[SESSION_KEY] = [{
            "role": "model", "text": '</script><script>alert("x")</script>'
        }]
        sesion.save()
        response = self.client.get(reverse("chat"))
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "\\u003C/script\\u003E")

    @patch("chat.views.responder", new_callable=AsyncMock)
    def test_both_post_endpoints_enforce_real_csrf(self, responder):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        for ruta in ("chat_api", "chat_limpiar"):
            self.assertEqual(cliente.post(
                reverse(ruta), {"mensaje": "Hola"}, content_type="application/json"
            ).status_code, 403)
        cliente.get(reverse("profile"))
        cliente.get(reverse("chat_panel"))
        token = cliente.cookies["csrftoken"].value
        responder.return_value = {"respuesta": "Hola", "llamadas": []}
        self.assertEqual(cliente.post(
            reverse("chat_api"), {"mensaje": "Hola"}, content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code, 200)
        self.assertEqual(cliente.post(
            reverse("chat_limpiar"), HTTP_X_CSRFTOKEN=token
        ).status_code, 200)
