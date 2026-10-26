from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile

User = get_user_model()


def _validar_email_unico(email, usuario_id=None):
    email = User.objects.normalize_email(email)
    usuarios = User.objects.filter(email__iexact=email)
    if usuario_id is not None:
        usuarios = usuarios.exclude(pk=usuario_id)
    if usuarios.exists():
        raise forms.ValidationError(
            "El email ya está registrado, prueba con otro.", code="duplicate_email"
        )
    return email


class UserCreationFormWithEmail(UserCreationForm):
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        max_length=254,
        help_text="Requerido. 254 caracteres como máximo y debe ser válido.",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data["email"])


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio']
        labels = {"avatar": "Avatar", "bio": "Biografía"}
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class':'form-control-file mt-3'}),
            'bio': forms.Textarea(attrs={'class':'form-control mt-3', 'rows':3, 'placeholder':'Biografía'}),
        }


class EmailForm(forms.ModelForm):
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        max_length=254,
        help_text="Requerido. 254 caracteres como máximo y debe ser válido.",
    )

    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data["email"], self.instance.pk)