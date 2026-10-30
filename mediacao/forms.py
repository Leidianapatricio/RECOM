
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from escolas.models import Escola

from .models import (
    PlanejamentoMediacao,
    AtividadeMediacao,
)


# ============================================================
# FORMULÁRIO DE PLANEJAMENTO DE MEDIAÇÃO
# ============================================================

class PlanejamentoMediacaoForm(forms.ModelForm):

    class Meta:
        model = PlanejamentoMediacao

        fields = [
            "data",
            "escola",
            "mediacoes_previstas",
        ]

        labels = {
            "data": "Data da mediação",
            "escola": "Escola",
            "mediacoes_previstas": (
                "Mediações previstas / Observações"
            ),
        }

        widgets = {
            "data": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                },
                format="%Y-%m-%d",
            ),

            "escola": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "mediacoes_previstas": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Descreva as mediações, atividades, "
                        "temas e estratégias previstas "
                        "para a escola..."
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["escola"].queryset = (
            Escola.objects
            .filter(ativa=True)
            .order_by("polo", "nome")
        )

        self.fields["escola"].empty_label = (
            "Selecione uma escola"
        )

        self.fields["data"].input_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

        if self.instance.pk and self.instance.data:
            self.initial["data"] = (
                self.instance.data.strftime("%Y-%m-%d")
            )

    def clean_mediacoes_previstas(self):
        texto = self.cleaned_data.get(
            "mediacoes_previstas",
            ""
        ).strip()

        if not texto:
            raise ValidationError(
                "Descreva as mediações previstas."
            )

        return texto


# ============================================================
# FORMULÁRIO DE REGISTRO DE ATIVIDADE
# PROJETO CULTURA DE PAZ
# ============================================================

