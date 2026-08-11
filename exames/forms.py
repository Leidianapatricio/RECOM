from django import forms
from .models import TipoExame
from .models import Agendamento
from unidades.models import UnidadeSaude


class TipoExameForm(forms.ModelForm):
    class Meta:
        model = TipoExame
        fields = ["nome", "descricao"]

        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Hemograma completo"
            }),
            "descricao": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Descrição do tipo de exame"
            }),
        }
class AgendamentoForm(forms.Form):
    cpf = forms.CharField(
        label="CPF do cidadão",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "000.000.000-00",
            "readonly": "readonly"
        })
    )

    nome = forms.CharField(
        label="Nome",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "readonly": "readonly"
        })
    )

    telefone = forms.CharField(
        label="Telefone",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "readonly": "readonly"
        })
    )

    tipo_exame = forms.ModelChoiceField(
        label="Tipo de exame",
        queryset=TipoExame.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    unidade = forms.ModelChoiceField(
        label="Unidade de saúde",
        queryset=UnidadeSaude.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    data = forms.DateField(
        label="Data do exame",
        widget=forms.DateInput(attrs={
            "class": "form-control",
            "type": "date"
        })
    )

    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3
        })
    )