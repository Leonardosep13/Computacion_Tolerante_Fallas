from typing import Annotated, TypeAlias

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from . import services
from .categories import CATEGORIAS

Categoria: TypeAlias = Annotated[
    str, Field(json_schema_extra={"enum": list(CATEGORIAS)})
]


def serializar_gasto(gasto):
    return {
        "id": gasto.pk,
        "monto": str(gasto.monto),
        "categoria": gasto.categoria,
        "descripcion": gasto.descripcion,
        "fecha": gasto.fecha.isoformat(),
    }


def crear_servidor(usuario_id: int) -> FastMCP:
    servidor = FastMCP("SpendingAdmin", log_level="WARNING")

    def ejecutar(user_id, funcion, **argumentos):
        if user_id != usuario_id:
            return {"error": "No puedes operar sobre los gastos de otro usuario."}
        try:
            return funcion(usuario_id, **argumentos)
        except ValidationError as error:
            return {"error": " ".join(error.messages)}

    @servidor.tool()
    async def registrar_gasto(
        user_id: int, monto: str, categoria: Categoria, descripcion: str = "",
        fecha: str | None = None, moneda: str = "MXN", tipo_cambio: str | None = None,
    ) -> dict:
        """Registra UN gasto propio y almacena MXN. Envía el monto ORIGINAL como
        texto decimal positivo y moneda ISO (MXN por defecto; USD, EUR, CAD...).
        Para moneda extranjera consulta Frankfurter a la fecha del gasto y calcula
        la conversión; NO conviertas antes de llamar. tipo_cambio es opcional:
        solo si el usuario lo dio explícitamente en MXN por 1 unidad extranjera.
        Si falla la tasa no guarda nada: pide tasa al usuario o cargo final en MXN.
        MXN admite dos decimales; el resultado debe ser 0.01 a 99999999.99 MXN.
        Fecha YYYY-MM-DD; sin fecha usa hoy en Guadalajara. No fechas futuras
        para conversiones. Devuelve monto guardado en MXN y detalle de conversión.
        No repetir una operación exitosa. Si faltan monto o categoría, preguntar.
        """
        def registrar(usuario_id, **datos):
            gasto, conversion = services.registrar_gasto_en_moneda(usuario_id, **datos)
            resultado = {**serializar_gasto(gasto), "moneda": "MXN"}
            if conversion.moneda_original != "MXN":
                resultado["conversion"] = conversion.datos()
            return resultado

        return await sync_to_async(ejecutar)(
            user_id, registrar, monto=monto, categoria=categoria,
            descripcion=descripcion, fecha=fecha, moneda=moneda, tipo_cambio=tipo_cambio,
        )

    @servidor.tool()
    async def obtener_resumen_gastos(
        user_id: int, fecha_inicio: str | None = None, fecha_fin: str | None = None,
        categoria: Categoria | None = None,
    ) -> dict:
        """Consulta total MXN, promedio, cantidad y desglose por categoría propios.
        Fechas opcionales YYYY-MM-DD, inclusivas. Para 'este mes', calcular inicio
        del mes y hoy usando la fecha actual indicada. Sin filtros: todo el historial.
        """
        def resumir(usuario_id, **filtros):
            resumen = services.obtener_resumen_gastos(usuario_id, **filtros)
            return {
                **resumen,
                "total": str(resumen["total"]),
                "promedio": str(resumen["promedio"]),
                "por_categoria": [
                    {**fila, "total": str(fila["total"])}
                    for fila in resumen["por_categoria"]
                ],
            }

        return await sync_to_async(ejecutar)(
            user_id, resumir, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
            categoria=categoria,
        )

    @servidor.tool()
    async def listar_gastos(user_id: int, limite: int = 10) -> dict:
        """Consulta los últimos gastos propios, del más reciente al más antiguo.
        Límite entre 1 y 20 (por defecto 10). Devuelve id, monto, categoría,
        descripción y fecha YYYY-MM-DD. No permite consultar otros usuarios.
        """
        def listar(usuario_id, limite):
            if not 1 <= limite <= 20:
                raise ValidationError("El límite debe estar entre 1 y 20.")
            return {
                "gastos": [
                    serializar_gasto(gasto)
                    for gasto in services.listar_gastos(usuario_id)[:limite]
                ]
            }

        return await sync_to_async(ejecutar)(user_id, listar, limite=limite)

    return servidor
