import asyncio
import os

import django
from django.conf import settings
from django.contrib.auth import get_user_model

from .history import MAX_MENSAJE, limitar_historial
from .orchestrator import ErrorChat, configurado, responder


def mostrar_llamadas(llamadas):
    for llamada in llamadas:
        print(f"🔧 {llamada['nombre']}({llamada['argumentos']}) — {llamada['estado']}")


async def conversar(usuario_id):
    historial = []
    print("Chat de gastos. /salir para terminar; /limpiar borra el historial, no los gastos.")
    print("Tus mensajes y los resultados de las consultas se enviarán a Google Gemini.")
    print("Para convertir monedas, Frankfurter recibe solo el par de monedas y la fecha.")
    while True:
        try:
            mensaje = (await asyncio.to_thread(input, "Tú: ")).strip()
        except EOFError:
            return
        if mensaje == "/salir":
            return
        if mensaje == "/limpiar":
            historial = []
            print("Historial borrado.")
            continue
        if not mensaje or len(mensaje) > MAX_MENSAJE:
            print(f"Escribe entre 1 y {MAX_MENSAJE} caracteres.")
            continue
        try:
            resultado = await responder(historial, mensaje, usuario_id)
        except ErrorChat as error:
            mostrar_llamadas(error.llamadas)
            print(f"Error: {error}")
            if error.llamadas:
                print("Algunas operaciones pudieron aplicarse. Revisa Gastos antes de repetirlas.")
            continue
        mostrar_llamadas(resultado["llamadas"])
        print(f"Asistente: {resultado['respuesta']}")
        historial = limitar_historial([
            *historial, {"role": "user", "text": mensaje},
            {"role": "model", "text": resultado["respuesta"]},
        ])


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SpendingAdmin.settings")
    django.setup()
    if not configurado():
        raise SystemExit("Configura GEMINI_API_KEY y GEMINI_MODEL en .env.")
    usuario_id = settings.USER_ID
    if usuario_id is None:
        try:
            usuario_id = int(input("ID del usuario local para la demo: "))
        except (ValueError, EOFError):
            raise SystemExit("Se requiere un ID entero positivo.") from None
    if usuario_id < 1 or not get_user_model().objects.filter(
        pk=usuario_id, is_active=True
    ).exists():
        raise SystemExit("No existe ese usuario activo.")
    try:
        asyncio.run(conversar(usuario_id))
    except KeyboardInterrupt:
        print("\nChat terminado.")


if __name__ == "__main__":
    main()