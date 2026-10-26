from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from spending.exchange import Conversion, convertir_a_mxn, texto_decimal


class ExchangeTests(SimpleTestCase):
    def setUp(self):
        hoy = patch("spending.exchange.timezone.localdate", return_value=date(2026, 10, 25))
        hoy.start()
        self.addCleanup(hoy.stop)
        self.fecha = date(2026, 10, 25)
        self.peticiones = []

    def convertir(
        self, *, payload=None, status=200, body=None, fallo=None,
        argumentos: dict[str, Any] | None = None,
    ) -> Conversion:
        def transporte(request):
            self.peticiones.append(request)
            if fallo is not None:
                raise fallo
            if body is not None:
                return httpx.Response(status, content=body)
            return httpx.Response(status, json=payload)

        cliente = httpx.Client(transport=httpx.MockTransport(transporte))
        argumentos = dict(argumentos or {})
        with patch("spending.exchange.httpx.Client", return_value=cliente) as crear_cliente:
            conversion = convertir_a_mxn(
                argumentos.pop("monto", "10.00"), argumentos.pop("moneda", "USD"),
                argumentos.pop("fecha", self.fecha), **argumentos,
            )
        if self.peticiones:
            crear_cliente.assert_called_once_with(
                timeout=8.0, follow_redirects=False, trust_env=False,
            )
        return conversion

    def test_reference_rate_uses_only_currency_and_expense_date(self):
        conversion = self.convertir(payload={
            "base": "USD", "quote": "MXN", "date": "2026-10-23", "rate": 18.7388,
        }, argumentos={"moneda": " usd "})
        self.assertEqual(conversion.monto_mxn, Decimal("187.39"))
        self.assertEqual(conversion.tipo_cambio, Decimal("18.7388"))
        self.assertEqual(conversion.fecha_tasa, date(2026, 10, 23))
        self.assertEqual(conversion.fuente, "Frankfurter")
        request = self.peticiones[0]
        self.assertEqual(request.url.host, "api.frankfurter.dev")
        self.assertEqual(request.url.path, "/v2/rate/USD/MXN")
        self.assertEqual(dict(request.url.params), {"date": "2026-10-25"})
        self.assertEqual(request.content, b"")
        self.assertNotIn("authorization", request.headers)
        self.assertNotIn("x-goog-api-key", request.headers)
        self.assertEqual(conversion.datos(), {
            "monto_original": "10", "moneda_original": "USD", "monto_mxn": "187.39",
            "tipo_cambio": "18.7388", "fecha_tasa": "2026-10-23", "fuente": "Frankfurter",
        })

    def test_manual_rate_and_local_currency_never_use_network(self):
        for monto, moneda, tasa, esperado in (
            ("10", "EUR", "20.12345", "201.23"),
            ("1", "USD", "0.005", "0.01"),
            ("0.001", "KWD", "60", "0.06"),
            ("1000000", "VND", "0.00074", "740.00"),
            ("100.10", "MXN", None, "100.10"),
            ("99999999.99", "MXN", None, "99999999.99"),
        ):
            with self.subTest(moneda=moneda, monto=monto):
                conversion = self.convertir(argumentos={
                    "monto": monto, "moneda": moneda, "tipo_cambio": tasa,
                })
                self.assertEqual(conversion.monto_mxn, Decimal(esperado))
                self.assertEqual(conversion.fuente, "MXN" if moneda == "MXN" else "usuario")
        self.assertEqual(self.peticiones, [])

    def test_historical_lookup_never_silently_uses_today(self):
        conversion = self.convertir(
            argumentos={"fecha": date(2025, 1, 15)},
            payload={"base": "USD", "quote": "MXN", "date": "2025-01-15", "rate": 20.0},
        )
        self.assertEqual(dict(self.peticiones[0].url.params), {"date": "2025-01-15"})
        self.assertEqual(conversion.fecha_tasa, date(2025, 1, 15))

    def test_unavailable_unsupported_or_rate_limited_provider_has_actionable_error(self):
        for status in (301, 404, 422, 429, 500, 503):
            with self.subTest(status=status):
                with self.assertLogs("spending.exchange", level="WARNING"), self.assertRaisesMessage(
                    ValidationError, "No se registró el gasto"
                ):
                    self.convertir(status=status, payload={"message": "Unavailable"})
        for error in (httpx.ConnectError("offline"), httpx.ReadTimeout("timeout")):
            with self.subTest(error=type(error).__name__):
                with self.assertLogs("spending.exchange", level="WARNING"), self.assertRaisesMessage(
                    ValidationError, "MXN por 1 unidad de USD"
                ):
                    self.convertir(fallo=error)

    def test_invalid_rate_bodies_and_dates_are_rejected(self):
        valido = {"base": "USD", "quote": "MXN", "date": "2026-10-25", "rate": 18.5}
        for cambios in (
            {"base": "EUR"}, {"quote": "USD"}, {"date": "2026-10-26"},
            {"date": "2026-10-17"}, {"date": "20261025"}, {"date": None},
            {"date": "2026-02-30"}, {"date": 123}, {"rate": 0}, {"rate": -1},
            {"rate": True}, {"rate": None}, {"rate": []}, {"rate": {}},
            {"rate": "NaN"}, {"rate": "Infinity"}, {"rate": "1e100"},
            {"rate": "1e-100"}, {"rate": "0.1234567890123"},
        ):
            with self.subTest(cambios=cambios):
                with self.assertLogs("spending.exchange", level="WARNING"), self.assertRaisesMessage(
                    ValidationError, "No se registró el gasto"
                ):
                    self.convertir(payload={**valido, **cambios})
        for body in (b"not-json", b"[]", b"null", b"{}", b"\xff"):
            with self.subTest(body=body):
                with self.assertLogs("spending.exchange", level="WARNING"), self.assertRaisesMessage(
                    ValidationError, "No se registró el gasto"
                ):
                    self.convertir(body=body)

    def test_invalid_user_inputs_never_consult_rates(self):
        for cambios in (
            {"monto": "0"}, {"monto": "-10"}, {"monto": "NaN"}, {"monto": "no"},
            {"monto": "Infinity"}, {"monto": "1e100000"}, {"monto": "1e-100000"},
            {"monto": 10.5}, {"monto": True}, {"monto": "0.000000001"},
            {"moneda": "$"}, {"moneda": "dólares"}, {"moneda": "USD/MXN"}, {"moneda": ""},
            {"moneda": None}, {"moneda": "../USD"}, {"moneda": "123"},
            {"fecha": date(2026, 10, 26)},
            {"tipo_cambio": "NaN"}, {"tipo_cambio": "Infinity"}, {"tipo_cambio": "0"},
            {"tipo_cambio": "-1"}, {"tipo_cambio": ""}, {"tipo_cambio": "1e100000"},
            {"tipo_cambio": True}, {"tipo_cambio": 18.5}, {"tipo_cambio": "1e-100000"},
        ):
            with self.subTest(cambios=cambios):
                with self.assertRaises(ValidationError):
                    self.convertir(argumentos=cambios)
        self.assertEqual(self.peticiones, [])

    def test_out_of_range_conversions_and_invalid_mxn_are_not_rounded_into_valid_expenses(self):
        for argumentos in (
            {"monto": "0.01", "moneda": "USD", "tipo_cambio": "0.001"},
            {"monto": "10000000", "moneda": "USD", "tipo_cambio": "20"},
            {"monto": "1", "moneda": "MXN", "tipo_cambio": "1"},
            {"monto": "0.001", "moneda": "MXN"},
            {"monto": "100000000", "moneda": "MXN"},
        ):
            with self.subTest(argumentos=argumentos):
                with self.assertRaises(ValidationError):
                    self.convertir(argumentos=argumentos)
        self.assertEqual(self.peticiones, [])

    def test_decimal_display_does_not_drop_integer_zeros_or_use_scientific_notation(self):
        self.assertEqual(texto_decimal(Decimal("100.00")), "100")
        self.assertEqual(texto_decimal(Decimal("0.0010")), "0.001")
        self.assertEqual(texto_decimal(Decimal("1E+2")), "100")

    def test_provider_json_is_parsed_without_float_precision_loss(self):
        conversion = self.convertir(body=(
            b'{"base":"USD","quote":"MXN","date":"2026-10-25","rate":18.123456789012}'
        ))
        self.assertEqual(conversion.tipo_cambio, Decimal("18.123456789012"))
        self.assertEqual(conversion.monto_mxn, Decimal("181.23"))
