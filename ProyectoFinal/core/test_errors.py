from unittest.mock import patch

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import OperationalError
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import get_resolver, path, reverse
from django.utils.functional import SimpleLazyObject

from SpendingAdmin import urls as project_urls


def failing_view(request, status):
    exceptions = {
        400: SuspiciousOperation,
        403: PermissionDenied,
        404: Http404,
        500: RuntimeError,
    }
    raise exceptions[status]("internal-error-detail-do-not-display")


def form_view(request):
    return HttpResponse("Formulario")


urlpatterns = [
    path("_error-test/<int:status>/", failing_view),
    path("api/_error-test/<int:status>/", failing_view),
    path("_error-test/form/", form_view),
    *project_urls.urlpatterns,
]
handler400 = "core.errors.bad_request"
handler403 = "core.errors.permission_denied"
handler404 = "core.errors.page_not_found"
handler500 = "core.errors.server_error"


@override_settings(DEBUG=False, ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"])
class ErrorPageTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_production_urlconf_registers_all_error_handlers(self):
        for status, name in (
            (400, "bad_request"),
            (403, "permission_denied"),
            (404, "page_not_found"),
            (500, "server_error"),
        ):
            with self.subTest(status=status):
                handler = get_resolver("SpendingAdmin.urls").resolve_error_handler(status)
                self.assertEqual(handler.__module__, "core.errors")
                self.assertEqual(handler.__name__, name)

    def test_html_errors_keep_status_and_offer_safe_navigation(self):
        for status in (400, 403, 404, 500):
            with self.subTest(status=status):
                response = self.client.get(f"/_error-test/{status}/")
                self.assertContains(response, f"Error {status}", status_code=status)
                self.assertTemplateUsed(response, "core/errors/error.html")
                self.assertContains(
                    response, f'href="{reverse("home")}"', status_code=status
                )
                self.assertContains(
                    response, f'href="{reverse("login")}"', status_code=status
                )
                for private_content in (
                    "internal-error-detail-do-not-display",
                    "Traceback",
                    'id="chat-widget-toggle"',
                    "<script",
                    "<form",
                ):
                    self.assertNotContains(
                        response, private_content, status_code=status
                    )
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_unknown_url_uses_custom_404_without_redirect(self):
        response = self.client.get("/ruta-que-no-existe/?secret=private-query")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Location", response.headers)
        self.assertContains(response, "No encontramos esta página", status_code=404)
        self.assertNotContains(response, "private-query", status_code=404)

    def test_api_errors_remain_json_with_the_existing_error_contract(self):
        for status in (400, 403, 404, 500):
            with self.subTest(status=status):
                response = self.client.get(f"/api/_error-test/{status}/")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["Content-Type"], "application/json")
                self.assertIsInstance(response.json()["error"], str)
                self.assertNotIn("internal-error", response.json()["error"])
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_unknown_api_url_returns_json_404(self):
        response = self.client.get("/api/no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_server_error_does_not_claim_a_failed_operation_was_rolled_back(self):
        response = self.client.post("/_error-test/500/", {"monto": "10"})
        self.assertContains(
            response, "revisa tus gastos antes de repetir", status_code=500
        )
        self.assertNotContains(response, "http-equiv", status_code=500)

    def test_errors_render_without_auth_session_database_or_context_processors(self):
        from . import errors

        def unavailable():
            raise OperationalError("unavailable-private-database")

        request = RequestFactory().get("/")
        request.user = SimpleLazyObject(unavailable)
        request.session = SimpleLazyObject(unavailable)
        with patch(
            "django.db.backends.utils.CursorWrapper.execute",
            side_effect=OperationalError("unavailable-private-database"),
        ), patch(
            "django.template.context.RequestContext.bind_template",
            side_effect=RuntimeError("unavailable-private-context"),
        ):
            for status, handler in (
                (400, errors.bad_request),
                (403, errors.permission_denied),
                (404, errors.page_not_found),
                (500, errors.server_error),
            ):
                with self.subTest(status=status):
                    args = () if status == 500 else (Exception("private"),)
                    response = handler(request, *args)
                    self.assertEqual(response.status_code, status)
                    self.assertIn(f"Error {status}".encode(), response.content)
                    self.assertNotIn(b"private", response.content)

    def test_invalid_host_keeps_bad_request_response(self):
        response = self.client.get("/", HTTP_HOST="untrusted.invalid")
        self.assertContains(response, "Error 400", status_code=400)
        self.assertNotContains(response, "untrusted.invalid", status_code=400)

    def test_unhandled_exception_is_still_logged(self):
        with self.assertLogs("django.request", level="ERROR") as captured:
            response = self.client.get("/_error-test/500/")
        self.assertEqual(response.status_code, 500)
        self.assertTrue(any(record.exc_info for record in captured.records))

    def test_csrf_failure_offers_recovery_without_leaking_reason(self):
        client = Client(enforce_csrf_checks=True)
        with self.assertLogs("django.security.csrf", level="WARNING"):
            response = client.post("/accounts/login/", {"username": "test"})
        self.assertContains(response, "No pudimos validar el formulario", status_code=403)
        self.assertNotContains(response, "CSRF cookie not set", status_code=403)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_csrf_api_rejection_is_json_and_preserves_403(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/chat/", data='{"mensaje":"hola"}', content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("formulario", response.json()["error"])

    def test_csrf_failure_never_displays_the_internal_reason(self):
        from .errors import csrf_failure

        response = csrf_failure(
            RequestFactory().post("/"), reason="private-origin-token-detail"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"private-origin-token-detail", response.content)

    @override_settings(DEBUG=True)
    def test_csrf_rejection_uses_safe_page_even_in_development(self):
        response = Client(enforce_csrf_checks=True).post("/_error-test/form/")
        self.assertContains(response, "No pudimos validar el formulario", status_code=403)
        self.assertNotContains(response, "CSRF cookie not set", status_code=403)

    def test_existing_validation_responses_are_not_replaced(self):
        response = self.client.post(
            "/api/chat/", data='{"mensaje":"hola"}', content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("sesión", response.json()["error"])
