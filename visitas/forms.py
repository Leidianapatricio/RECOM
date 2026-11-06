
import re
import unicodedata
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from cartao_programa.models import (
    EfetivoViatura,
    ViaturaPlantao,
)

from .models import RondaVisita


# =========================================================
# CORRESPONDÊNCIA ENTRE MISSÃO E TIPO DE VISITA
# =========================================================

TIPO_VISITA_POR_MISSAO = {
    "ENTRADA": "ENTRADA",
    "SAIDA": "SAIDA",
    "VISITA": "ROTINA",
    "RONDAS": "RONDAS",
    "RONDAS_PB": "RONDAS_PB",
    "PALESTRA": "PALESTRA",
    "FANTOCHE": "FANTOCHE",
    "EJA": "OUTRA",
    "OUTRA": "OUTRA",
}


# =========================================================
# NORMALIZAR NOME DA EQUIPE
# =========================================================

def normalizar_nome_equipe(nome):

    nome = unicodedata.normalize(
        "NFKD",
        nome or "",
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = nome.upper().strip()

    nome = re.sub(
        r"[^A-Z0-9]+",
        " ",
        nome,
    )

    return " ".join(nome.split())


# =========================================================
# IDENTIFICAR CÓDIGO DA EQUIPE
# =========================================================

def obter_codigo_equipe_viatura(viatura):

    tipo_servico = getattr(
        viatura,
        "tipo_servico",
        None,
    )

    if tipo_servico is None:
        tipo_servico = getattr(
            viatura.plantao,
            "tipo_servico",
            None,
        )

    if viatura.equipe_id is None:

        if tipo_servico == "EXTRAORDINARIO":
            return "EXTRA"

        raise ValidationError(
            "A viatura não possui equipe responsável "
            "cadastrada."
        )

    nome = normalizar_nome_equipe(
        viatura.equipe.nome
    )

    if nome in {"A", "B", "C", "D", "E", "F"}:
        return nome

    correspondencia = re.fullmatch(
        r"EQUIPE ([A-F])",
        nome,
    )

    if correspondencia:
        return correspondencia.group(1)

    correspondencia = re.fullmatch(
        r"EQUIPE [A-Z]+ ([A-F])",
        nome,
    )

    if correspondencia:
        return correspondencia.group(1)

    nomes_equipes = {
        "ALPHA": "A",
        "ALFA": "A",
        "BRAVO": "B",
        "CHARLIE": "C",
        "DELTA": "D",
        "ECHO": "E",
        "FOXTROT": "F",
    }

    nome_sem_prefixo = nome.removeprefix(
        "EQUIPE "
    ).strip()

    if nome_sem_prefixo in nomes_equipes:
        return nomes_equipes[nome_sem_prefixo]

    if nome in {
        "EXTRA",
        "EXTRAORDINARIA",
        "EQUIPE EXTRA",
        "EQUIPE EXTRAORDINARIA",
    }:
        return "EXTRA"

    if tipo_servico == "EXTRAORDINARIO":
        return "EXTRA"

    raise ValidationError(
        "Não foi possível identificar o código "
        f"da equipe '{viatura.equipe.nome}'."
    )


def obter_codigo_equipe(missao):

    return obter_codigo_equipe_viatura(
        missao.viatura
    )


# =========================================================
# DADOS AUTOMÁTICOS DA MISSÃO
# =========================================================

def dados_da_missao(missao):

    if not missao.escola_id:
        raise ValidationError(
            "Esta missão não possui escola vinculada."
        )

    codigo_equipe = obter_codigo_equipe(
        missao
    )

    tipo_visita = TIPO_VISITA_POR_MISSAO.get(
        missao.tipo_missao
    )

    if tipo_visita is None:
        raise ValidationError(
            "O tipo desta missão não possui "
            "correspondência com os tipos de visita."
        )

    return {
        "escola": missao.escola,
        "viatura": missao.viatura,
        "equipe": codigo_equipe,
        "data_visita": missao.cartao.plantao.data,
        "tipo_visita": tipo_visita,
    }


# =========================================================
# FORMULÁRIO DE VISITAS
# =========================================================

class RondaVisitaForm(forms.ModelForm):

    class Meta:

        model = RondaVisita

        fields = [
            "escola",
            "data_visita",
            "viatura",
            "equipe",
            "horario",
            "tipo_visita",
            "situacao",
            "relato",
            "orientacoes",
        ]

        labels = {
            "escola": "Escola",
            "data_visita": "Data da visita",
            "viatura": "Viatura do plantão",
            "equipe": "Equipe responsável",
            "horario": "Horário",
            "tipo_visita": "Tipo de visita",
            "situacao": "Situação encontrada",
            "relato": "Relato da visita",
            "orientacoes": "Orientações / providências",
        }

        widgets = {

            "escola": forms.Select(
                attrs={
                    "class": "form-select select-escola",
                    "id": "id_escola",
                    "data-placeholder": (
                        "Digite o nome da escola..."
                    ),
                }
            ),

            "data_visita": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "viatura": forms.Select(
                attrs={
                    "class": "form-select",
                    "id": "id_viatura",
                }
            ),

            "equipe": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "horario": forms.TimeInput(
                format="%H:%M",
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
                        "Descreva o que foi observado "
                        "ou realizado durante a visita."
                    ),
                }
            ),

            "orientacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Informe as orientações ou "
                        "providências adotadas."
                    ),
                }
            ),
        }

    # =====================================================
    # INICIALIZAÇÃO
    # =====================================================

    def __init__(
        self,
        *args,
        missao=None,
        usuario_logado=None,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.missao = missao
        self.usuario_logado = usuario_logado

        # ==============================================
        # ESCOLAS ATIVAS
        # ==============================================

        escolas = (
            self.fields["escola"]
            .queryset
            .filter(ativa=True)
        )

        if (
            self.instance.pk
            and self.instance.escola_id
        ):

            escola_atual = (
                self.fields["escola"]
                .queryset
                .filter(pk=self.instance.escola_id)
            )

            escolas = escolas | escola_atual

        self.fields["escola"].queryset = (
            escolas.distinct().order_by("nome")
        )

        self.fields["escola"].empty_label = (
            "Digite ou selecione uma escola"
        )

        # ==============================================
        # CAMPOS OBRIGATÓRIOS
        # ==============================================

        for campo in (
            "escola", "data_visita", "equipe", "horario",
            "tipo_visita", "situacao",
        ):
            self.fields[campo].required = True

        # A viatura só é obrigatória quando a visita
        # pertence a uma missão do Cartão Programa.
        self.fields["viatura"].required = missao is not None

        if missao is not None:
            # VISITA PROGRAMADA: preserva os dados da missão.
            dados = dados_da_missao(missao)
            self.fields["escola"].queryset = (
                self.fields["escola"].queryset.model.objects.filter(
                    pk=missao.escola_id
                )
            )
            self.fields["viatura"].queryset = (
                ViaturaPlantao.objects.filter(pk=missao.viatura_id)
            )
            for campo, valor in dados.items():
                self.fields[campo].initial = valor
                self.fields[campo].disabled = True
            self.fields["escola"].help_text = (
                "Escola definida pela missão do Cartão Programa."
            )
            self.fields["viatura"].help_text = (
                "Viatura definida automaticamente pela missão."
            )
        else:
            # VISITAS LEGADAS E AVULSAS: não possuem viatura.
            # A equipe é informada diretamente, sem depender de escala.
            self.fields["viatura"].queryset = ViaturaPlantao.objects.none()
            self.fields["viatura"].widget = forms.HiddenInput()
            self.fields["viatura"].required = False
            self.fields["equipe"].disabled = False
            self.fields["equipe"].required = True
            self.fields["equipe"].help_text = (
                "Selecione a equipe responsável pela visita."
            )

    # =====================================================
    # VALIDAÇÃO
    # =====================================================

    def clean(self):

        cleaned_data = super().clean()

        # ==============================================
        # VISITA PROGRAMADA
        # ==============================================

        if self.missao is not None:

            dados = dados_da_missao(
                self.missao
            )

            for campo, valor in dados.items():

                cleaned_data[campo] = valor

            return cleaned_data

        # Visitas sem missão (legadas e avulsas) não podem
        # receber vínculo com viatura, mesmo se um valor
        # for enviado manualmente na requisição.
        cleaned_data["viatura"] = None
        return cleaned_data