class AtividadeMediacaoForm(forms.ModelForm):

    class Meta:
        model = AtividadeMediacao

        fields = [
            # Planejamento vinculado
            "planejamento",

            # Identificação
            "escola",
            "data",
            "turno",
            "diretor",
            "coordenador",
            "inspetor_1",
            "inspetor_2",
            "turma",

            # Público atendido
            "alunos",
            "profissionais",
            "familiares",
            "outros_publico",

            # Quantidade por sexo
            "quantidade_homens",
            "quantidade_mulheres",

            # Necessidades especiais
            "necessidade_nt",
            "necessidade_aut",
            "necessidade_df_f",
            "necessidade_df_i",
            "necessidade_df_v",
            "necessidade_outros",

            # Descrição da atividade
            "mediadores_presentes",
            "tema_dinamica",
            "fatos_marcantes",
            "observacoes",
        ]

        labels = {
            "planejamento": "Planejamento vinculado",
            "escola": "Escola",
            "data": "Data da atividade",
            "turno": "Turno",
            "diretor": "Diretor(a)",
            "coordenador": "Coordenador(a)",
            "inspetor_1": "Inspetor(a) 1",
            "inspetor_2": "Inspetor(a) 2",
            "turma": "Turma",

            "alunos": "Alunos",
            "profissionais": "Profissionais",
            "familiares": "Familiares",
            "outros_publico": "Outros",

            "quantidade_homens": "Homens (H)",
            "quantidade_mulheres": "Mulheres (M)",

            "necessidade_nt": "Nt",
            "necessidade_aut": "Aut",
            "necessidade_df_f": "Df.F",
            "necessidade_df_i": "Df.I",
            "necessidade_df_v": "Df.V",
            "necessidade_outros": "Out",

            "mediadores_presentes": "Mediadores presentes",
            "tema_dinamica": "Tema e dinâmica",
            "fatos_marcantes": "Fatos marcantes",
            "observacoes": "Observações",
        }

        widgets = {
            "planejamento": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "escola": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "data": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                },
                format="%Y-%m-%d",
            ),

            "turno": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "diretor": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome do(a) diretor(a)",
                }
            ),

            "coordenador": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome do(a) coordenador(a)",
                }
            ),

            "inspetor_1": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome do(a) inspetor(a)",
                }
            ),

            "inspetor_2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nome do(a) segundo(a) inspetor(a)",
                }
            ),

            "turma": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex.: 6º ano A",
                }
            ),

            "mediadores_presentes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Informe os nomes dos mediadores "
                        "presentes na atividade."
                    ),
                }
            ),

            "tema_dinamica": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Descreva o tema abordado e "
                        "a dinâmica desenvolvida."
                    ),
                }
            ),

            "fatos_marcantes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Registre os fatos marcantes "
                        "observados durante a atividade."
                    ),
                }
            ),

            "observacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Informações complementares "
                        "sobre a atividade."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        mediador=None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        # ==========================================
        # ESCOLAS ATIVAS
        # ==========================================

        self.fields["escola"].queryset = (
            Escola.objects
            .filter(ativa=True)
            .order_by("polo", "nome")
        )

        self.fields["escola"].empty_label = (
            "Selecione uma escola"
        )

        # ==========================================
        # PLANEJAMENTOS DO MEDIADOR
        # ==========================================

        planejamentos = (
            PlanejamentoMediacao.objects
            .select_related("escola")
            .order_by("-data", "escola__nome")
        )

        if mediador is not None:
            planejamentos = planejamentos.filter(
                mediador=mediador
            )

        self.fields["planejamento"].queryset = (
            planejamentos
        )

        self.fields["planejamento"].required = False

        self.fields["planejamento"].empty_label = (
            "Atividade sem planejamento prévio"
        )

        # ==========================================
        # DATA
        # ==========================================

        self.fields["data"].input_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

        if self.instance.pk and self.instance.data:
            self.initial["data"] = (
                self.instance.data.strftime("%Y-%m-%d")
            )

        elif not self.is_bound:
            self.initial.setdefault(
                "data",
                timezone.localdate().strftime("%Y-%m-%d")
            )

        # ==========================================
        # CAMPOS NUMÉRICOS
        # ==========================================

        campos_numericos = [
            "alunos",
            "profissionais",
            "familiares",
            "outros_publico",
            "quantidade_homens",
            "quantidade_mulheres",
            "necessidade_nt",
            "necessidade_aut",
            "necessidade_df_f",
            "necessidade_df_i",
            "necessidade_df_v",
            "necessidade_outros",
        ]

        for campo in campos_numericos:
            self.fields[campo].widget = (
                forms.NumberInput(
                    attrs={
                        "class": "form-control",
                        "min": 0,
                        "step": 1,
                    }
                )
            )

            self.fields[campo].required = False

            if not self.is_bound:
                self.initial.setdefault(campo, 0)

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    def clean(self):
        cleaned_data = super().clean()

        planejamento = cleaned_data.get(
            "planejamento"
        )

        escola = cleaned_data.get(
            "escola"
        )

        # ==========================================
        # VALIDAR ESCOLA DO PLANEJAMENTO
        # ==========================================

        if planejamento and escola:

            if planejamento.escola_id != escola.pk:

                self.add_error(
                    "escola",
                    (
                        "A escola selecionada deve ser "
                        "a mesma do planejamento vinculado."
                    )
                )

        # ==========================================
        # VALIDAR CAMPOS NUMÉRICOS
        # ==========================================

        campos_numericos = [
            "alunos",
            "profissionais",
            "familiares",
            "outros_publico",
            "quantidade_homens",
            "quantidade_mulheres",
            "necessidade_nt",
            "necessidade_aut",
            "necessidade_df_f",
            "necessidade_df_i",
            "necessidade_df_v",
            "necessidade_outros",
        ]

        for campo in campos_numericos:

            valor = cleaned_data.get(campo)

            if valor is None:
                cleaned_data[campo] = 0

        # ==========================================
        # VALIDAR QUANTITATIVOS
        # ==========================================

        total_publico = sum(
            cleaned_data.get(campo, 0)
            for campo in [
                "alunos",
                "profissionais",
                "familiares",
                "outros_publico",
            ]
        )

        total_homens_mulheres = (
            cleaned_data.get("quantidade_homens", 0)
            + cleaned_data.get("quantidade_mulheres", 0)
        )

        if total_homens_mulheres > total_publico:

            self.add_error(
                "quantidade_homens",
                (
                    "A soma de homens e mulheres "
                    "não pode ser maior que o total "
                    "do público atendido."
                )
            )

        return cleaned_data
