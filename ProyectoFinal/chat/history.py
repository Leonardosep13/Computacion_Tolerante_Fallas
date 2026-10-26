from typing import Literal, TypedDict

MAX_MENSAJES = 20
MAX_MENSAJE = 2000
SESSION_KEY = "chat_historial"


class Mensaje(TypedDict):
    role: Literal["user", "model"]
    text: str


def limitar_historial(historial: list[Mensaje]) -> list[Mensaje]:
    historial = historial[-MAX_MENSAJES:]
    if historial and historial[0]["role"] == "model":
        historial = historial[1:]
    return historial
