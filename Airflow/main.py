import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from airflow.sdk import dag, task


DATA_FILE = Path(__file__).parent / "data" / "ventas.csv"
OUTPUT_FILE = Path(__file__).parent / "output" / "resumen_ventas.csv"


@dag(
    dag_id="resumen_ventas_diarias",
    description="Resume unidades e ingresos por producto desde un archivo CSV",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ejemplo", "ventas"],
)
def resumen_ventas_diarias():
    @task
    def cargar_ventas() -> list[dict[str, str | int]]:
        ventas: list[dict[str, str | int]] = []

        with DATA_FILE.open(newline="", encoding="utf-8") as archivo:
            lector = csv.DictReader(archivo)
            columnas_requeridas = {"producto", "cantidad", "precio_unitario"}
            if not columnas_requeridas.issubset(lector.fieldnames or []):
                raise ValueError(
                    "El CSV debe incluir las columnas: "
                    "producto, cantidad, precio_unitario"
                )

            for numero_fila, fila in enumerate(lector, start=2):
                producto = (fila.get("producto") or "").strip()
                try:
                    cantidad = int(fila.get("cantidad") or "")
                    precio = Decimal(fila.get("precio_unitario") or "")
                except (ValueError, InvalidOperation) as error:
                    raise ValueError(
                        f"Datos numéricos inválidos en la fila {numero_fila}"
                    ) from error

                if not producto or cantidad <= 0 or not precio.is_finite() or precio < 0:
                    raise ValueError(f"Datos inválidos en la fila {numero_fila}")

                ventas.append(
                    {
                        "producto": producto,
                        "cantidad": cantidad,
                        "precio_unitario": str(precio),
                    }
                )

        return ventas

    @task
    def calcular_resumen(
        ventas: list[dict[str, str | int]],
    ) -> list[dict[str, str | int]]:
        resumen: dict[str, dict[str, int | Decimal]] = {}

        for venta in ventas:
            producto = str(venta["producto"])
            cantidad = int(venta["cantidad"])
            precio = Decimal(str(venta["precio_unitario"]))
            datos = resumen.setdefault(
                producto, {"unidades": 0, "ingresos": Decimal("0")}
            )
            datos["unidades"] = int(datos["unidades"]) + cantidad
            datos["ingresos"] = Decimal(str(datos["ingresos"])) + cantidad * precio

        return [
            {
                "producto": producto,
                "unidades": int(datos["unidades"]),
                "ingresos": f"{Decimal(str(datos['ingresos'])):.2f}",
            }
            for producto, datos in resumen.items()
        ]

    @task
    def guardar_resumen(resumen: list[dict[str, str | int]]) -> None:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["producto", "unidades_vendidas", "ingresos_totales"])
            for datos in sorted(resumen, key=lambda fila: str(fila["producto"])):
                escritor.writerow(
                    [datos["producto"], datos["unidades"], datos["ingresos"]]
                )

        print(f"Resumen guardado en: {OUTPUT_FILE}")

    guardar_resumen(calcular_resumen(cargar_ventas()))


resumen_ventas_diarias()
