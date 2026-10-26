from django.urls import path

from .views import GastoListView

urlpatterns = [
    path("gastos/", GastoListView.as_view(), name="gastos"),
]
