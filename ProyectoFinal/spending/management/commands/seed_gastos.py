from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from spending.models import Gasto

DATOS_DEMO = [
    ("250.00", "comida", "Comida en el centro", 0),
    ("32.00", "transporte", "Viajes en transporte público", 1),
    ("185.50", "entretenimiento", "Entrada al cine", 2),
    ("499.00", "servicios", "Servicio de internet", 3),
    ("320.00", "salud", "Compra en farmacia", 4),
    ("245.00", "educacion", "Libro de programación", 5),
    ("85.00", "otros", "Artículos para el hogar", 6),
    ("680.75", "comida", "Despensa semanal", 7),
    ("150.00", "transporte", "Traslado en taxi", 8),
    ("120.00", "entretenimiento", "Suscripción de música", 9),
    ("235.40", "servicios", "Recibo de agua", 10),
    ("550.00", "salud", "Consulta médica", 11),
    ("199.00", "educacion", "Curso en línea", 12),
    ("90.00", "otros", "Papelería", 13),
    ("95.00", "comida", "Desayuno", 16),
    ("450.00", "transporte", "Gasolina", 19),
    ("280.00", "entretenimiento", "Visita al museo y cafetería", 23),
    ("620.25", "servicios", "Recibo de luz", 27),
    ("180.00", "salud", "Artículos de cuidado personal", 31),
    ("350.00", "educacion", "Material de estudio", 35),
    ("140.00", "otros", "Reparación de un accesorio", 42),
]


class Command(BaseCommand):
    help = "Carga gastos ficticios [DEMO] para un usuario existente, sin duplicarlos."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            usuario = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError("No existe el usuario indicado.") from None

        hoy = timezone.localdate()
        creados = 0
        for indice, (monto, categoria, descripcion, dias) in enumerate(DATOS_DEMO, 1):
            _, creado = Gasto.objects.get_or_create(
                usuario=usuario,
                descripcion=f"[DEMO {indice:02d}] {descripcion}",
                defaults={
                    "monto": Decimal(monto),
                    "categoria": categoria,
                    "fecha": hoy - timedelta(days=dias),
                },
            )
            creados += creado
        self.stdout.write(
            self.style.SUCCESS(
                f"{creados} gastos de demostración creados para {usuario.get_username()}; "
                f"{len(DATOS_DEMO) - creados} ya existían."
            )
        )
