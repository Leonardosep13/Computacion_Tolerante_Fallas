from collections.abc import Sequence
import json

from mcp.types import CallToolResult, ContentBlock, TextContent


def datos_bloques(resultado: Sequence[ContentBlock] | dict) -> dict:
    if isinstance(resultado, dict):
        return resultado
    bloque = resultado[0]
    assert isinstance(bloque, TextContent)
    datos = json.loads(bloque.text)
    assert isinstance(datos, dict)
    return datos


def datos_resultado(resultado: CallToolResult) -> dict:
    if resultado.structuredContent is not None:
        return resultado.structuredContent
    return datos_bloques(resultado.content)
