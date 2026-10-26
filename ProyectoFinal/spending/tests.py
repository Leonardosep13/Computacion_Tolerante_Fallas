from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from html import unescape
from io import StringIO
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .categories import CATEGORIAS
from .forms import GastoFiltroForm
from .management.commands.seed_gastos import DATOS_DEMO
from .models import Gasto
from .services import listar_gastos, resumir_gastos


class GastoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="gastos-uno")
        cls.otro = get_user_model().objects.create_user(username="gastos-dos")

    def crear_gasto(self, **kwargs):
        datos = {
            "usuario": self.usuario,
            "monto": Decimal("125.50"),
            "categoria": "comida",
            "descripcion": "Comida de prueba",
            "fecha": date(2026, 1, 15),
        }
        datos.update(kwargs)
        return Gasto.objects.create(**datos)


class GastoModelTests(GastoTestCase):
    def test_monto_is_decimal_and_str_identifies_expense(self):
        gasto = self.crear_gasto()
        gasto.refresh_from_db()
        self.assertEqual(gasto.monto, Decimal("125.50"))
        self.assertIsInstance(gasto.monto, Decimal)
        self.assertEqual(str(gasto), "Comida · $125.50 · 2026-01-15")

    def test_default_date_uses_guadalajara_local_date(self):
        instante = datetime(2026, 1, 15, 3, tzinfo=datetime_timezone.utc)
        with timezone.override("America/Mexico_City"):
            with patch("django.utils.timezone.now", return_value=instante):
                gasto = Gasto.objects.create(
                    usuario=self.usuario, monto="1.00", categoria="otros"
                )
        self.assertEqual(gasto.fecha, date(2026, 1, 14))

    def test_all_categories_use_shared_labels_and_colors(self):
        for clave, categoria in CATEGORIAS.items():
            with self.subTest(categoria=clave):
                gasto = self.crear_gasto(categoria=clave)
                gasto.full_clean()
                self.assertEqual(gasto.get_categoria_display(), categoria["nombre"])
                self.assertEqual(gasto.categoria_color, categoria["color"])

    def test_model_rejects_invalid_amounts_and_categories(self):
        for cambios in (
            {"monto": Decimal("0.00")},
            {"monto": Decimal("-1.00")},
            {"monto": Decimal("1.001")},
            {"monto": Decimal("100000000.00")},
            {"categoria": "inexistente"},
        ):
            with self.subTest(cambios=cambios):
                gasto = Gasto(
                    usuario=self.usuario, monto="1.00", categoria="otros"
                )
                for campo, valor in cambios.items():
                    setattr(gasto, campo, valor)
                with self.assertRaises(ValidationError):
                    gasto.full_clean()

    def test_database_rejects_nonpositive_amounts(self):
        for monto in ("0.00", "-0.01"):
            with self.subTest(monto=monto):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.crear_gasto(monto=monto)

    def test_deleting_user_deletes_expenses(self):
        gasto = self.crear_gasto()
        self.usuario.delete()
        self.assertFalse(Gasto.objects.filter(pk=gasto.pk).exists())


