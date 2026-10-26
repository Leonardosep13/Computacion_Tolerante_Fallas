from datetime import date
from decimal import Decimal
from decimal import InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.utils import timezone

from .categories import CATEGORIAS
from .models import Gasto


def listar_gastos(usuario_id, *, fecha_inicio=None, fecha_fin=None, categoria=None):
    fecha_inicio = validar_fecha(fecha_inicio)
    fecha_fin = validar_fecha(fecha_fin)
    if categoria and categoria not in CATEGORIAS:
        raise ValidationError("Selecciona una categoría válida.")
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise ValidationError(
            "La fecha inicial no puede ser posterior a la fecha final."
        )

    gastos = Gasto.objects.filter(usuario_id=usuario_id)
    if fecha_inicio:
        gastos = gastos.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        gastos = gastos.filter(fecha__lte=fecha_fin)
    if categoria:
        gastos = gastos.filter(categoria=categoria)
    return gastos


def resumir_gastos(gastos):
    resumen = gastos.aggregate(total=Sum("monto"), cantidad=Count("pk"))
    total = (resumen["total"] or Decimal("0.00")).quantize(Decimal("0.01"))
    cantidad = resumen["cantidad"]
    promedio = total / cantidad if cantidad else Decimal("0.00")
    return {
        "total": total,
        "cantidad": cantidad,
        "promedio": promedio.quantize(Decimal("0.01")),
    }


def validar_fecha(valor):
    if valor is None or valor == "":
        return None
    if type(valor) is date:
        return valor
    if isinstance(valor, str):
        try:
            fecha = date.fromisoformat(valor)
        except ValueError:
            raise ValidationError("La fecha debe ser válida y usar YYYY-MM-DD.") from None
        if fecha.isoformat() == valor:
            return fecha
    raise ValidationError("La fecha debe ser válida y usar YYYY-MM-DD.")


def registrar_gasto(usuario_id, *, monto, categoria, descripcion="", fecha=None):
    if not isinstance(monto, (str, Decimal)):
        raise ValidationError("Envía el monto como texto decimal, por ejemplo '250.00'.")
    try:
        importe = Decimal(monto)
    except InvalidOperation:
        raise ValidationError("El monto debe ser un número decimal válido.") from None
    if not importe.is_finite():
        raise ValidationError("El monto debe ser un número decimal finito.")
    gasto = Gasto(
        usuario_id=usuario_id,
        monto=importe,
        categoria=categoria,
        descripcion=descripcion,
        fecha=validar_fecha(fecha) or timezone.localdate(),
    )
    gasto.full_clean()
    gasto.save()
    return gasto


def obtener_resumen_gastos(usuario_id, *, fecha_inicio=None, fecha_fin=None, categoria=None):
    gastos = listar_gastos(
        usuario_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, categoria=categoria
    )
    resumen = resumir_gastos(gastos)
    resumen["por_categoria"] = [
        {
            "categoria": fila["categoria"],
            "nombre": CATEGORIAS[fila["categoria"]]["nombre"],
            "total": fila["total"].quantize(Decimal("0.01")),
            "cantidad": fila["cantidad"],
        }
        for fila in gastos.order_by().values("categoria").annotate(
            total=Sum("monto"), cantidad=Count("pk")
        ).order_by("categoria")
    ]
    return resumen
