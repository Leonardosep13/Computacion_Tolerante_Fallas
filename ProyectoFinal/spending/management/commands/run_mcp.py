from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from spending.mcp_server import crear_servidor


class Command(BaseCommand):
    help = "Inicia MCP por stdio, limitado a un usuario local explícito."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)

    def handle(self, *args, **options):
        usuario_id = options["user_id"]
        if usuario_id < 1 or not get_user_model().objects.filter(
            pk=usuario_id, is_active=True
        ).exists():
            raise CommandError("Se requiere el ID de un usuario activo existente.")
        crear_servidor(usuario_id).run(transport="stdio")
