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
