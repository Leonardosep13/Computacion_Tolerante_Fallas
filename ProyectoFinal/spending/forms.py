from django import forms

from .categories import CATEGORIA_CHOICES


class GastoFiltroForm(forms.Form):
    fecha_inicio = forms.DateField(
        label="Desde",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    fecha_fin = forms.DateField(
        label="Hasta",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    categoria = forms.ChoiceField(
        label="Categoría",
        required=False,
        choices=[("", "Todas las categorías"), *CATEGORIA_CHOICES],
    )

    def clean(self):
        data = super().clean()
        inicio = data.get("fecha_inicio")
        fin = data.get("fecha_fin")
        if inicio and fin and inicio > fin:
            raise forms.ValidationError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )
        return data