class GastoFiltroFormTests(TestCase):
    def test_empty_filters_are_valid(self):
        self.assertTrue(GastoFiltroForm({}).is_valid())

    def test_parses_date_range_and_category(self):
        form = GastoFiltroForm({
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-01-31",
            "categoria": "salud",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["fecha_inicio"], date(2026, 1, 1))
        self.assertEqual(form.cleaned_data["categoria"], "salud")

    def test_same_date_is_allowed(self):
        self.assertTrue(GastoFiltroForm({
            "fecha_inicio": "2026-01-15", "fecha_fin": "2026-01-15"
        }).is_valid())

    def test_invalid_filters_are_reported(self):
        for datos, campo in (
            ({"fecha_inicio": "no-es-fecha"}, "fecha_inicio"),
            ({"fecha_fin": "2026-02-30"}, "fecha_fin"),
            ({"categoria": "inventada"}, "categoria"),
            ({"fecha_inicio": "2026-02-01", "fecha_fin": "2026-01-01"}, "__all__"),
        ):
            with self.subTest(datos=datos):
                form = GastoFiltroForm(datos)
                self.assertFalse(form.is_valid())
                self.assertIn(campo, form.errors)


class GastoServiceTests(GastoTestCase):
    def test_every_query_and_summary_is_user_scoped(self):
        propio = self.crear_gasto(monto=Decimal("0.10"))
        self.crear_gasto(monto=Decimal("0.20"))
        self.crear_gasto(usuario=self.otro, monto=Decimal("90000.00"))
        gastos = listar_gastos(self.usuario.pk)
        self.assertIn(propio, gastos)
        self.assertEqual(gastos.count(), 2)
        self.assertEqual(resumir_gastos(gastos), {
            "total": Decimal("0.30"), "cantidad": 2, "promedio": Decimal("0.15")
        })

    def test_filters_are_inclusive_and_combined(self):
        primero = self.crear_gasto(fecha=date(2026, 1, 1))
        ultimo = self.crear_gasto(fecha=date(2026, 1, 31))
        self.crear_gasto(fecha=date(2025, 12, 31))
        self.crear_gasto(fecha=date(2026, 2, 1))
        self.crear_gasto(categoria="salud")
        gastos = listar_gastos(
            self.usuario.pk, fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 31), categoria="comida",
        )
        self.assertEqual(list(gastos), [ultimo, primero])

    def test_each_open_date_bound(self):
        self.crear_gasto(fecha=date(2026, 1, 1))
        self.crear_gasto(fecha=date(2026, 1, 31))
        self.assertEqual(listar_gastos(
            self.usuario.pk, fecha_inicio=date(2026, 1, 15)
        ).count(), 1)
        self.assertEqual(listar_gastos(
            self.usuario.pk, fecha_fin=date(2026, 1, 15)
        ).count(), 1)

    def test_invalid_service_filters_raise_explicit_errors(self):
        for filtros in (
            {"categoria": "inventada"},
            {"fecha_inicio": date(2026, 2, 1), "fecha_fin": date(2026, 1, 1)},
        ):
            with self.subTest(filtros=filtros), self.assertRaises(ValidationError):
                listar_gastos(self.usuario.pk, **filtros)

    def test_empty_summary_uses_decimal_zero(self):
        self.assertEqual(resumir_gastos(listar_gastos(self.usuario.pk)), {
            "total": Decimal("0.00"), "cantidad": 0, "promedio": Decimal("0.00")
        })

    def test_same_date_order_is_deterministic(self):
        primero = self.crear_gasto()
        segundo = self.crear_gasto()
        Gasto.objects.update(creado_en=timezone.now())
        self.assertEqual(list(listar_gastos(self.usuario.pk)), [segundo, primero])


