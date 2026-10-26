from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/home.html"
    extra_context = {"title": "Inicio"}


class UpcomingView(LoginRequiredMixin, TemplateView):
    template_name = "core/proximamente.html"