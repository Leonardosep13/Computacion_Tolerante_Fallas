# Ejemplo de Apache Airflow: resumen diario de ventas

DAG de Apache Airflow que lee un CSV de ventas, valida los datos, calcula las unidades vendidas e ingresos por producto y guarda el resultado en otro CSV.

## Estructura

```
Airflow/
├── main.py                  # Definición del DAG `resumen_ventas_diarias`
├── data/ventas.csv          # Datos de entrada de ejemplo
├── output/resumen_ventas.csv# Resumen generado por el DAG
├── requirements.txt         # Dependencia de Airflow
├── .airflowignore           # Excluye `venv` del escaneo de DAGs
└── venv/                    # Entorno virtual (Python 3.12)
```

## Flujo del DAG

El DAG se ejecuta a diario (`@daily`, `catchup=False`) y tiene tres tareas encadenadas:

1. **`cargar_ventas`**: lee `data/ventas.csv`, valida las columnas (`producto`, `cantidad`, `precio_unitario`) y los valores (cantidad > 0, precio ≥ 0, producto no vacío).
2. **`calcular_resumen`**: agrupa por producto y suma unidades e ingresos con `Decimal` para evitar errores de redondeo.
3. **`guardar_resumen`**: escribe `output/resumen_ventas.csv` ordenado por producto.

Los datos viajan entre tareas mediante XCom, por eso se devuelven listas de diccionarios con valores simples (las claves de texto con acentos dentro de un diccionario provocaron un error de transporte en XCom, así que el resumen se devuelve como lista de filas).

### Ejemplo

Entrada (`data/ventas.csv`):

```csv
producto,cantidad,precio_unitario
café,3,4.50
té,2,3.25
café,1,4.50
pan,5,1.20
```

Salida (`output/resumen_ventas.csv`):

```csv
producto,unidades_vendidas,ingresos_totales
café,4,18.00
pan,5,6.00
té,2,6.50
```

## Instalación

Se usa el entorno virtual dentro de esta carpeta y el archivo de restricciones oficial de Airflow para una instalación reproducible:

```bash
cd Airflow
./venv/bin/python -m pip install -r requirements.txt \
  --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt
```

Versión instalada: **Apache Airflow 3.3.2** (Python 3.12). `pip check` no reporta conflictos.

## Ejecución

Este archivo define un DAG, por lo que **no se ejecuta con `python main.py`**. Para probarlo de principio a fin:

```bash
cd Airflow
export AIRFLOW_HOME=/tmp/airflow-ejemplo-ventas
export AIRFLOW__CORE__DAGS_FOLDER="$PWD"

./venv/bin/python -m airflow db migrate        # solo la primera vez
./venv/bin/python -m airflow dags test resumen_ventas_diarias 2026-11-02
```

Siempre debe usarse el intérprete `Airflow/venv/bin/python`. Con otro entorno aparece `ModuleNotFoundError: No module named 'airflow'`.

Para usarlo con la interfaz web, apunta `AIRFLOW__CORE__DAGS_FOLDER` a esta carpeta y levanta Airflow (por ejemplo, `./venv/bin/python -m airflow standalone`).

## Notas

- `.airflowignore` contiene `venv`; sin él, Airflow falla al recorrer la carpeta de DAGs por enlaces recursivos dentro del entorno virtual.
- `AIRFLOW_HOME` apunta a `/tmp` en los comandos de prueba para no generar archivos de configuración ni base de datos dentro del repositorio.
- Pylance puede marcar `airflow.sdk` como no resuelto si el editor no está usando `Airflow/venv`; selecciona ese intérprete en VS Code.
