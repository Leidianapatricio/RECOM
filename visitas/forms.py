from django import forms

from .models import RondaVisita


class RondaVisitaForm(forms.ModelForm):

    class Meta:
        model = RondaVisita

        fields = [
            "escola",
            "equipe",
            "data_visita",
            "horario",
            "tipo_visita",
            "situacao",
            "relato",
            "orientacoes",
        ]

        labels = {
            "escola": "Escola",
            "equipe": "Equipe responsável",
            "data_visita": "Data da visita",
            "horario": "Horário",
            "tipo_visita": "Tipo de visita",
            "situacao": "Situação encontrada",
            "relato": "Relato da visita",
            "orientacoes": "Orientações / providências",
        }

        widgets = {
            "escola": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "equipe": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "data_visita": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "horario": forms.TimeInput(
                attrs={
                    "class": "form-control",
                    "type": "time",
                }
            ),

            "tipo_visita": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "situacao": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "relato": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Descreva o que foi observado ou realizado "
                        "durante a visita."
                    ),
                }
            ),

            "orientacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Informe as orientações ou providências adotadas, "
                        "quando houver."
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Exibe somente escolas ativas no cadastro da visita
        self.fields["escola"].queryset = (
            self.fields["escola"]
            .queryset
            .filter(ativa=True)
            .order_by("polo", "nome")
        )

        # Texto inicial dos campos de seleção
        self.fields["escola"].empty_label = "Selecione uma escola"

        # Define os campos obrigatórios
        self.fields["escola"].required = True
        self.fields["equipe"].required = True
        self.fields["data_visita"].required = True
        self.fields["horario"].required = True
        self.fields["tipo_visita"].required = True
        self.fields["situacao"].required = True