from functools import partial

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import EmailForm, ProfileForm, UserCreationFormWithEmail
from .models import Profile


class SignUpView(CreateView):
    form_class = UserCreationFormWithEmail
    template_name = "registration/signup.html"

    def get_success_url(self):
        return f"{reverse('login')}?register"

    @transaction.atomic
    def form_valid(self, form):
        return super().form_valid(form)


class LoginView(DjangoLoginView):
    template_name = "registration/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("profile")
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = ProfileForm
    template_name = "registration/profile_form.html"
    success_url = reverse_lazy("profile")
    success_message = "Tu perfil se actualizó correctamente."

    def get_object(self, queryset=None):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile

    @transaction.atomic
    def form_valid(self, form):
        avatar_anterior = Profile.objects.get(pk=self.object.pk).avatar
        response = super().form_valid(form)
        if avatar_anterior and avatar_anterior.name != self.object.avatar.name:
            transaction.on_commit(partial(avatar_anterior.delete, save=False))
        return response


class ProfileEmailView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = EmailForm
    template_name = "registration/profile_email_form.html"
    success_url = reverse_lazy("profile")
    success_message = "Tu correo electrónico se actualizó correctamente."

    def get_object(self, queryset=None):
        return self.request.user
