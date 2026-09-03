# Ejemplo de Manejo de Errores

Este directorio contiene un script sencillo que muestra el manejo de excepciones en Python mediante los bloques `try`, `except`, `else` y `finally`.

## Contenido

El archivo `main.py` demuestra los siguientes casos:

- Conversión correcta de una edad a entero.
- Error al recibir una edad negativa mediante la excepción personalizada `EdadInvalidaError`.
- Error al intentar convertir texto no numérico a entero (`ValueError`).
- División correcta y manejo de división entre cero (`ZeroDivisionError`).
- Ejecución del bloque `finally` en todos los casos.

## Requisitos

- Python 3.10 o superior.

El ejemplo no utiliza dependencias externas.

## Ejecución

Desde este directorio, ejecutar:

```bash
python main.py
```

El programa imprimirá el resultado de cada caso y mostrará cuándo se ejecuta el bloque `finally`.