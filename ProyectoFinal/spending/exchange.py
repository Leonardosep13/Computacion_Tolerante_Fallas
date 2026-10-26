import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

import httpx
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)
API_CAMBIO = "https://api.frankfurter.dev/v2/rate"
MAX_ANTIGUEDAD = timedelta(days=7)


def decimal_positivo(valor: object, *, campo: str, maximo: Decimal, decimales: int) -> Decimal:
    if not isinstance(valor, (str, Decimal)) or len(str(valor)) > 48:
        raise ValidationError(f"{campo} debe ser texto decimal válido.")
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        raise ValidationError(f"{campo} debe ser texto decimal válido.") from None
    if not numero.is_finite() or numero <= 0 or numero > maximo:
        raise ValidationError(f"{campo} debe ser positivo, finito y no superar {maximo}.")
    exponente = numero.as_tuple().exponent
    if not isinstance(exponente, int) or exponente < -decimales:
        raise ValidationError(f"{campo} admite como máximo {decimales} decimales.")
    return numero


def texto_decimal(valor: Decimal) -> str:
    texto = format(valor, "f")
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


@dataclass(frozen=True)
class Conversion:
    monto_original: Decimal
    moneda_original: str
    monto_mxn: Decimal
    tipo_cambio: Decimal
    fecha_tasa: date
    fuente: str

    def datos(self) -> dict[str, str]:
        return {
            "monto_original": texto_decimal(self.monto_original),
            "moneda_original": self.moneda_original,
            "monto_mxn": str(self.monto_mxn),
            "tipo_cambio": texto_decimal(self.tipo_cambio),
            "fecha_tasa": self.fecha_tasa.isoformat(),
            "fuente": self.fuente,
        }

    def referencia(self) -> str:
        return (
            f"[{texto_decimal(self.monto_original)} {self.moneda_original}; "
            f"1 {self.moneda_original}={texto_decimal(self.tipo_cambio)} MXN; "
            f"{self.fecha_tasa.isoformat()}; {self.fuente}]"
        )


def obtener_tasa(moneda: str, fecha: date) -> tuple[Decimal, date]:
    aviso = (
        f"No se pudo obtener una tasa de {moneda} a MXN para {fecha.isoformat()}. "
        "No se registró el gasto. Indica el tipo de cambio en MXN por 1 unidad "
        f"de {moneda} o el importe final cobrado en MXN."
    )
    try:
        # Solo se envían el par público de monedas y la fecha, nunca datos del gasto.
        with httpx.Client(timeout=8.0, follow_redirects=False, trust_env=False) as cliente:
            respuesta = cliente.get(
                f"{API_CAMBIO}/{moneda}/MXN", params={"date": fecha.isoformat()}
            )
            respuesta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("No se pudo consultar la tasa de referencia en Frankfurter.")
        raise ValidationError(aviso) from None
    try:
        datos = respuesta.json(parse_float=Decimal)
        if not isinstance(datos, dict) or datos.get("base") != moneda or datos.get("quote") != "MXN":
            raise ValueError("Par de monedas no válido.")
        fecha_texto = datos.get("date")
        if not isinstance(fecha_texto, str):
            raise ValueError("Falta la fecha de la tasa.")
        fecha_tasa = date.fromisoformat(fecha_texto)
        if fecha_tasa.isoformat() != fecha_texto or not fecha - MAX_ANTIGUEDAD <= fecha_tasa <= fecha:
            raise ValueError("Fecha de tasa no válida o demasiado antigua.")
        tasa = datos.get("rate")
        if type(tasa) is int:
            tasa = str(tasa)
        return decimal_positivo(
            tasa, campo="El tipo de cambio", maximo=Decimal("1000000000000"), decimales=12,
        ), fecha_tasa
    except (ValueError, InvalidOperation, ValidationError):
        logger.warning("Frankfurter devolvió una tasa de referencia no válida.")
        raise ValidationError(aviso) from None


def convertir_a_mxn(
    monto: str | Decimal, moneda: str, fecha: date, tipo_cambio: str | None = None,
) -> Conversion:
    if not isinstance(moneda, str) or not re.fullmatch(r"[A-Z]{3}", moneda.strip().upper()):
        raise ValidationError("Indica la moneda con un código ISO de tres letras, por ejemplo USD.")
    moneda = moneda.strip().upper()
    importe = decimal_positivo(
        monto, campo="El monto", maximo=Decimal("999999999999999999.99999999"), decimales=8,
    )
    if moneda == "MXN":
        if tipo_cambio is not None:
            raise ValidationError("Un gasto en MXN no necesita tipo de cambio.")
        exponente = importe.as_tuple().exponent
        if not isinstance(exponente, int) or exponente < -2:
            raise ValidationError("El monto en MXN admite como máximo dos decimales.")
        tasa, fecha_tasa, fuente = Decimal("1"), fecha, "MXN"
    else:
        if fecha > timezone.localdate():
            raise ValidationError(
                "No se registró el gasto: no se convierten gastos con fecha futura. "
                "Indica la fecha real del gasto."
            )
        if tipo_cambio is None:
            tasa, fecha_tasa = obtener_tasa(moneda, fecha)
            fuente = "Frankfurter"
        else:
            tasa = decimal_positivo(
                tipo_cambio, campo="El tipo de cambio",
                maximo=Decimal("1000000000000"), decimales=12,
            )
            fecha_tasa, fuente = fecha, "usuario"
    with localcontext() as contexto:
        contexto.prec = 60
        monto_mxn = (importe * tasa).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not Decimal("0.01") <= monto_mxn <= Decimal("99999999.99"):
        raise ValidationError(
            "No se registró el gasto: el importe convertido debe estar entre 0.01 "
            "y 99999999.99 MXN."
        )
    return Conversion(importe, moneda, monto_mxn, tasa, fecha_tasa, fuente)
