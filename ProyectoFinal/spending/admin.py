from django.contrib import admin

from .models import Gasto


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "monto", "categoria", "fecha")
    list_filter = ("categoria", "fecha")
    search_fields = ("descripcion",)
    date_hierarchy = "fecha"
    exclude = ("usuario",)
    readonly_fields = ("creado_en",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(usuario=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
