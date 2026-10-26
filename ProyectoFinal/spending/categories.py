CATEGORIAS = {
    "comida": {"nombre": "Comida", "color": "var(--category-comida)"},
    "transporte": {"nombre": "Transporte", "color": "var(--category-transporte)"},
    "entretenimiento": {
        "nombre": "Entretenimiento",
        "color": "var(--category-entretenimiento)",
    },
    "servicios": {"nombre": "Servicios", "color": "var(--category-servicios)"},
    "salud": {"nombre": "Salud", "color": "var(--category-salud)"},
    "educacion": {"nombre": "Educación", "color": "var(--category-educacion)"},
    "otros": {"nombre": "Otros", "color": "var(--category-otros)"},
}

CATEGORIA_CHOICES = [
    (clave, categoria["nombre"]) for clave, categoria in CATEGORIAS.items()
]
