"""
Configuración ASGI para clima_project.

Se recomienda ejecutar el proyecto con un servidor ASGI (p. ej. uvicorn)
para aprovechar por completo las vistas asíncronas.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clima_project.settings")

application = get_asgi_application()
