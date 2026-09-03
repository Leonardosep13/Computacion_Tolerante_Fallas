# Computacion Tolerante a Fallas

Repositorio de entregas para la materia **Computacion Tolerante a Fallas**.
Cada tarea se guarda en un directorio independiente para que pueda ejecutarse y evaluarse de forma aislada durante el curso.

## Estructura del repositorio

Cada tarea debe utilizar el siguiente formato:

```text
.
├── homework-01/
│   ├── README.md
│   ├── src/
│   ├── tests/
│   └── requirements.txt
├── homework-02/
│   └── ...
└── README.md
```

- `homework-XX/`: directorio de una tarea, numerado con dos digitos.
- `README.md`: descripcion de la solucion, instrucciones de ejecucion y supuestos relevantes.
- `src/`: codigo fuente de la tarea.
- `tests/`: pruebas automatizadas, cuando apliquen.
- `requirements.txt`: dependencias necesarias para ejecutar la tarea, cuando apliquen.

## Reglas para cada entrega

1. Cada tarea debe ser autocontenida: no debe depender del contenido de otros directorios de tareas.
2. Incluir instrucciones claras para instalar dependencias y ejecutar los scripts.
3. Indicar los argumentos de entrada, el formato esperado de los datos y el resultado esperado.
4. No incluir archivos generados, entornos virtuales, credenciales ni archivos binarios innecesarios.
5. Agregar pruebas o ejemplos de uso que permitan verificar el comportamiento de la solucion.

## Ejecucion

Las instrucciones exactas deben estar en el `README.md` de cada tarea. Como guia, la ejecucion deberia seguir una forma similar a esta:

```bash
cd homework-01
python -m pip install -r requirements.txt
python src/main.py
```

## Evaluacion

El docente podra clonar este repositorio y probar cada entrega desde su directorio correspondiente. Por ello, antes de entregar, se debe verificar que la tarea pueda ejecutarse desde cero siguiendo unicamente las instrucciones incluidas en su propio directorio.