class GastoListViewTests(GastoTestCase):
    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse("gastos")

    def test_login_required(self):
        self.client.logout()
        self.assertRedirects(
            self.client.get(self.url), f"{reverse('login')}?next={self.url}"
        )

    def test_renders_template_layout_and_empty_state_without_seeding(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "spending/gasto_list.html")
        self.assertTemplateUsed(response, "core/base.html")
        self.assertContains(response, "Tu historial empieza aquí")
        self.assertEqual(Gasto.objects.count(), 0)

    def test_cannot_see_other_users_data_or_override_owner(self):
        propio = self.crear_gasto()
        self.crear_gasto(usuario=self.otro, descripcion="GASTO PRIVADO AJENO")
        response = self.client.get(self.url, {"usuario": self.otro.pk})
        self.assertEqual(list(response.context["gastos"]), [propio])
        self.assertEqual(response.context["resumen"]["cantidad"], 1)
        self.assertEqual(response.context["resumen"]["total"], propio.monto)
        self.assertNotContains(response, "GASTO PRIVADO AJENO")

    def test_filters_combined_and_summary_matches_selection(self):
        esperado = self.crear_gasto()
        self.crear_gasto(categoria="salud")
        self.crear_gasto(fecha=date(2025, 12, 1))
        response = self.client.get(self.url, {
            "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
            "categoria": "comida",
        })
        self.assertEqual(list(response.context["gastos"]), [esperado])
        self.assertEqual(response.context["resumen"]["total"], esperado.monto)
        self.assertContains(response, 'value="2026-01-01"')
        self.assertContains(response, '<option value="comida" selected>Comida</option>')

    def test_pagination_preserves_filters_and_totals_across_pages(self):
        for indice in range(23):
            self.crear_gasto(
                monto=Decimal("10.00"), fecha=date(2026, 1, 1) + timedelta(days=indice)
            )
        filtros = {
            "categoria": "comida", "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-01-31",
        }
        response = self.client.get(self.url, filtros)
        self.assertEqual(len(response.context["gastos"]), 10)
        self.assertEqual(response.context["resumen"]["total"], Decimal("230.00"))
        self.assertEqual(response.context["resumen"]["cantidad"], 23)
        self.assertContains(response, "1–10 de 23")
        enlace = re.search(r'href="([^"]+)" rel="next"', response.content.decode())[1]
        parametros = parse_qs(urlsplit(unescape(enlace)).query)
        self.assertEqual(parametros, {**{k: [v] for k, v in filtros.items()}, "page": ["2"]})
        segunda = self.client.get(self.url, {**filtros, "page": 2})
        tercera = self.client.get(self.url, {**filtros, "page": 3})
        self.assertEqual(len(segunda.context["gastos"]), 10)
        self.assertEqual(len(tercera.context["gastos"]), 3)
        self.assertEqual(tercera.context["resumen"]["total"], Decimal("230.00"))
        self.assertTrue(set(response.context["gastos"]).isdisjoint(segunda.context["gastos"]))
        self.assertContains(response, f'action="{self.url}"')
        self.assertNotContains(response, 'name="page"')

    def test_no_results_has_clear_filters_link(self):
        self.crear_gasto()
        response = self.client.get(self.url, {"categoria": "educacion"})
        self.assertContains(response, "No encontramos movimientos")
        self.assertContains(response, "Ver todos los gastos")
        self.assertEqual(response.context["resumen"]["total"], Decimal("0.00"))

    def test_invalid_filters_return_400_with_visible_errors_and_no_totals(self):
        self.crear_gasto()
        for datos in (
            {"categoria": "invalida"},
            {"fecha_inicio": "invalida"},
            {"fecha_inicio": "2026-02-01", "fecha_fin": "2026-01-01"},
            {"fecha_inicio": "invalida", "page": "99"},
        ):
            with self.subTest(datos=datos):
                response = self.client.get(self.url, datos)
                self.assertContains(response, "Revisa los filtros", status_code=400)
                self.assertTrue(response.context["filtros"].errors)
                self.assertNotIn("resumen", response.context)
                self.assertNotContains(response, "Comida de prueba", status_code=400)

    def test_bad_page_returns_404(self):
        self.crear_gasto()
        for page in ("no-es-numero", 0, 99):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(self.url, {"page": page}).status_code, 404)

    def test_description_is_escaped_and_blank_description_is_supported(self):
        self.crear_gasto(descripcion="<script>alert('x')</script>")
        self.crear_gasto(descripcion="")
        response = self.client.get(self.url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertContains(response, "Sin descripción")

    def test_list_does_not_allow_creating_via_post(self):
        self.assertEqual(self.client.post(self.url, {"monto": "10.00"}).status_code, 405)
        self.assertEqual(Gasto.objects.count(), 0)

    def test_stylesheet_is_discoverable(self):
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find("spending/css/spending.css"))


