from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import get_template
from django.utils.cache import add_never_cache_headers


ERROR_MESSAGES = {
    400: (
        "No pudimos procesar la solicitud",
        "La dirección o los datos enviados no son válidos. "
        "Vuelve a abrir la página y revisa la información antes de enviarla.",
    ),
    403: (
        "No tienes acceso a esta página",
        "Tu cuenta no tiene permiso para realizar esta acción. "
        "Puedes volver al inicio o iniciar sesión con una cuenta autorizada.",
    ),
    404: (
        "No encontramos esta página",
        "El enlace puede haber cambiado o la página ya no está disponible. "
        "Revisa la dirección o vuelve al inicio para continuar.",
    ),
    500: (
        "Algo no salió como esperábamos",
        "No pudimos completar la solicitud por un problema del servidor. "
        "Puedes volver al inicio e intentarlo más tarde. "
        "Si estabas registrando un movimiento, revisa tus gastos antes de repetir "
        "la operación para evitar duplicados.",
    ),
}


def _error_response(
    request: HttpRequest, status: int, *, csrf: bool = False
) -> HttpResponse:
    title, message = ERROR_MESSAGES[status]
    if csrf:
        title = "No pudimos validar el formulario"
        message = (
            "La validación de seguridad del formulario falló. "
            "Vuelve a abrirlo para obtener una validación nueva y comprueba "
            "que las cookies estén habilitadas. Si tu sesión terminó, "
            "inicia sesión de nuevo."
        )
    if request.path_info.startswith("/api/"):
        response = JsonResponse({"error": message}, status=status)
    else:
        # No RequestContext: a database or session failure must not break this page.
        template = get_template("core/errors/error.html")
        response = HttpResponse(
            template.render({"status": status, "title": title, "message": message}),
            status=status,
        )
    add_never_cache_headers(response)
    return response


def bad_request(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(request, 400)


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(request, 403)


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(request, 404)


def server_error(request: HttpRequest) -> HttpResponse:
    return _error_response(request, 500)


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    return _error_response(request, 403, csrf=True)
