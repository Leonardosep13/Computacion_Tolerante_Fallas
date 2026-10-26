from datetime import date
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from spending import services
from spending.mcp_server import crear_servidor
from spending.models import Gasto

from .helpers import datos_bloques


class SpendingChatServicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="servicios-chat")
        cls.otro = get_user_model().objects.create_user(username="otro-servicios")

    def test_registration_uses_decimal_and_local_date(self):
        with patch("spending.services.timezone.localdate", return_value=date(2026, 1, 15)):
            gasto = services.registrar_gasto(
                self.usuario.pk, monto="250.10", categoria="comida", descripcion="Tacos"
            )
        gasto.refresh_from_db()
        self.assertEqual(gasto.monto, Decimal("250.10"))
        self.assertEqual(gasto.fecha, date(2026, 1, 15))
        self.assertTrue(Gasto.objects.filter(pk=gasto.pk, usuario=self.usuario).exists())

    def test_bad_data_never_creates_expenses(self):
        for cambios in (
            {"monto": "no"}, {"monto": "NaN"}, {"monto": "Infinity"},
            {"monto": "-1"}, {"monto": "0"}, {"monto": "0.001"},
            {"monto": 1.25}, {"monto": "100000000.00"}, {"categoria": "inventada"},
            {"descripcion": "x" * 201}, {"fecha": "2026-02-30"},
            {"fecha": "20260101"}, {"fecha": "hoy"},
        ):
            with self.subTest(cambios=cambios):
                datos = {"monto": "1.00", "categoria": "comida", **cambios}
                with self.assertRaises(ValidationError):
                    services.registrar_gasto(self.usuario.pk, **datos)
        self.assertFalse(Gasto.objects.exists())

    def test_summary_is_exact_filtered_and_owner_scoped(self):
        for monto, categoria in (("0.10", "comida"), ("0.20", "comida"), ("9.00", "salud")):
            services.registrar_gasto(
                self.usuario.pk, monto=monto, categoria=categoria, fecha="2026-01-15"
            )
        services.registrar_gasto(
            self.otro.pk, monto="900.00", categoria="comida", fecha="2026-01-15"
        )
        resumen = services.obtener_resumen_gastos(
            self.usuario.pk, fecha_inicio="2026-01-01", fecha_fin="2026-01-31",
            categoria="comida",
        )
        self.assertEqual(resumen["total"], Decimal("0.30"))
        self.assertEqual(resumen["cantidad"], 2)
        self.assertEqual(resumen["por_categoria"], [{
            "categoria": "comida", "nombre": "Comida",
            "total": Decimal("0.30"), "cantidad": 2,
        }])

    def test_mcp_tools_execute_sync_orm_off_event_loop_and_bind_owner(self):
        servidor = crear_servidor(self.usuario.pk)
        resultado = async_to_sync(servidor.call_tool)("registrar_gasto", {
            "user_id": self.usuario.pk, "monto": "250.00", "categoria": "comida",
            "descripcion": "Desde MCP", "fecha": "2026-01-15",
        })
        datos = datos_bloques(resultado)
        self.assertEqual(datos["monto"], "250.00")
        self.assertEqual(datos["fecha"], "2026-01-15")
        self.assertTrue(Gasto.objects.filter(usuario=self.usuario, descripcion="Desde MCP").exists())
        rechazo = async_to_sync(servidor.call_tool)("registrar_gasto", {
            "user_id": self.otro.pk, "monto": "250.00", "categoria": "comida",
        })
        self.assertIn("error", datos_bloques(rechazo))
        self.assertFalse(Gasto.objects.filter(usuario=self.otro).exists())

    def test_mcp_validation_errors_are_tool_results_and_can_be_retried(self):
        servidor = crear_servidor(self.usuario.pk)
        for nombre, datos in (
            ("registrar_gasto", {"monto": "-1", "categoria": "comida"}),
            ("registrar_gasto", {"monto": "1", "categoria": "inventada"}),
            ("listar_gastos", {"limite": 21}),
            ("obtener_resumen_gastos", {"fecha_inicio": "ayer"}),
        ):
            with self.subTest(nombre=nombre, datos=datos):
                resultado = async_to_sync(servidor.call_tool)(
                    nombre, {"user_id": self.usuario.pk, **datos}
                )
                self.assertIn("error", datos_bloques(resultado))

    @patch("spending.exchange.obtener_tasa", return_value=(Decimal("18.7388"), date(2026, 1, 15)))
    def test_foreign_currency_registration_stores_only_mxn_and_keeps_conversion_reference(self, tasa):
        servidor = crear_servidor(self.usuario.pk)
        resultado = async_to_sync(servidor.call_tool)("registrar_gasto", {
            "user_id": self.usuario.pk, "monto": "10.00", "moneda": "USD",
            "categoria": "comida", "descripcion": "Almuerzo", "fecha": "2026-01-15",
        })
        datos = datos_bloques(resultado)
        self.assertNotIn("error", datos)
        self.assertEqual(datos["moneda"], "MXN")
        self.assertEqual(datos["monto"], "187.39")
        self.assertEqual(datos["conversion"]["tipo_cambio"], "18.7388")
        self.assertEqual(datos["conversion"]["fuente"], "Frankfurter")
        gasto = Gasto.objects.get(usuario=self.usuario)
        self.assertEqual(gasto.monto, Decimal("187.39"))
        self.assertEqual(gasto.fecha, date(2026, 1, 15))
        self.assertIn("10 USD", gasto.descripcion)
        self.assertIn("18.7388 MXN", gasto.descripcion)
        self.assertIn("2026-01-15; Frankfurter", gasto.descripcion)
        resumen = services.obtener_resumen_gastos(self.usuario.pk)
        self.assertEqual(resumen["total"], Decimal("187.39"))
        tasa.assert_called_once_with("USD", date(2026, 1, 15))

    @patch("spending.exchange.obtener_tasa", side_effect=ValidationError("No hay tasa disponible."))
    def test_failed_lookup_saves_nothing_and_user_rate_can_correct_it(self, tasa):
        servidor = crear_servidor(self.usuario.pk)
        argumentos = {
            "user_id": self.usuario.pk, "monto": "10", "moneda": "CAD",
            "categoria": "transporte", "fecha": "2026-01-15",
        }
        error = datos_bloques(async_to_sync(servidor.call_tool)("registrar_gasto", argumentos))
        self.assertIn("error", error)
        self.assertFalse(Gasto.objects.exists())
        exito = datos_bloques(async_to_sync(servidor.call_tool)(
            "registrar_gasto", {**argumentos, "tipo_cambio": "13.25"}
        ))
        self.assertEqual(exito["monto"], "132.50")
        self.assertEqual(exito["conversion"]["fuente"], "usuario")
        self.assertEqual(Gasto.objects.count(), 1)
        self.assertIn("usuario", Gasto.objects.get().descripcion)
        tasa.assert_called_once()

    @patch("spending.exchange.obtener_tasa")
    def test_owner_invalid_data_and_mxn_do_not_contact_exchange_provider(self, tasa):
        servidor = crear_servidor(self.usuario.pk)
        for cambios in (
            {"user_id": self.otro.pk}, {"categoria": "inventada"}, {"monto": "-1"},
            {"descripcion": "x" * 201}, {"fecha": "mañana"}, {"moneda": "$"},
            {"tipo_cambio": "-1"}, {"fecha": "2999-01-01"},
        ):
            with self.subTest(cambios=cambios):
                resultado = async_to_sync(servidor.call_tool)("registrar_gasto", {
                    "user_id": self.usuario.pk, "monto": "10", "moneda": "EUR",
                    "categoria": "comida", **cambios,
                })
                self.assertIn("error", datos_bloques(resultado))
        self.assertFalse(Gasto.objects.exists())
        resultado = async_to_sync(servidor.call_tool)("registrar_gasto", {
            "user_id": self.usuario.pk, "monto": "10.10", "categoria": "comida",
        })
        datos = datos_bloques(resultado)
        self.assertEqual(datos["monto"], "10.10")
        self.assertNotIn("conversion", datos)
        self.assertEqual(Gasto.objects.get().descripcion, "")
        tasa.assert_not_called()

    def test_long_description_is_not_silently_truncated_to_store_conversion(self):
        servidor = crear_servidor(self.usuario.pk)
        resultado = async_to_sync(servidor.call_tool)("registrar_gasto", {
            "user_id": self.usuario.pk, "monto": "10", "moneda": "EUR",
            "tipo_cambio": "20", "categoria": "comida", "descripcion": "x" * 190,
        })
        self.assertIn("Acorta la descripción", datos_bloques(resultado)["error"])
        self.assertFalse(Gasto.objects.exists())