class GastoAdminTests(GastoTestCase):
    def setUp(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save()
        self.client.force_login(self.usuario)

    def test_admin_list_and_search_exclude_other_owners_even_for_superuser(self):
        self.crear_gasto(descripcion="Gasto propio")
        self.crear_gasto(usuario=self.otro, descripcion="Secreto ajeno")
        url = reverse("admin:spending_gasto_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Gasto propio")
        self.assertNotContains(response, "Secreto ajeno")
        filtrado = self.client.get(url, {"q": "Secreto"})
        self.assertEqual(filtrado.context["cl"].result_count, 0)

    def test_admin_add_assigns_owner_and_ignores_spoofed_owner(self):
        url = reverse("admin:spending_gasto_add")
        self.assertNotContains(self.client.get(url), 'name="usuario"')
        response = self.client.post(url, {
            "usuario": self.otro.pk, "monto": "75.25", "categoria": "salud",
            "descripcion": "Alta por admin", "fecha": "2026-01-15", "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 302)
        gasto = Gasto.objects.get(descripcion="Alta por admin")
        self.assertEqual(gasto.usuario, self.usuario)

    def test_admin_cannot_read_change_or_delete_other_users_expense(self):
        ajeno = self.crear_gasto(usuario=self.otro, descripcion="No visible")
        change_url = reverse("admin:spending_gasto_change", args=[ajeno.pk])
        self.assertNotContains(self.client.get(change_url, follow=True), "No visible")
        self.client.post(change_url, {
            "monto": "1.00", "categoria": "otros", "descripcion": "Manipulado",
            "fecha": "2026-01-01", "_save": "Guardar",
        })
        self.client.post(
            reverse("admin:spending_gasto_delete", args=[ajeno.pk]), {"post": "yes"}
        )
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.descripcion, "No visible")
        self.assertEqual(ajeno.monto, Decimal("125.50"))

    def test_admin_can_update_and_delete_own_expense(self):
        propio = self.crear_gasto()
        response = self.client.post(
            reverse("admin:spending_gasto_change", args=[propio.pk]),
            {"monto": "50.00", "categoria": "otros", "descripcion": "Actualizado",
             "fecha": "2026-01-15", "_save": "Guardar"},
        )
        self.assertEqual(response.status_code, 302)
        propio.refresh_from_db()
        self.assertEqual(propio.monto, Decimal("50.00"))
        self.assertEqual(propio.usuario, self.usuario)
        self.client.post(
            reverse("admin:spending_gasto_delete", args=[propio.pk]), {"post": "yes"}
        )
        self.assertFalse(Gasto.objects.filter(pk=propio.pk).exists())

    def test_admin_rejects_invalid_amount(self):
        response = self.client.post(reverse("admin:spending_gasto_add"), {
            "monto": "-1.00", "categoria": "otros", "fecha": "2026-01-15",
            "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("monto", response.context["adminform"].form.errors)
        self.assertFalse(Gasto.objects.exists())


class SeedGastosTests(GastoTestCase):
    def test_demo_data_is_explicit_idempotent_and_does_not_change_real_data(self):
        real = self.crear_gasto(descripcion="Gasto real")
        ajeno = self.crear_gasto(usuario=self.otro)
        salida = StringIO()
        call_command("seed_gastos", username=self.usuario.username, stdout=salida)
        call_command("seed_gastos", username=self.usuario.username, stdout=salida)
        demo = self.usuario.gastos.filter(descripcion__startswith="[DEMO ")
        self.assertEqual(demo.count(), len(DATOS_DEMO))
        self.assertEqual(set(demo.values_list("categoria", flat=True)), set(CATEGORIAS))
        self.assertEqual(self.otro.gastos.count(), 1)
        self.assertTrue(Gasto.objects.filter(pk=ajeno.pk).exists())
        real.refresh_from_db()
        self.assertEqual(real.monto, Decimal("125.50"))
        self.assertEqual(real.descripcion, "Gasto real")
        self.assertIn("0 gastos de demostración creados", salida.getvalue())

    def test_demo_dates_use_local_today_and_do_not_shift_on_rerun(self):
        with patch("spending.management.commands.seed_gastos.timezone.localdate",
                   return_value=date(2026, 1, 15)):
            call_command("seed_gastos", username=self.usuario.username, stdout=StringIO())
        with patch("spending.management.commands.seed_gastos.timezone.localdate",
                   return_value=date(2026, 1, 16)):
            call_command("seed_gastos", username=self.usuario.username, stdout=StringIO())
        demo = self.usuario.gastos.filter(descripcion__startswith="[DEMO ")
        self.assertEqual(demo.latest("fecha").fecha, date(2026, 1, 15))
        self.assertEqual(demo.earliest("fecha").fecha, date(2025, 12, 4))

    def test_unknown_user_raises_error_without_creating_data(self):
        with self.assertRaisesMessage(CommandError, "No existe el usuario indicado"):
            call_command("seed_gastos", username="no-existe", stdout=StringIO())
        self.assertFalse(Gasto.objects.exists())
