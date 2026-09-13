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

            # =================================================
            # ESCOLA
            # =================================================
            "escola": forms.Select(
                attrs={
                    "class": "form-select select-escola",
                    "id": "id_escola",
                    "data-placeholder": "Digite o nome da escola...",
                }
            ),

            # =================================================
            # EQUIPE
            # =================================================
            "equipe": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # =================================================
            # DATA
            # =================================================
            "data_visita": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            # =================================================
            # HORÁRIO
            # =================================================
            "horario": forms.TimeInput(
                attrs={
                    "class": "form-control",
                    "type": "time",
                }
            ),

            # =================================================
            # TIPO DE VISITA
            # =================================================
            "tipo_visita": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # =================================================
            # SITUAÇÃO
            # =================================================
            "situacao": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # =================================================
            # RELATO
            # =================================================
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

            # =================================================
            # ORIENTAÇÕES / PROVIDÊNCIAS
            # =================================================
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

        # =====================================================
        # ESCOLAS
        # =====================================================
        #
        # Exibe somente escolas ativas.
        #
        # A ordenação é feita alfabeticamente pelo nome,
        # independentemente do polo.
        #
        # =====================================================

        self.fields["escola"].queryset = (
            self.fields["escola"]
            .queryset
            .filter(
                ativa=True
            )
            .order_by(
                "nome"
            )
        )

        self.fields["escola"].empty_label = (
            "Digite ou selecione uma escola"
        )

        # =====================================================
        # CAMPOS OBRIGATÓRIOS
        # =====================================================

        self.fields["escola"].required = True
        self.fields["equipe"].required = True
        self.fields["data_visita"].required = True
        self.fields["horario"].required = True
        self.fields["tipo_visita"].required = True
        self.fields["situacao"].required = True