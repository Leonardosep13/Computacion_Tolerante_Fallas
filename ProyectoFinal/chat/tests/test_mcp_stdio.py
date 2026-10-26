import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import SimpleTestCase
import httpx
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from chat.orchestrator import ejecutar_conversacion

from .helpers import datos_resultado


class MCPStdioIntegrationTests(SimpleTestCase):
    def test_real_stdio_protocol_registration_summary_and_owner_isolation(self):
        with TemporaryDirectory(prefix="spending-mcp-test-") as directorio:
            entorno = {
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "chat.tests.mcp_settings",
                "SPENDING_MCP_TEST_DB": str(Path(directorio) / "test.sqlite3"),
            }
            base = [sys.executable, str(settings.BASE_DIR / "manage.py")]
            subprocess.run(
                [*base, "migrate", "--noinput"], env=entorno, cwd=settings.BASE_DIR,
                capture_output=True, check=True, timeout=30,
            )
            subprocess.run(
                [*base, "shell", "-c",
                 "from django.contrib.auth import get_user_model; "
                 "U=get_user_model(); U.objects.create_user(pk=8101, username='mcp-test'); "
                 "U.objects.create_user(pk=8102, username='mcp-other')"],
                env=entorno, cwd=settings.BASE_DIR, capture_output=True, check=True, timeout=15,
            )

            async def comprobar():
                parametros = StdioServerParameters(
                    command=sys.executable,
                    args=[str(settings.BASE_DIR / "manage.py"), "run_mcp", "--user-id", "8101"],
                    env=entorno, cwd=str(settings.BASE_DIR),
                )
                async with asyncio.timeout(20):
                    async with stdio_client(parametros) as (read, write):
                        async with ClientSession(read, write) as cliente:
                            await cliente.initialize()
                            herramientas = await cliente.list_tools()
                            self.assertEqual(
                                {t.name for t in herramientas.tools},
                                {"registrar_gasto", "obtener_resumen_gastos", "listar_gastos"},
                            )
                            resultado = await cliente.call_tool("registrar_gasto", {
                                "user_id": 8101, "monto": "0.10", "categoria": "comida",
                                "fecha": "2026-01-15", "descripcion": "Demo aislada",
                            })
                            self.assertFalse(resultado.isError)
                            self.assertEqual(datos_resultado(resultado)["monto"], "0.10")
                            resumen = await cliente.call_tool(
                                "obtener_resumen_gastos", {"user_id": 8101}
                            )
                            self.assertEqual(datos_resultado(resumen)["total"], "0.10")
                            ajeno = await cliente.call_tool("listar_gastos", {"user_id": 8102})
                            self.assertIn("error", datos_resultado(ajeno))
                            invalido = await cliente.call_tool("registrar_gasto", {
                                "user_id": 8101, "monto": "no", "categoria": "comida",
                            })
                            self.assertIn("error", datos_resultado(invalido))
                            ultimos = await cliente.call_tool("listar_gastos", {"user_id": 8101})
                            self.assertEqual(len(datos_resultado(ultimos)["gastos"]), 1)

                            peticiones = []

                            def transporte(request):
                                peticion = json.loads(request.content)
                                peticiones.append(peticion)
                                if len(peticiones) == 1:
                                    parte = {"functionCall": {
                                        "name": "obtener_resumen_gastos",
                                        "args": {
                                            "fecha_inicio": "2026-01-01",
                                            "fecha_fin": "2026-01-31",
                                        },
                                        "id": "resumen-stdio",
                                    }}
                                else:
                                    self.assertEqual(
                                        [turno["role"] for turno in peticion["contents"]],
                                        ["user", "model", "user"],
                                    )
                                    respuesta_tool = peticion["contents"][-1]["parts"][0][
                                        "functionResponse"
                                    ]
                                    self.assertEqual(respuesta_tool["id"], "resumen-stdio")
                                    self.assertEqual(respuesta_tool["response"]["total"], "0.10")
                                    self.assertEqual(respuesta_tool["response"]["cantidad"], 1)
                                    self.assertEqual(
                                        respuesta_tool["response"]["por_categoria"][0]["total"],
                                        "0.10",
                                    )
                                    parte = {"text": "Llevas $0.10 MXN en enero."}
                                return httpx.Response(200, json={"candidates": [{
                                    "content": {"role": "model", "parts": [parte]},
                                    "finishReason": "STOP",
                                }]})

                            async with genai.Client(
                                vertexai=False, enterprise=False,
                                api_key="dummy-not-a-real-key",
                                http_options=types.HttpOptions(async_client_args={
                                    "transport": httpx.MockTransport(transporte)
                                }),
                            ).aio as gemini:
                                respuesta = await ejecutar_conversacion(
                                    cliente, gemini, [], "¿Cuánto llevo gastado en enero?",
                                    8101, [],
                                )
                            self.assertEqual(respuesta["respuesta"], "Llevas $0.10 MXN en enero.")
                            self.assertEqual(respuesta["llamadas"][0]["estado"], "completada")
                            self.assertEqual(len(peticiones), 2)

            async_to_sync(comprobar)()
