"""Ejemplos sencillos de manejo de errores en Python."""


class EdadInvalidaError(ValueError):
	"""Se produce cuando una edad no puede ser negativa."""


def calcular_anio_nacimiento(edad: int, anio_actual: int = 2026) -> int:
	"""Devuelve el año aproximado de nacimiento para una edad valida."""
	if edad < 0:
		raise EdadInvalidaError("La edad no puede ser negativa.")
	return anio_actual - edad


def procesar_edad(valor: str) -> None:
	"""Convierte una edad y muestra el flujo de manejo de excepciones."""
	print(f"\nEntrada: {valor!r}")

	try:
		edad = int(valor)
		anio_nacimiento = calcular_anio_nacimiento(edad)
	except ValueError as error:
		print(f"Error: {error}")
	else:
		print(f"La conversion fue correcta. Anio de nacimiento: {anio_nacimiento}.")
	finally:
		print("Finally: este bloque se ejecuta siempre.")


def dividir(dividendo: float, divisor: float) -> None:
	"""Muestra el manejo especifico de una division entre cero."""
	try:
		resultado = dividendo / divisor
	except ZeroDivisionError:
		print("Error: no es posible dividir entre cero.")
	else:
		print(f"Resultado de la division: {resultado}")
	finally:
		print("Finally: la operacion de division termino.")


def main() -> None:
	print("=== Ejemplo de manejo de errores ===")
	procesar_edad("20")
	procesar_edad("-5")
	procesar_edad("veinte")
	print()
	dividir(10, 2)
	dividir(10, 0)


if __name__ == "__main__":
	main()
