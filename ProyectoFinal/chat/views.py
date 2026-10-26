import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .history import MAX_MENSAJE, SESSION_KEY, limitar_historial
from .orchestrator import ErrorChat, configurado, responder


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class ChatView(LoginRequiredMixin, TemplateView):
    template_name = "chat/chat.html"
    extra_context = {"title": "Chat"}
    chat_prefix = "chat"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chat_configurado"] = configurado()
        context["historial"] = self.request.session.get(SESSION_KEY, [])
        context["max_mensaje"] = MAX_MENSAJE
        context["chat_prefix"] = self.chat_prefix
        return context


class ChatPanelView(ChatView):
    template_name = "chat/panel.html"
    chat_prefix = "chat-widget"


@require_POST
async def chat_api(request):
    usuario = await request.auser()
    if not usuario.is_authenticated:
        return JsonResponse({"error": "Tu sesión terminó. Inicia sesión de nuevo."}, status=401)
    if request.content_type != "application/json":
        return JsonResponse({"error": "Envía el mensaje como JSON."}, status=415)
    if len(request.body) > 16000:
        return JsonResponse({"error": "El mensaje es demasiado largo."}, status=400)
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "El JSON no es válido."}, status=400)
    mensaje = datos.get("mensaje") if isinstance(datos, dict) else None
    if not isinstance(mensaje, str) or not mensaje.strip():
        return JsonResponse({"error": "Escribe un mensaje antes de enviarlo."}, status=400)
    mensaje = mensaje.strip()
    if len(mensaje) > MAX_MENSAJE:
        return JsonResponse({
            "error": f"El mensaje no puede superar {MAX_MENSAJE} caracteres."
        }, status=400)
    historial = await request.session.aget(SESSION_KEY, [])
    try:
        resultado = await responder(historial, mensaje, usuario.pk)
    except ErrorChat as error:
        aviso = str(error)
        if error.llamadas:
            aviso += " Algunas operaciones pudieron aplicarse; revisa Gastos antes de repetirlas."
        return JsonResponse(
            {"error": aviso, "llamadas": error.llamadas}, status=error.status
        )
    await request.session.aset(SESSION_KEY, limitar_historial([
        *historial,
        {"role": "user", "text": mensaje},
        {"role": "model", "text": resultado["respuesta"]},
    ]))
    return JsonResponse(resultado)


@require_POST
async def limpiar_chat(request):
    usuario = await request.auser()
    if not usuario.is_authenticated:
        return JsonResponse({"error": "Tu sesión terminó. Inicia sesión de nuevo."}, status=401)
    await request.session.aset(SESSION_KEY, [])
    return JsonResponse({"historial": []})