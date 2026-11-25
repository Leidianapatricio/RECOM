
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import inlineformset_factory

from cartao_programa.models import CartaoPrograma
from escolas.models import Escola
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
    Aplica automaticamente as classes Bootstrap
    aos campos dos formulários.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for nome, campo in self.fields.items():
            widget = campo.widget

            if isinstance(widget, forms.HiddenInput):
                continue

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"

            elif isinstance(
                widget,
                (forms.RadioSelect, forms.CheckboxSelectMultiple),
            ):
                widget.attrs["class"] = "form-check-input"

            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"

            else:
                widget.attrs["class"] = "form-control"


# ==========================================================
# FORMULÁRIO PRINCIPAL DA OCORRÊNCIA
# ==========================================================

class OcorrenciaForm(BootstrapModelForm):
    """
    Formulário para cadastrar e editar ocorrências.

    ADMIN e COORDENADOR:
        Podem vincular ocorrências a qualquer Cartão Programa.

    GCM:
        Pode registrar ocorrências independentemente
        da função exercida na escala.

        Quando estiver escalado, a ocorrência poderá
        ser vinculada ao respectivo Cartão Programa.

        Quando não estiver escalado, poderá registrar
        uma ocorrência sem vínculo com um cartão.

    EDIÇÃO:
        O vínculo original com o Cartão Programa
        não poderá ser alterado.

    ESCOLA:
        O vínculo é opcional.
        A lista apresenta as escolas ativas,
        ordenadas alfabeticamente.

        Na edição, preserva a escola vinculada,
        mesmo que esteja desativada.

    As permissões também devem ser verificadas
    nas views.
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

    # ======================================================
    # CONFIGURAÇÃO DO MODELFORM
    # ======================================================

    class Meta:
        model = Ocorrencia

        fields = [
            "cartao_programa",
            "data",
            "horario",
            "escola",
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
            "cartao_programa": "Cartão Programa",
            "data": "Data da ocorrência",
            "horario": "Horário",
            "escola": "Escola",
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
            "cartao_programa": forms.Select(),

            "data": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),

            "horario": forms.TimeInput(
                attrs={"type": "time"},
                format="%H:%M",
            ),

            # Lista suspensa preparada para Select2.
            # A pesquisa será exibida dentro da lista.

            "escola": forms.Select(
                attrs={
                    "class": "form-select",
                    "data-control": "select2-escola",
                    "data-placeholder": (
                        "Selecione ou pesquise uma escola"
                    ),
                    "style": "width: 100%;",
                }
            ),

            "local": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Informe o endereço ou local da ocorrência"
                    ),
                }
            ),

            "bairro": forms.TextInput(
                attrs={
                    "placeholder": "Informe o bairro",
                }
            ),

            "natureza_atuacao": forms.RadioSelect,

            "equipe_apoiada": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ex.: Tático 1, Preventivo, ROCAM, PRF"
                    ),
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
            None,
        )

        super().__init__(*args, **kwargs)

        self.usuario_logado = usuario_logado
        self.usuario_recom = None
        self.gestor = False
        self.modo_edicao = bool(self.instance.pk)

        # --------------------------------------------------
        # IDENTIFICAR USUÁRIO AUTENTICADO
        # --------------------------------------------------

        if (
            usuario_logado is not None
            and usuario_logado.is_authenticated
            and usuario_logado.is_active
        ):

            self.usuario_recom = Usuario.objects.filter(
                user=usuario_logado,
                ativo=True,
            ).first()

            self.gestor = (
                usuario_logado.is_superuser
                or (
                    self.usuario_recom is not None
                    and self.usuario_recom.perfil in (
                        "ADMIN",
                        "COORDENADOR",
                    )
                )
            )

        # --------------------------------------------------
        # CONFIGURAÇÃO DOS CAMPOS
        # --------------------------------------------------

        self.fields["cartao_programa"].required = False

        self.fields["cartao_programa"].empty_label = (
            "Sem Cartão Programa"
        )

        self.fields["cartao_programa"].help_text = (
            "Quando houver vínculo com um Cartão Programa, "
            "a ocorrência será compartilhada com todos "
            "os GCMs nele escalados."
        )

        self.fields["equipe_apoiada"].required = False

        # Categoria obrigatória, sem opção vazia no RadioSelect.
        self.fields["categoria"].choices = Ocorrencia.Categoria.choices
        self.fields["categoria"].required = True

        # --------------------------------------------------
        # ESCOLAS
        # --------------------------------------------------

        self.fields["escola"].required = False

        # Apresenta somente escolas ativas em novos
        # cadastros.
        #
        # Na edição, mantém a escola vinculada
        # mesmo que tenha sido desativada.

        filtro_escolas = Q(ativa=True)

        if (
            self.modo_edicao
            and self.instance.escola_id
        ):
            filtro_escolas |= Q(
                pk=self.instance.escola_id
            )

        self.fields["escola"].queryset = (
            Escola.objects.filter(filtro_escolas)
            .order_by("nome", "pk")
            .distinct()
        )

        # A primeira opção é apenas um placeholder.
        # O campo continua opcional.

        self.fields["escola"].empty_label = (
            "Selecione ou pesquise uma escola"
        )

        self.fields["escola"].help_text = ""

        # Identificador usado pelo JavaScript
        # para ativar a pesquisa dentro da lista.

        self.fields["escola"].widget.attrs.update({
            "id": "id_escola",
            "data-control": "select2-escola",
            "data-placeholder": (
                "Selecione ou pesquise uma escola"
            ),
        })

        # --------------------------------------------------
        # TIPO DE OCORRÊNCIA
        # --------------------------------------------------

        self.fields["tipo_ocorrencia"].choices = [
            ("", "Selecione o tipo de ocorrência"),
            *Ocorrencia.TipoOcorrencia.choices,
        ]

        self.fields[
            "tipo_ocorrencia"
        ].widget.attrs["data-categoria"] = (
            "tipo-ocorrencia"
        )

        # --------------------------------------------------
        # CAMPOS SIM / NÃO
        # --------------------------------------------------

        self.initial["acionamento_cicc"] = (
            "sim"
            if (
                self.instance.pk
                and self.instance.acionamento_cicc
            )
            else "nao"
        )

        self.initial["possui_vitima"] = (
            "sim"
            if (
                self.instance.pk
                and self.instance.possui_vitima
            )
            else "nao"
        )

        # --------------------------------------------------
        # CARTÕES PROGRAMA AUTORIZADOS
        # --------------------------------------------------

        self.fields["cartao_programa"].queryset = (
            self.obter_cartoes_autorizados()
        )

        self.fields[
            "cartao_programa"
        ].label_from_instance = (
            self.descricao_cartao_programa
        )

        # --------------------------------------------------
        # EDIÇÃO DE OCORRÊNCIA
        # --------------------------------------------------

        if self.modo_edicao:

            if self.instance.cartao_programa_id:

                self.fields[
                    "cartao_programa"
                ].queryset = (
                    CartaoPrograma.objects.filter(
                        pk=self.instance.cartao_programa_id
                    ).select_related("plantao")
                )

                self.initial["cartao_programa"] = (
                    self.instance.cartao_programa_id
                )

            else:

                self.initial["cartao_programa"] = None

                self.fields[
                    "cartao_programa"
                ].queryset = (
                    CartaoPrograma.objects.none()
                )

            # Impede alterações no vínculo original.

            self.fields[
                "cartao_programa"
            ].disabled = True

            self.fields[
                "cartao_programa"
            ].help_text = (
                "O vínculo original com o Cartão Programa "
                "não pode ser alterado durante a edição."
            )

            # Preserva a data quando existe vínculo
            # com Cartão Programa ou viatura.

            if (
                self.instance.cartao_programa_id
                or self.instance.viatura_id
            ):
                self.fields["data"].disabled = True

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
    # IDENTIFICAR CARTÕES PROGRAMA AUTORIZADOS
    # ======================================================

    def obter_cartoes_autorizados(self, data=None):
        """
        Retorna os cartões disponíveis para o
        usuário autenticado.

        Não restringe pela função C, M, P1 ou P2.
        """

        cartoes = CartaoPrograma.objects.none()

        usuario_logado = self.usuario_logado

        if (
            usuario_logado is None
            or not usuario_logado.is_authenticated
            or not usuario_logado.is_active
        ):
            return cartoes

        # --------------------------------------------------
        # ADMINISTRADOR E COORDENADOR
        # --------------------------------------------------

        if self.gestor:

            cartoes = CartaoPrograma.objects.all()

        # --------------------------------------------------
        # GCM - TODAS AS FUNÇÕES
        # --------------------------------------------------

        elif (
            self.usuario_recom is not None
            and self.usuario_recom.perfil == "GCM"
        ):

            cartoes = CartaoPrograma.objects.filter(
                plantao__viaturas__efetivo__gcm=(
                    self.usuario_recom
                )
            ).distinct()

        # --------------------------------------------------
        # FILTRO PELA DATA
        # --------------------------------------------------

        if data is not None:

            cartoes = cartoes.filter(
                plantao__data=data
            )

        # --------------------------------------------------
        # ORDENAÇÃO
        # --------------------------------------------------

        return (
            cartoes
            .select_related("plantao")
            .order_by(
                "-plantao__data",
                "-pk",
            )
        )

    # ======================================================
    # DESCRIÇÃO DO CARTÃO PROGRAMA
    # ======================================================

    @staticmethod
    def descricao_cartao_programa(cartao):

        data = cartao.plantao.data.strftime(
            "%d/%m/%Y"
        )

        tipo_servico = (
            cartao.plantao.get_tipo_servico_display()
        )

        return (
            f"CP {cartao.pk} - "
            f"{data} - "
            f"{tipo_servico}"
        )

    # ======================================================
    # VALIDAÇÕES DO FORMULÁRIO
    # ======================================================

    def clean(self):

        cleaned_data = super().clean()

        cartao_programa = cleaned_data.get(
            "cartao_programa"
        )

        data = cleaned_data.get("data")

        natureza = cleaned_data.get(
            "natureza_atuacao"
        )

        equipe_apoiada = (
            cleaned_data.get("equipe_apoiada") or ""
        ).strip()

        categoria = cleaned_data.get("categoria")

        tipo = cleaned_data.get("tipo_ocorrencia")

        # --------------------------------------------------
        # VALIDAR USUÁRIO
        # --------------------------------------------------

        usuario_logado = self.usuario_logado

        if (
            usuario_logado is None
            or not usuario_logado.is_authenticated
            or not usuario_logado.is_active
        ):
            raise ValidationError(
                "Usuário não autenticado ou inativo."
            )

        if not self.gestor:

            if (
                self.usuario_recom is None
                or self.usuario_recom.perfil != "GCM"
            ):
                raise ValidationError(
                    "Você não possui permissão "
                    "para registrar ocorrências."
                )

        # --------------------------------------------------
        # CADASTRO DE NOVA OCORRÊNCIA
        # --------------------------------------------------

        if not self.modo_edicao:

            # Novos registros não possuem vínculo
            # direto com viatura.

            self.instance.viatura = None

            if (
                data
                and "cartao_programa" not in self.errors
            ):

                cartoes_disponiveis = (
                    self.obter_cartoes_autorizados(
                        data=data
                    )
                )

                # Cartão Programa informado.

                if cartao_programa:

                    if (
                        cartao_programa.plantao.data
                        != data
                    ):

                        self.add_error(
                            "cartao_programa",
                            "A data do Cartão Programa deve "
                            "corresponder à data da ocorrência.",
                        )

                    elif not cartoes_disponiveis.filter(
                        pk=cartao_programa.pk
                    ).exists():

                        self.add_error(
                            "cartao_programa",
                            "Você não possui autorização "
                            "para utilizar este Cartão Programa.",
                        )

                # Cartão Programa não informado.

                elif not self.gestor:

                    quantidade = (
                        cartoes_disponiveis.count()
                    )

                    if quantidade == 1:

                        cartao_programa = (
                            cartoes_disponiveis.first()
                        )

                        cleaned_data[
                            "cartao_programa"
                        ] = cartao_programa

                    elif quantidade > 1:

                        self.add_error(
                            "cartao_programa",
                            "Selecione o Cartão Programa "
                            "correspondente à sua escala.",
                        )

                    else:

                        cleaned_data[
                            "cartao_programa"
                        ] = None

        # --------------------------------------------------
        # EDIÇÃO DE OCORRÊNCIA
        # --------------------------------------------------

        else:

            cleaned_data["cartao_programa"] = (
                self.instance.cartao_programa
            )

            if (
                self.instance.cartao_programa_id
                or self.instance.viatura_id
            ):

                cleaned_data["data"] = (
                    self.instance.data
                )

        # --------------------------------------------------
        # EQUIPE APOIADA
        # --------------------------------------------------

        if natureza == Ocorrencia.NaturezaAtuacao.APOIO:

            if not equipe_apoiada:

                self.add_error(
                    "equipe_apoiada",
                    "Informe qual equipe recebeu o apoio.",
                )

            else:

                cleaned_data[
                    "equipe_apoiada"
                ] = equipe_apoiada

        else:

            cleaned_data["equipe_apoiada"] = ""

        # --------------------------------------------------
        # CATEGORIA E TIPO
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
                Ocorrencia.TipoOcorrencia.OUTRA,
            },
        }

        if (
            categoria
            and tipo
            and tipo not in tipos_por_categoria.get(
                categoria,
                set(),
            )
        ):

            self.add_error(
                "tipo_ocorrencia",
                "O tipo selecionado não pertence "
                "à categoria informada.",
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
                    ),
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
                    "placeholder": (
                        "CPF ou outro documento"
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
    # VALIDAR IDADE
    # ======================================================

    def clean_idade(self):

        idade = self.cleaned_data.get("idade")

        if (
            idade is not None
            and idade > 120
        ):
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
                    "style": (
                        "text-transform: uppercase;"
                    ),
                }
            ),

            "marca_modelo": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Fiat Argo",
                }
            ),

            "cor": forms.TextInput(
                attrs={
                    "placeholder": "Cor do veículo",
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
            None,
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
