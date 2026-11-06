
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from cartao_programa.models import (
    EfetivoViatura,
    ViaturaPlantao,
)
from usuarios.models import Usuario

from .models import (
    Ocorrencia,
    PessoaEnvolvida,
    VeiculoEnvolvido,
)


# ==========================================================
# FORMULÁRIO BASE - BOOTSTRAP
# ==========================================================

class BootstrapModelForm(forms.ModelForm):
    """
    Aplica automaticamente as classes do Bootstrap
    aos campos dos formulários.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for nome, campo in self.fields.items():
            widget = campo.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"

            elif isinstance(
                widget,
                (forms.RadioSelect, forms.CheckboxSelectMultiple)
            ):
                widget.attrs["class"] = "form-check-input"

            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"

            else:
                widget.attrs["class"] = "form-control"

            if campo.required:
                widget.attrs["required"] = "required"


# ==========================================================
# FORMULÁRIO PRINCIPAL DA OCORRÊNCIA
# ==========================================================

class OcorrenciaForm(BootstrapModelForm):
    """
    Formulário para cadastrar e editar ocorrências.

    A seleção de viaturas depende do usuário:

    - ADMIN e COORDENADOR: todas as viaturas.
    - GCM C e P1: viaturas em que estiver escalado.
    - GCM M e P2: nenhuma viatura autorizada.

    As permissões de acesso às views também devem
    ser verificadas no servidor.
    """

    SIM_NAO = (
        ("sim", "Sim"),
        ("nao", "Não"),
    )

    acionamento_cicc = forms.TypedChoiceField(
        label="Foi acionamento do CICC?",
        choices=SIM_NAO,
        coerce=lambda valor: valor == "sim",
        widget=forms.RadioSelect,
        required=True,
    )

    possui_vitima = forms.TypedChoiceField(
        label="Houve vítima?",
        choices=SIM_NAO,
        coerce=lambda valor: valor == "sim",
        widget=forms.RadioSelect,
        required=True,
    )

    class Meta:
        model = Ocorrencia

        fields = [
            "viatura",
            "data",
            "horario",
            "local",
            "bairro",
            "acionamento_cicc",
            "natureza_atuacao",
            "equipe_apoiada",
            "categoria",
            "tipo_ocorrencia",
            "possui_vitima",
            "relato",
            "providencias",
            "orgaos_acionados",
        ]

        labels = {
            "viatura": "Viatura responsável",
            "data": "Data da ocorrência",
            "horario": "Horário",
            "local": "Local da ocorrência",
            "bairro": "Bairro",
            "natureza_atuacao": "Natureza da atuação",
            "equipe_apoiada": "Equipe apoiada",
            "categoria": "Categoria da ocorrência",
            "tipo_ocorrencia": "Tipo da ocorrência",
            "relato": "Relato da ocorrência",
            "providencias": "Providências adotadas",
            "orgaos_acionados": "Órgãos acionados",
        }

        widgets = {
            "viatura": forms.Select(),

            "data": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),

            "horario": forms.TimeInput(
                attrs={"type": "time"},
                format="%H:%M",
            ),

            "local": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Informe o endereço ou local da ocorrência"
                    )
                }
            ),

            "bairro": forms.TextInput(
                attrs={
                    "placeholder": "Informe o bairro"
                }
            ),

            "natureza_atuacao": forms.RadioSelect,

            "equipe_apoiada": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ex.: Tático 1, Preventivo, ROCAM, PRF"
                    )
                }
            ),

            "categoria": forms.RadioSelect,

            "tipo_ocorrencia": forms.Select,

            "relato": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Descreva os fatos e as circunstâncias "
                        "da ocorrência."
                    ),
                }
            ),

            "providencias": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Descreva as providências adotadas "
                        "pela equipe RECOM."
                    ),
                }
            ),

            "orgaos_acionados": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": (
                        "Ex.: SAMU, Bombeiros, PRF, "
                        "Polícia Militar."
                    ),
                }
            ),
        }

    # ======================================================
    # INICIALIZAÇÃO
    # ======================================================

    def __init__(self, *args, **kwargs):

        usuario_logado = kwargs.pop(
            "usuario_logado",
            None
        )

        super().__init__(*args, **kwargs)

        self.usuario_logado = usuario_logado

        # --------------------------------------------------
        # CONFIGURAÇÃO DOS CAMPOS
        # --------------------------------------------------

        self.fields["viatura"].required = True

        self.fields["viatura"].empty_label = (
            "Selecione a viatura responsável"
        )

        self.fields["equipe_apoiada"].required = False

        self.fields["tipo_ocorrencia"].choices = [
            ("", "Selecione o tipo de ocorrência"),
            *Ocorrencia.TipoOcorrencia.choices,
        ]

        self.fields["tipo_ocorrencia"].widget.attrs[
            "data-categoria"
        ] = "tipo-ocorrencia"

        # --------------------------------------------------
        # CAMPOS SIM / NÃO
        # --------------------------------------------------

        self.fields["acionamento_cicc"].initial = (
            "sim"
            if self.instance.pk
            and self.instance.acionamento_cicc
            else "nao"
        )

        self.fields["possui_vitima"].initial = (
            "sim"
            if self.instance.pk
            and self.instance.possui_vitima
            else "nao"
        )

        # --------------------------------------------------
        # VIATURAS AUTORIZADAS
        # --------------------------------------------------

        self.fields["viatura"].queryset = (
            self.obter_viaturas_autorizadas()
        )

        # --------------------------------------------------
        # FORMATAÇÃO DA DATA
        # --------------------------------------------------

        self.fields["data"].input_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

        # --------------------------------------------------
        # FORMATAÇÃO DO HORÁRIO
        # --------------------------------------------------

        self.fields["horario"].input_formats = [
            "%H:%M",
            "%H:%M:%S",
        ]

    # ======================================================
    # IDENTIFICAR VIATURAS AUTORIZADAS
    # ======================================================

    def obter_viaturas_autorizadas(self):
        """
        Retorna somente as viaturas que o usuário
        autenticado pode utilizar no formulário.
        """

        viaturas = ViaturaPlantao.objects.none()

        usuario_logado = self.usuario_logado

        if usuario_logado is None:
            return viaturas

        if not usuario_logado.is_active:
            return viaturas

        usuario_recom = Usuario.objects.filter(
            user=usuario_logado,
            ativo=True,
        ).first()

        # --------------------------------------------------
        # ADMINISTRADOR DO DJANGO
        # --------------------------------------------------

        if usuario_logado.is_superuser:

            viaturas = ViaturaPlantao.objects.all()

        # --------------------------------------------------
        # ADMIN E COORDENADOR
        # --------------------------------------------------

        elif (
            usuario_recom is not None
            and usuario_recom.perfil in [
                "ADMIN",
                "COORDENADOR",
            ]
        ):

            viaturas = ViaturaPlantao.objects.all()

        # --------------------------------------------------
        # GCM - COMANDANTE OU PATRULHEIRO 1
        # --------------------------------------------------

        elif (
            usuario_recom is not None
            and usuario_recom.perfil == "GCM"
        ):

            viaturas = ViaturaPlantao.objects.filter(
                efetivo__gcm=usuario_recom,
                efetivo__funcao__in=[
                    "C",
                    "P1",
                ],
            ).distinct()

        # --------------------------------------------------
        # ORDENAÇÃO
        # --------------------------------------------------

        return (
            viaturas
            .select_related(
                "plantao",
                "equipe",
            )
            .order_by(
                "-plantao__data",
                "identificacao",
            )
        )

    # ======================================================
    # VALIDAÇÕES DO FORMULÁRIO
    # ======================================================

    def clean(self):

        cleaned_data = super().clean()

        viatura = cleaned_data.get("viatura")
        data = cleaned_data.get("data")
        horario = cleaned_data.get("horario")

        natureza = cleaned_data.get(
            "natureza_atuacao"
        )

        equipe_apoiada = (
            cleaned_data.get("equipe_apoiada") or ""
        ).strip()

        categoria = cleaned_data.get("categoria")
        tipo = cleaned_data.get("tipo_ocorrencia")

        # --------------------------------------------------
        # VIATURA OBRIGATÓRIA
        # --------------------------------------------------

        if not viatura:

            if "viatura" not in self.errors:
                self.add_error(
                    "viatura",
                    "Selecione a viatura responsável."
                )

        # --------------------------------------------------
        # DATA DA OCORRÊNCIA
        # --------------------------------------------------

        if viatura and data:

            if viatura.plantao.data != data:

                self.add_error(
                    "data",
                    "A data da ocorrência deve corresponder "
                    "à data do plantão da viatura."
                )

        # --------------------------------------------------
        # DUPLICIDADE DE OCORRÊNCIA
        # --------------------------------------------------

        if viatura and data and horario:

            ocorrencia_existente = (
                Ocorrencia.objects.filter(
                    viatura=viatura,
                    data=data,
                    horario=horario,
                )
                .exclude(
                    pk=self.instance.pk
                )
                .first()
            )

            if ocorrencia_existente:

                self.add_error(
                    "horario",
                    "Já existe uma ocorrência registrada "
                    "para esta viatura, nesta data e horário. "
                    "Consulte o registro existente antes "
                    "de realizar outro cadastro."
                )

        # --------------------------------------------------
        # EQUIPE APOIADA
        # --------------------------------------------------

        if natureza == Ocorrencia.NaturezaAtuacao.APOIO:

            if not equipe_apoiada:

                self.add_error(
                    "equipe_apoiada",
                    "Informe qual equipe recebeu o apoio."
                )

        else:

            cleaned_data["equipe_apoiada"] = ""

        # --------------------------------------------------
        # CATEGORIA E TIPO DE OCORRÊNCIA
        # --------------------------------------------------

        tipos_por_categoria = {

            Ocorrencia.Categoria.TRANSITO: {
                Ocorrencia.TipoOcorrencia.SINISTRO,
            },

            Ocorrencia.Categoria.VIOLENCIA: {
                Ocorrencia.TipoOcorrencia.FURTO,
                Ocorrencia.TipoOcorrencia.ROUBO,
                Ocorrencia.TipoOcorrencia.AMEACA,
                Ocorrencia.TipoOcorrencia.AGRESSAO,
            },
        }

        if (
            categoria
            and tipo
            and tipo not in tipos_por_categoria.get(
                categoria,
                set()
            )
        ):

            self.add_error(
                "tipo_ocorrencia",
                "O tipo selecionado não pertence "
                "à categoria informada."
            )

        return cleaned_data


# ==========================================================
# FORMULÁRIO DE PESSOAS ENVOLVIDAS
# ==========================================================

class PessoaEnvolvidaForm(BootstrapModelForm):
    """
    Cadastro de vítimas, suspeitos, condutores,
    passageiros, testemunhas e outros envolvidos.
    """

    class Meta:
        model = PessoaEnvolvida

        fields = [
            "nome",
            "papel",
            "idade",
            "sexo",
            "documento",
            "observacoes",
        ]

        widgets = {

            "nome": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Nome da pessoa envolvida"
                    )
                }
            ),

            "papel": forms.Select,

            "idade": forms.NumberInput(
                attrs={
                    "min": 0,
                    "max": 120,
                }
            ),

            "sexo": forms.Select,

            "documento": forms.TextInput(
                attrs={
                    "placeholder": "CPF ou outro documento"
                }
            ),

            "observacoes": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": (
                        "Informações complementares"
                    ),
                }
            ),
        }

    def clean_idade(self):

        idade = self.cleaned_data.get("idade")

        if idade is not None and idade > 120:

            raise ValidationError(
                "Informe uma idade válida."
            )

        return idade


# ==========================================================
# FORMULÁRIO DE VEÍCULOS ENVOLVIDOS
# ==========================================================

class VeiculoEnvolvidoForm(BootstrapModelForm):
    """
    Cadastro dos veículos envolvidos na ocorrência.

    O condutor deve pertencer à mesma ocorrência.
    """

    class Meta:
        model = VeiculoEnvolvido

        fields = [
            "placa",
            "marca_modelo",
            "cor",
            "condutor",
            "danos",
            "observacoes",
        ]

        widgets = {

            "placa": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: ABC1D23",
                    "maxlength": 10,
                    "style": "text-transform: uppercase;",
                }
            ),

            "marca_modelo": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Fiat Argo"
                }
            ),

            "cor": forms.TextInput(
                attrs={
                    "placeholder": "Cor do veículo"
                }
            ),

            "condutor": forms.Select,

            "danos": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": (
                        "Descreva os danos identificados"
                    ),
                }
            ),

            "observacoes": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": (
                        "Informações complementares"
                    ),
                }
            ),
        }

    # ======================================================
    # INICIALIZAÇÃO
    # ======================================================

    def __init__(self, *args, **kwargs):

        ocorrencia = kwargs.pop(
            "ocorrencia",
            None
        )

        super().__init__(*args, **kwargs)

        self.fields["condutor"].required = False

        if (
            ocorrencia is None
            and self.instance.pk
        ):
            ocorrencia = self.instance.ocorrencia

        # --------------------------------------------------
        # CONDUTORES DA OCORRÊNCIA
        # --------------------------------------------------

        if (
            ocorrencia is not None
            and ocorrencia.pk
        ):

            self.fields["condutor"].queryset = (
                PessoaEnvolvida.objects.filter(
                    ocorrencia=ocorrencia,
                    papel=PessoaEnvolvida.Papel.CONDUTOR,
                ).order_by("nome")
            )

        else:

            self.fields["condutor"].queryset = (
                PessoaEnvolvida.objects.none()
            )

    # ======================================================
    # PADRONIZAR PLACA
    # ======================================================

    def clean_placa(self):

        placa = (
            self.cleaned_data.get("placa") or ""
        ).strip().upper()

        return placa


# ==========================================================
# FORMSET - PESSOAS ENVOLVIDAS
# ==========================================================

PessoaEnvolvidaFormSet = inlineformset_factory(
    Ocorrencia,
    PessoaEnvolvida,
    form=PessoaEnvolvidaForm,
    extra=1,
    can_delete=True,
)


# ==========================================================
# FORMSET - VEÍCULOS ENVOLVIDOS
# ==========================================================

VeiculoEnvolvidoFormSet = inlineformset_factory(
    Ocorrencia,
    VeiculoEnvolvido,
    form=VeiculoEnvolvidoForm,
    extra=1,
    can_delete=True,
)
