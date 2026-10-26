from collections.abc import Callable
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .categories import CATEGORIA_CHOICES, CATEGORIAS


class Gasto(models.Model):
    get_categoria_display: Callable[[], str]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gastos"
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en", "-pk"]
        indexes = [
            models.Index(fields=["usuario", "-fecha"], name="gasto_usuario_fecha_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monto__gt=0), name="gasto_monto_positivo"
            ),
        ]

    @property
    def categoria_color(self):
        return CATEGORIAS[self.categoria]["color"]

    def __str__(self):
        return f"{self.get_categoria_display()} · ${self.monto:.2f} · {self.fecha}"
