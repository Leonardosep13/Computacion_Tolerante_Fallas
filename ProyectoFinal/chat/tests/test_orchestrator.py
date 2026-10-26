import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec, patch

import httpx
from asgiref.sync import async_to_sync
from django.test import SimpleTestCase, override_settings
from google.genai import errors, types
from google import genai
from mcp import types as mcp_types
from mcp import ClientSession

from chat import orchestrator
from chat.history import Mensaje, limitar_historial
from spending.categories import CATEGORIAS
from spending.mcp_server import crear_servidor


def respuesta_modelo(*, texto=None, funciones=None):
    partes = []
    if texto is not None:
        partes.append(types.Part.from_text(text=texto))
    for nombre, argumentos in funciones or []:
        partes.append(types.Part(
            function_call=types.FunctionCall(name=nombre, args=argumentos, id=nombre),
            thought_signature=b"firma-que-debe-conservarse",
        ))
    return types.GenerateContentResponse(candidates=[
        types.Candidate(content=types.Content(role="model", parts=partes))
    ])


@override_settings(GEMINI_API_KEY="test-only", GEMINI_MODEL="modelo-prueba")
class OrchestratorTests(SimpleTestCase):
    def setUp(self):
        herramientas = async_to_sync(crear_servidor(17).list_tools)()
        self.session = create_autospec(ClientSession, instance=True)
        self.session.list_tools = AsyncMock(return_value=SimpleNamespace(tools=herramientas))
        self.session.call_tool = AsyncMock(return_value=mcp_types.CallToolResult(
            content=[], structuredContent={"total": "250.00"}
        ))
        self.generar = AsyncMock()
        self.cliente = SimpleNamespace(models=SimpleNamespace(generate_content=self.generar))
        self.llamadas = []

    def ejecutar(self, historial=None, mensaje="Mi resumen"):
        return async_to_sync(orchestrator.ejecutar_conversacion)(
            self.session, self.cliente, historial or [], mensaje, 17, self.llamadas
        )

    def test_schema_hides_owner_resolves_enum_and_does_not_mutate_original(self):
        herramientas = async_to_sync(crear_servidor(17).list_tools)()
        for tool in herramientas:
            original = json.dumps(tool.inputSchema, sort_keys=True)
            limpio = orchestrator.esquema_sin_user(tool.inputSchema)
            self.assertNotIn("user_id", limpio["properties"])
            self.assertNotIn("user_id", limpio.get("required", []))
            self.assertNotIn("$ref", json.dumps(limpio))
            self.assertNotIn("$defs", limpio)
            self.assertEqual(json.dumps(tool.inputSchema, sort_keys=True), original)
        registro = orchestrator.esquema_sin_user(herramientas[0].inputSchema)
        self.assertEqual(set(registro["properties"]["categoria"]["enum"]), set(CATEGORIAS))
        self.assertEqual(registro["properties"]["monto"]["type"], "string")
        self.assertEqual(registro["properties"]["moneda"]["type"], "string")
        self.assertIn("tipo_cambio", registro["properties"])
        self.assertNotIn("moneda", registro["required"])
        self.assertNotIn("tipo_cambio", registro["required"])

    def test_direct_response_rebuilds_text_history_and_injects_local_date(self):
        self.generar.return_value = respuesta_modelo(texto="Hola, ¿en qué te ayudo?")
        with patch("chat.orchestrator.timezone.localdate") as fecha:
            fecha.return_value.isoformat.return_value = "2026-01-15"
            resultado = self.ejecutar([
                {"role": "user", "text": "Hola"}, {"role": "model", "text": "Bienvenido"}
            ])
        self.assertEqual(resultado["respuesta"], "Hola, ¿en qué te ayudo?")
        self.assertEqual(resultado["llamadas"], [])
        assert self.generar.await_args is not None
        kwargs = self.generar.await_args.kwargs
        self.assertIn("2026-01-15", kwargs["config"].system_instruction)
        self.assertIn("Guadalajara", kwargs["config"].system_instruction)
        self.assertEqual(kwargs["model"], "modelo-prueba")
        self.assertTrue(kwargs["config"].automatic_function_calling.disable)
        self.assertEqual([turn.role for turn in kwargs["contents"]], ["user", "model", "user"])
        self.session.call_tool.assert_not_awaited()

    def test_function_call_overwrites_spoofed_owner_and_preserves_signature_and_id(self):
        primera = respuesta_modelo(funciones=[
            ("obtener_resumen_gastos", {"user_id": 99, "categoria": "comida"})
        ])
        self.generar.side_effect = [primera, respuesta_modelo(texto="Gastaste $250.00.")]
        resultado = self.ejecutar()
        self.session.call_tool.assert_awaited_once_with(
            "obtener_resumen_gastos", arguments={"categoria": "comida", "user_id": 17}
        )
        self.assertEqual(resultado["llamadas"][0]["argumentos"], {"categoria": "comida"})
        self.assertEqual(resultado["llamadas"][0]["estado"], "completada")
        assert self.generar.await_args is not None
        assert primera.candidates is not None
        contents = self.generar.await_args.kwargs["contents"]
        self.assertIs(contents[-2], primera.candidates[0].content)
        self.assertEqual(contents[-2].parts[0].thought_signature, b"firma-que-debe-conservarse")
        self.assertEqual(contents[-1].parts[0].function_response.id, "obtener_resumen_gastos")

    def test_multiple_tools_in_one_response_are_all_answered(self):
        self.generar.side_effect = [
            respuesta_modelo(funciones=[
                ("listar_gastos", {}), ("obtener_resumen_gastos", {"categoria": "salud"})
            ]), respuesta_modelo(texto="Resumen listo."),
        ]
        resultado = self.ejecutar()
        self.assertEqual(len(resultado["llamadas"]), 2)
        self.assertEqual(self.session.call_tool.await_count, 2)
        assert self.generar.await_args is not None
        self.assertEqual(len(self.generar.await_args.kwargs["contents"][-1].parts), 2)

    def test_validation_error_goes_back_to_model_instead_of_false_success(self):
        self.session.call_tool.return_value = mcp_types.CallToolResult(
            content=[], structuredContent={"error": "El monto no es válido."}
        )
        self.generar.side_effect = [
            respuesta_modelo(funciones=[("registrar_gasto", {"monto": "-1"})]),
            respuesta_modelo(texto="Necesito un monto positivo."),
        ]
        resultado = self.ejecutar()
        self.assertEqual(resultado["llamadas"][0]["estado"], "error")
        assert self.generar.await_args is not None
        self.assertEqual(
            self.generar.await_args.kwargs["contents"][-1].parts[0].function_response.response,
            {"error": "El monto no es válido."},
        )

    def test_foreign_amount_is_passed_unchanged_to_mcp_and_conversion_returns_to_model(self):
        conversion = {
            "monto_original": "10", "moneda_original": "USD", "monto_mxn": "187.39",
            "tipo_cambio": "18.7388", "fecha_tasa": "2026-10-23", "fuente": "Frankfurter",
        }
        self.session.call_tool.return_value = mcp_types.CallToolResult(
            content=[], structuredContent={
                "monto": "187.39", "moneda": "MXN", "conversion": conversion,
            },
        )
        self.generar.side_effect = [
            respuesta_modelo(funciones=[("registrar_gasto", {
                "monto": "10", "moneda": "USD", "categoria": "comida", "fecha": "2026-10-25",
            })]),
            respuesta_modelo(texto="Registrados 187.39 MXN por 10 USD."),
        ]
        resultado = self.ejecutar(mensaje="Gasté 10 USD en comida hoy")
        self.session.call_tool.assert_awaited_once_with("registrar_gasto", arguments={
            "monto": "10", "moneda": "USD", "categoria": "comida",
            "fecha": "2026-10-25", "user_id": 17,
        })
        self.assertEqual(resultado["llamadas"][0]["estado"], "completada")
        assert self.generar.await_args is not None
        kwargs = self.generar.await_args.kwargs
        self.assertEqual(
            kwargs["contents"][-1].parts[0].function_response.response["conversion"],
            conversion,
        )
        prompt = kwargs["config"].system_instruction
        self.assertIn("monto ORIGINAL", prompt)
        self.assertIn("No la inventes", prompt)
        self.assertIn("requieren preguntar cuál moneda", prompt)
        self.assertIn("MXN por 1 unidad", prompt)

    def test_currency_provider_failure_is_returned_for_clarification_without_fake_registration(self):
        aviso = "No se registró el gasto. Indica el tipo de cambio en MXN por 1 unidad de CAD."
        self.session.call_tool.return_value = mcp_types.CallToolResult(
            content=[], structuredContent={"error": aviso},
        )
        self.generar.side_effect = [
            respuesta_modelo(funciones=[("registrar_gasto", {
                "monto": "10", "moneda": "CAD", "categoria": "comida",
            })]),
            respuesta_modelo(texto="No pude consultar la tasa. ¿Cuántos MXN por 1 CAD uso?"),
        ]
        resultado = self.ejecutar(mensaje="Gasté 10 CAD en comida")
        self.assertEqual(resultado["llamadas"][0]["estado"], "error")
        self.session.call_tool.assert_awaited_once()
        assert self.generar.await_args is not None
        self.assertEqual(
            self.generar.await_args.kwargs["contents"][-1].parts[0].function_response.response,
            {"error": aviso},
        )

    def test_mcp_validation_text_error_can_be_corrected(self):
        self.session.call_tool.return_value = mcp_types.CallToolResult(
            content=[mcp_types.TextContent(type="text", text="Invalid arguments")],
            isError=True,
        )
        self.generar.side_effect = [
            respuesta_modelo(funciones=[("listar_gastos", {"limite": "bad"})]),
            respuesta_modelo(texto="Corrige el límite."),
        ]
        self.assertEqual(self.ejecutar()["llamadas"][0]["estado"], "error")

    def test_unknown_function_is_not_executed(self):
        self.generar.return_value = respuesta_modelo(funciones=[("eliminar_gasto", {"id": 1})])
        with self.assertRaisesMessage(orchestrator.ErrorChat, "no disponible"):
            self.ejecutar()
        self.session.call_tool.assert_not_awaited()

    def test_repeated_function_requests_stop_after_bounded_iterations(self):
        self.generar.return_value = respuesta_modelo(funciones=[("listar_gastos", {})])
        with self.assertRaisesMessage(orchestrator.ErrorChat, "límite de pasos"):
            self.ejecutar()
        self.assertEqual(self.generar.await_count, orchestrator.MAX_ITERACIONES)

    def test_excessive_batch_stops_at_tool_budget(self):
        self.generar.return_value = respuesta_modelo(
            funciones=[("listar_gastos", {})] * 12
        )
        with self.assertRaisesMessage(orchestrator.ErrorChat, "límite de herramientas"):
            self.ejecutar()
        self.assertEqual(self.session.call_tool.await_count, orchestrator.MAX_LLAMADAS)

    def test_empty_or_blocked_responses_are_errors(self):
        for respuesta in (
            types.GenerateContentResponse(), respuesta_modelo(texto="  "),
        ):
            with self.subTest(respuesta=respuesta):
                self.generar.return_value = respuesta
                with self.assertRaises(orchestrator.ErrorChat):
                    self.ejecutar()

    def test_truncated_response_is_not_reported_as_complete(self):
        respuesta = respuesta_modelo(texto="Texto incompleto")
        assert respuesta.candidates is not None
        respuesta.candidates[0].finish_reason = types.FinishReason.MAX_TOKENS
        self.generar.return_value = respuesta
        with self.assertRaisesMessage(orchestrator.ErrorChat, "demasiado larga"):
            self.ejecutar()

    def test_real_google_sdk_serializes_schemas_without_network_or_credentials(self):
        capturadas = []

        def transporte(request):
            self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
            capturadas.append(json.loads(request.content))
            return httpx.Response(200, json={
                "candidates": [{
                    "content": {"role": "model", "parts": [{"text": "Prueba sin red."}]},
                    "finishReason": "STOP",
                }],
            })

        async def comprobar():
            async with genai.Client(
                vertexai=False,
                enterprise=False,
                api_key="dummy-not-a-real-key",
                http_options=types.HttpOptions(async_client_args={
                    "transport": httpx.MockTransport(transporte)
                }),
            ).aio as cliente:
                return await orchestrator.ejecutar_conversacion(
                    self.session, cliente, [], "Hola", 17, []
                )

        self.assertEqual(async_to_sync(comprobar)()["respuesta"], "Prueba sin red.")
        declaraciones = capturadas[0]["tools"][0]["functionDeclarations"]
        self.assertEqual(len(declaraciones), 3)
        self.assertNotIn("user_id", json.dumps(declaraciones))
        self.assertEqual(
            declaraciones[0]["parameters_json_schema"]["required"],
            ["monto", "categoria"],
        )

    def test_google_api_accepts_tool_result_role_and_receives_mcp_data(self):
        peticiones = []

        def transporte(request):
            self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
            datos = json.loads(request.content)
            peticiones.append(datos)
            if len(peticiones) == 1:
                return httpx.Response(200, json={
                    "candidates": [{
                        "content": {"role": "model", "parts": [{
                            "functionCall": {
                                "name": "obtener_resumen_gastos",
                                "args": {
                                    "fecha_inicio": "2026-10-01",
                                    "fecha_fin": "2026-10-25",
                                },
                                "id": "resumen-mes",
                            },
                            "thoughtSignature": "ZmlybWE=",
                        }]},
                        "finishReason": "STOP",
                    }],
                })
            roles = [contenido["role"] for contenido in datos["contents"]]
            if any(role not in {"user", "model"} for role in roles):
                return httpx.Response(400, json={"error": {
                    "code": 400, "status": "INVALID_ARGUMENT",
                    "message": "Content role must be user or model.",
                }})
            self.assertEqual(roles, ["user", "model", "user"])
            llamada = datos["contents"][-2]["parts"][0]
            self.assertEqual(llamada["thoughtSignature"], "ZmlybWE=")
            resultado = datos["contents"][-1]["parts"][0]["functionResponse"]
            self.assertEqual(resultado["id"], "resumen-mes")
            self.assertEqual(resultado["name"], "obtener_resumen_gastos")
            self.assertEqual(resultado["response"], {"total": "250.00"})
            return httpx.Response(200, json={"candidates": [{
                "content": {"role": "model", "parts": [{
                    "text": "Este mes llevas gastados $250.00 MXN."
                }]},
                "finishReason": "STOP",
            }]})

        async def comprobar():
            async with genai.Client(
                vertexai=False, enterprise=False, api_key="dummy-not-a-real-key",
                http_options=types.HttpOptions(async_client_args={
                    "transport": httpx.MockTransport(transporte)
                }),
            ).aio as cliente:
                return await orchestrator.ejecutar_conversacion(
                    self.session, cliente, [], "¿Cuánto llevo gastado este mes?", 17, []
                )

        resultado = async_to_sync(comprobar)()
        self.assertEqual(resultado["respuesta"], "Este mes llevas gastados $250.00 MXN.")
        self.assertEqual(resultado["llamadas"][0]["estado"], "completada")
        self.assertEqual(len(peticiones), 2)
        self.session.call_tool.assert_awaited_once_with(
            "obtener_resumen_gastos",
            arguments={
                "fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-25", "user_id": 17,
            },
        )

    def test_api_errors_are_sanitized(self):
        for codigo, status in ((429, 429), (403, 502)):
            self.generar.side_effect = errors.ClientError(
                codigo, {"error": {"message": "NO-MOSTRAR-CREDENCIAL"}}
            )
            with self.assertLogs("chat.orchestrator", level="WARNING") as logs:
                with self.assertRaises(orchestrator.ErrorChat) as caught:
                    self.ejecutar()
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("NO-MOSTRAR", str(caught.exception))
            self.assertNotIn("NO-MOSTRAR", str(logs.output))

    @override_settings(GEMINI_API_KEY="")
    def test_missing_configuration_does_not_start_mcp(self):
        with patch("chat.orchestrator.stdio_client") as stdio:
            with self.assertRaises(orchestrator.ErrorChat) as caught:
                async_to_sync(orchestrator.responder)([], "Hola", 17)
        self.assertEqual(caught.exception.status, 503)
        stdio.assert_not_called()

    def test_history_is_limited_and_does_not_start_with_model(self):
        historial: list[Mensaje] = [{"role": "user", "text": str(i)} for i in range(30)]
        self.assertEqual(len(limitar_historial(historial)), 20)
        self.assertEqual(limitar_historial([
            {"role": "model", "text": "huérfano"}, {"role": "user", "text": "Hola"}
        ]), [{"role": "user", "text": "Hola"}])

    def test_responder_connects_real_contracts_and_closes_contexts(self):
        @asynccontextmanager
        async def stdio(parametros):
            self.assertIn("--user-id", parametros.args)
            self.assertEqual(parametros.args[-1], "17")
            yield ("read", "write")

        session_cm = AsyncMock()
        self.session.initialize = AsyncMock()
        session_cm.__aenter__.return_value = self.session
        cliente_cm = AsyncMock()
        cliente_cm.__aenter__.return_value = self.cliente
        self.generar.return_value = respuesta_modelo(texto="Todo listo.")
        with patch("chat.orchestrator.stdio_client", stdio), patch(
            "chat.orchestrator.ClientSession", return_value=session_cm
        ), patch("chat.orchestrator.genai.Client") as cliente:
            cliente.return_value.aio = cliente_cm
            resultado = async_to_sync(orchestrator.responder)([], "Hola", 17)
        cliente.assert_called_once_with(
            vertexai=False,
            enterprise=False,
            api_key="test-only",
            http_options=types.HttpOptions(timeout=30000),
        )
        self.assertEqual(resultado["respuesta"], "Todo listo.")
        session_cm.__aexit__.assert_awaited_once()
        cliente_cm.__aexit__.assert_awaited_once()

    def test_transport_exception_group_becomes_explicit_chat_error(self):
        with patch(
            "chat.orchestrator.stdio_client",
            side_effect=ExceptionGroup("transport", [OSError("detalle privado")]),
        ):
            with self.assertLogs("chat.orchestrator", level="WARNING"):
                with self.assertRaisesMessage(orchestrator.ErrorChat, "herramientas"):
                    async_to_sync(orchestrator.responder)([], "Hola", 17)

    def test_timeout_is_explicit_and_not_success_shaped(self):
        with patch("chat.orchestrator.stdio_client", side_effect=TimeoutError):
            with self.assertLogs("chat.orchestrator", level="WARNING"):
                with self.assertRaises(orchestrator.ErrorChat) as error:
                    async_to_sync(orchestrator.responder)([], "Hola", 17)
        self.assertEqual(error.exception.status, 504)
