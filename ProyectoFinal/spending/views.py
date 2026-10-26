from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.views.generic import ListView

from .forms import GastoFiltroForm
from .models import Gasto
from .services import listar_gastos, resumir_gastos


class GastoListView(LoginRequiredMixin, ListView):
    object_list: QuerySet[Gasto]
    template_name = "spending/gasto_list.html"
    context_object_name = "gastos"
    paginate_by = 10
    extra_context = {"title": "Gastos"}

    def get_queryset(self):
        self.filtros = GastoFiltroForm(self.request.GET)
        gastos = listar_gastos(self.request.user.pk)
        if not self.filtros.is_valid():
            return gastos.none()
        return listar_gastos(self.request.user.pk, **self.filtros.cleaned_data)

    def get_paginate_by(self, queryset):
        if not self.filtros.is_valid():
            return None
        return super().get_paginate_by(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtros"] = self.filtros
        context["filtros_validos"] = self.filtros.is_valid()
        if self.filtros.is_valid():
            context["resumen"] = resumir_gastos(self.object_list)
            context["filtros_activos"] = any(self.filtros.cleaned_data.values())
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if not self.filtros.is_valid():
            response.status_code = 400
        return response
