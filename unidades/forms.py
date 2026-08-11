from django import forms
from .models import UnidadeSaude, Profissional


class UnidadeSaudeForm(forms.ModelForm):
    class Meta:
        model = UnidadeSaude
        fields = ["nome", "endereco", "contato"]

        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nome da unidade"
            }),
            "endereco": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Endereço completo"
            }),
            "contato": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "(83) 99999-9999"
            }),
        }


class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = [
            "nome",
            "cpf",
            "conselho",
            "registro",
            "especialidade",
            "telefone",
            "email",
            "unidade",
        ]

        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00"}),
            "conselho": forms.Select(attrs={"class": "form-select"}),
            "registro": forms.TextInput(attrs={"class": "form-control"}),
            "especialidade": forms.TextInput(attrs={"class": "form-control"}),
            "telefone": forms.TextInput(attrs={"class": "form-control", "placeholder": "(83) 99999-9999"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "unidade": forms.Select(attrs={"class": "form-select"}),
        }