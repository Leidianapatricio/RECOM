
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

        campos_obrigatorios = [
            "escola",
            "data_visita",
            "viatura",
            "equipe",
            "horario",
            "tipo_visita",
            "situacao",
        ]

        for campo in campos_obrigatorios:
            self.fields[campo].required = True

        # ==============================================
        # VISITA PROGRAMADA
        # ==============================================

        if missao is not None:

            dados = dados_da_missao(missao)

            self.fields["escola"].queryset = (
                self.fields["escola"]
                .queryset.model.objects.filter(
                    pk=missao.escola_id
                )
            )

            self.fields["viatura"].queryset = (
                ViaturaPlantao.objects.filter(
                    pk=missao.viatura_id
                )
            )

            for campo, valor in dados.items():

                self.fields[campo].initial = valor
                self.fields[campo].disabled = True

            self.fields["escola"].help_text = (
                "Escola definida pela missão "
                "do Cartão Programa."
            )

            self.fields["viatura"].help_text = (
                "Viatura definida automaticamente "
                "pela missão."
            )

        # ==============================================
        # VISITA AVULSA
        # ==============================================

        else:

            self.fields["equipe"].disabled = True

            self.fields["equipe"].help_text = (
                "A equipe será identificada "
                "automaticamente pela viatura."
            )

            self.fields["viatura"].help_text = (
                "Selecione a viatura correspondente "
                "à data da visita."
            )

            data_selecionada = None

            if self.is_bound:

                data_informada = self.data.get(
                    self.add_prefix("data_visita"),
                    "",
                )

                try:
                    data_selecionada = (
                        date.fromisoformat(data_informada)
                    )
                except (ValueError, TypeError):
                    pass

            elif self.initial.get("data_visita"):

                data_inicial = self.initial[
                    "data_visita"
                ]

                if isinstance(data_inicial, date):
                    data_selecionada = data_inicial

                elif isinstance(data_inicial, str):
                    try:
                        data_selecionada = (
                            date.fromisoformat(
                                data_inicial
                            )
                        )
                    except ValueError:
                        pass

            elif self.instance.pk:

                data_selecionada = (
                    self.instance.data_visita
                )

            # ==========================================
            # VIATURAS AUTORIZADAS
            # ==========================================

            viaturas = (
                ViaturaPlantao.objects
                .select_related(
                    "plantao",
                    "equipe",
                )
                .none()
            )

            usuario = usuario_logado

            if (
                usuario is not None
                and usuario.is_authenticated
                and usuario.is_active
            ):

                usuario_recom = (
                    getattr(
                        usuario,
                        "usuario",
                        None,
                    )
                )

                if usuario.is_superuser or (
                    usuario_recom is not None
                    and usuario_recom.ativo
                    and usuario_recom.perfil in (
                        "ADMIN",
                        "COORDENADOR",
                    )
                ):

                    viaturas = (
                        ViaturaPlantao.objects
                        .select_related(
                            "plantao",
                            "equipe",
                        )
                        .all()
                    )

                elif (
                    usuario_recom is not None
                    and usuario_recom.ativo
                    and usuario_recom.perfil == "GCM"
                ):

                    # Mantém as funções autorizadas
                    # a cadastrar visitas.
                    ids_viaturas = (
                        EfetivoViatura.objects.filter(
                            gcm=usuario_recom,
                            funcao__in=(
                                "C",
                                "P1",
                                "P2",
                            ),
                        ).values_list(
                            "viatura_id",
                            flat=True,
                        )
                    )

                    viaturas = (
                        ViaturaPlantao.objects
                        .select_related(
                            "plantao",
                            "equipe",
                        )
                        .filter(
                            pk__in=ids_viaturas
                        )
                    )

            if data_selecionada is not None:

                viaturas = viaturas.filter(
                    plantao__data=data_selecionada
                )

            else:

                viaturas = viaturas.none()

            # Preserva a viatura da visita em edição
            # apenas se ainda estiver autorizada.
            self.fields["viatura"].queryset = (
                viaturas.distinct().order_by(
                    "identificacao",
                    "pk",
                )
            )

            self.fields["viatura"].empty_label = (
                "Selecione a viatura"
            )

            # ==========================================
            # EQUIPE AUTOMÁTICA
            # ==========================================

            viatura_selecionada = None

            if self.is_bound:

                viatura_id = self.data.get(
                    self.add_prefix("viatura")
                )

                if viatura_id:

                    viatura_selecionada = (
                        self.fields["viatura"]
                        .queryset
                        .filter(pk=viatura_id)
                        .first()
                    )

            elif (
                self.instance.pk
                and self.instance.viatura_id
            ):

                viatura_selecionada = (
                    self.fields["viatura"]
                    .queryset
                    .filter(
                        pk=self.instance.viatura_id
                    )
                    .first()
                )

            if viatura_selecionada:

                try:

                    codigo_equipe = (
                        obter_codigo_equipe_viatura(
                            viatura_selecionada
                        )
                    )

                    self.fields["equipe"].initial = (
                        codigo_equipe
                    )

                except ValidationError:
                    pass

            # O campo desabilitado não precisa
            # ser enviado pelo navegador.
            self.fields["equipe"].required = False

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

        # ==============================================
        # VISITA AVULSA
        # ==============================================

        viatura = cleaned_data.get(
            "viatura"
        )

        data_visita = cleaned_data.get(
            "data_visita"
        )

        if viatura is None:
            return cleaned_data

        if (
            data_visita is not None
            and viatura.plantao.data != data_visita
        ):

            self.add_error(
                "viatura",
                "A viatura selecionada não pertence "
                "à data informada.",
            )

            return cleaned_data

        try:

            codigo_equipe = (
                obter_codigo_equipe_viatura(
                    viatura
                )
            )

            cleaned_data["equipe"] = (
                codigo_equipe
            )

        except ValidationError as erro:

            self.add_error(
                "viatura",
                erro,
            )

        return cleaned_data
