from django import forms

from .models import Escola


class EscolaForm(forms.ModelForm):

    SIM_NAO_CHOICES = [
        ("True", "Sim"),
        ("False", "Não"),
    ]

    monitoramento = forms.TypedChoiceField(
        label="Possui monitoramento",
        choices=SIM_NAO_CHOICES,
        coerce=lambda value: value == "True",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    botao_panico = forms.TypedChoiceField(
        label="Possui botão do pânico",
        choices=SIM_NAO_CHOICES,
        coerce=lambda value: value == "True",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    class Meta:
        model = Escola

        fields = [
            "nome",
            "polo",
            "endereco",
            "gestor",
            "telefone",
            "monitoramento",
            "botao_panico",
            "quantidade_alunos",
            "quantidade_alunos_pcd",
            "modalidade",
            "observacoes",
        ]

        widgets = {
            "nome": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome da escola",
                }
            ),

            "polo": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "endereco": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Endereço da escola",
                }
            ),

            "gestor": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome do gestor",
                }
            ),

            "telefone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Telefone",
                }
            ),

            "quantidade_alunos": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),

            "quantidade_alunos_pcd": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),

            "modalidade": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex.: Ensino Fundamental I e II",
                }
            ),

            "observacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Observações sobre a escola",
                }
            ),
        }

        labels = {
            "nome": "Nome da escola",
            "polo": "Polo",
            "endereco": "Endereço",
            "gestor": "Gestor",
            "telefone": "Telefone",
            "monitoramento": "Possui monitoramento",
            "botao_panico": "Possui botão do pânico",
            "quantidade_alunos": "Quantidade de alunos",
            "quantidade_alunos_pcd": "Quantidade de alunos PCD",
            "modalidade": "Modalidade",
            "observacoes": "Observações",
        }

    def clean_nome(self):
        nome = self.cleaned_data.get("nome")

        if not nome:
            return nome

        nome = nome.strip()

        escolas = Escola.objects.filter(
            nome__iexact=nome
        )

        if self.instance.pk:
            escolas = escolas.exclude(
                pk=self.instance.pk
            )

        if escolas.exists():
            raise forms.ValidationError(
                "Já existe uma escola cadastrada com este nome."
            )

        return nome

    def clean(self):
        cleaned_data = super().clean()

        quantidade_alunos = cleaned_data.get(
            "quantidade_alunos"
        )

        quantidade_alunos_pcd = cleaned_data.get(
            "quantidade_alunos_pcd"
        )

        if (
            quantidade_alunos is not None
            and quantidade_alunos_pcd is not None
            and quantidade_alunos_pcd > quantidade_alunos
        ):
            self.add_error(
                "quantidade_alunos_pcd",
                (
                    "A quantidade de alunos PCD não pode ser "
                    "maior que a quantidade total de alunos."
                ),
            )

        return cleaned_data