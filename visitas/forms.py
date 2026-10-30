
import re
import unicodedata

from django import forms
from django.core.exceptions import ValidationError

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
    """
    Normaliza o nome cadastrado da equipe.

    Exemplos:
        Equipe A     -> EQUIPE A
        Equipe - A   -> EQUIPE A
        Equipe "A"   -> EQUIPE A
        equipe_a     -> EQUIPE A
    """

    nome = unicodedata.normalize("NFKD", nome or "")

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = nome.upper().strip()

    nome = re.sub(r"[^A-Z0-9]+", " ", nome)

    return " ".join(nome.split())


# =========================================================
# IDENTIFICAR EQUIPE DA VIATURA
# =========================================================


def obter_codigo_equipe(missao):
    """
    Identifica o código da equipe responsável pela missão.

    Exemplos:
        Equipe Alpha - A   -> A
        Equipe Bravo - B   -> B
        Equipe Charlie - C -> C
        Equipe Delta - D   -> D
        Equipe Echo - E    -> E
        Equipe Foxtrot - F -> F
        Equipe A           -> A
        A                  -> A
    """

    viatura = missao.viatura

    # Serviço extraordinário sem equipe fixa.
    if viatura.equipe_id is None:

        if viatura.tipo_servico == "EXTRAORDINARIO":
            return "EXTRA"

        raise ValidationError(
            "A viatura não possui equipe responsável cadastrada."
        )

    nome = normalizar_nome_equipe(
        viatura.equipe.nome
    )

    # Equipes identificadas diretamente pela letra.
    if nome in {"A", "B", "C", "D", "E", "F"}:
        return nome

    # Equipes cadastradas como "Equipe A".
    correspondencia = re.fullmatch(
        r"EQUIPE ([A-F])",
        nome
    )

    if correspondencia:
        return correspondencia.group(1)

    # Equipes cadastradas como:
    # "Equipe Echo - E"
    # "Equipe Alpha - A"
    # etc.
    correspondencia = re.fullmatch(
        r"EQUIPE [A-Z]+ ([A-F])",
        nome
    )

    if correspondencia:
        return correspondencia.group(1)

    # Reconhecimento dos nomes fonéticos.
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

    # Equipes extraordinárias.
    if nome in {
        "EXTRA",
        "EXTRAORDINARIA",
        "EQUIPE EXTRA",
        "EQUIPE EXTRAORDINARIA",
    }:
        return "EXTRA"

    if viatura.tipo_servico == "EXTRAORDINARIO":
        return "EXTRA"

    raise ValidationError(
        "Não foi possível identificar o código "
        f"da equipe '{viatura.equipe.nome}'."
    )



# =========================================================
# DADOS AUTOMÁTICOS DA MISSÃO
# =========================================================

def dados_da_missao(missao):
    """
    Recupera os dados definidos pelo coordenador
    no Cartão Programa.

    Esses valores não poderão ser modificados
    pelo GCM durante o registro da visita.
    """

    if not missao.escola:
        raise ValidationError(
            "Esta missão não possui escola vinculada."
        )

    codigo_equipe = obter_codigo_equipe(missao)

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

            # ESCOLA
            "escola": forms.Select(
                attrs={
                    "class": "form-select select-escola",
                    "id": "id_escola",
                    "data-placeholder": (
                        "Digite o nome da escola..."
                    ),
                }
            ),

            # EQUIPE
            "equipe": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # DATA
            "data_visita": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            # HORÁRIO
            "horario": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "time",
                }
            ),

            # TIPO DE VISITA
            "tipo_visita": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # SITUAÇÃO
            "situacao": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # RELATO
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

            # ORIENTAÇÕES
            "orientacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Informe as orientações ou "
                        "providências adotadas, "
                        "quando houver."
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
        **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.missao = missao

        # ==============================================
        # ESCOLAS ATIVAS
        # ==============================================

        escolas = (
            self.fields["escola"]
            .queryset
            .filter(ativa=True)
        )

        # Preservar escola inativa durante a edição.
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

        campos_obrigatorios = [
            "escola",
            "equipe",
            "data_visita",
            "horario",
            "tipo_visita",
            "situacao",
        ]

        for campo in campos_obrigatorios:
            self.fields[campo].required = True

        # ==============================================
        # VISITA VINCULADA AO CARTÃO PROGRAMA
        # ==============================================

        if missao is not None:

            dados = dados_da_missao(missao)

            # Permitir a escola da missão no queryset,
            # mesmo que tenha sido desativada.
            self.fields["escola"].queryset = (
                self.fields["escola"]
                .queryset.model.objects.filter(
                    pk=missao.escola_id
                )
            )

            # Preenchimento automático e bloqueio.
            for campo, valor in dados.items():

                self.fields[campo].initial = valor

                # O Django ignora alterações enviadas
                # pelo navegador para campos disabled.
                self.fields[campo].disabled = True

            self.fields["escola"].help_text = (
                "Escola definida automaticamente "
                "pela missão do Cartão Programa."
            )

        # ==============================================
        # VISITA AVULSA
        # ==============================================

        else:

            self.fields["escola"].disabled = False
            self.fields["equipe"].disabled = False
            self.fields["data_visita"].disabled = False
            self.fields["tipo_visita"].disabled = False

    # =====================================================
    # VALIDAÇÃO DOS DADOS DA MISSÃO
    # =====================================================

    def clean(self):

        cleaned_data = super().clean()

        if self.missao is not None:

            dados = dados_da_missao(
                self.missao
            )

            # Reforça os dados originais da missão.
            for campo, valor in dados.items():

                if campo == "escola":
                    cleaned_data[campo] = (
                        self.missao.escola
                    )

                else:
                    cleaned_data[campo] = valor

        return cleaned_data
