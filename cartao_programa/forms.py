

from django import forms


from .models import (

    Equipe,

    IntegranteEquipe,

    Plantao,

    ViaturaPlantao,

    EfetivoViatura,

    CartaoPrograma,

    MissaoCartao,

)


from usuarios.models import Usuario
from escolas.models import Escola


# =====================================================

# EQUIPES

# =====================================================


class EquipeForm(forms.ModelForm):


    class Meta:

        model = Equipe

        fields = ["nome", "descricao", "ativa"]


        widgets = {

            "nome": forms.TextInput(attrs={

                "class": "form-control",

                "placeholder": "Ex.: Equipe Alfa - A",

            }),

            "descricao": forms.Textarea(attrs={

                "class": "form-control",

                "rows": 3,

                "placeholder": "Observações sobre a equipe",

            }),

            "ativa": forms.CheckboxInput(attrs={

                "class": "form-check-input",

            }),

        }


# =====================================================

# INTEGRANTES DAS EQUIPES FIXAS

# =====================================================


class IntegranteEquipeForm(forms.ModelForm):


    class Meta:

        model = IntegranteEquipe

        fields = ["equipe", "gcm", "funcao_habitual"]


        widgets = {

            "equipe": forms.Select(attrs={

                "class": "form-select",

            }),

            "gcm": forms.Select(attrs={

                "class": "form-select",

            }),

            "funcao_habitual": forms.Select(attrs={

                "class": "form-select",

            }),

        }


    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)


        equipes = Equipe.objects.filter(ativa=True)


        if self.instance.pk and self.instance.equipe_id:

            equipes = Equipe.objects.filter(

                pk__in=list(equipes.values_list("pk", flat=True))

                + [self.instance.equipe_id]

            )


        self.fields["equipe"].queryset = equipes.order_by("nome")


        vinculados = IntegranteEquipe.objects.exclude(

            pk=self.instance.pk

        ).values_list("gcm_id", flat=True)


        gcms = Usuario.objects.filter(

            perfil="GCM",

            ativo=True,

        ).exclude(pk__in=vinculados)


        if self.instance.pk and self.instance.gcm_id:

            gcms = gcms | Usuario.objects.filter(

                pk=self.instance.gcm_id

            )


        self.fields["gcm"].queryset = (

            gcms.distinct().order_by("nome")

        )


# =====================================================

# PLANTÕES

# =====================================================


class PlantaoForm(forms.ModelForm):


    class Meta:

        model = Plantao


        fields = [

            "data",

            "tipo_servico",

            "local_descanso",

            "observacoes",

        ]


        widgets = {

            "data": forms.DateInput(

                format="%Y-%m-%d",

                attrs={

                    "class": "form-control",

                    "type": "date",

                }

            ),

            "tipo_servico": forms.Select(attrs={

                "class": "form-select",

            }),

            "local_descanso": forms.TextInput(attrs={

                "class": "form-control",

                "placeholder": "Ex.: Base da RECOM",

            }),

            "observacoes": forms.Textarea(attrs={

                "class": "form-control",

                "rows": 4,

                "placeholder": "Informações adicionais sobre o plantão",

            }),

        }


    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)


        self.fields["data"].input_formats = ["%Y-%m-%d"]


        self.fields["data"].label = "Data do plantão"

        self.fields["tipo_servico"].label = "Tipo de serviço"

        self.fields["local_descanso"].label = "Local de descanso"

        self.fields["observacoes"].label = "Observações"


        self.fields["observacoes"].required = False


# =====================================================

# VIATURAS DO PLANTÃO

# =====================================================


class ViaturaPlantaoForm(forms.ModelForm):
    class Meta:
        model = ViaturaPlantao
        fields = [
            "identificacao", "modelo", "tipo_servico", "equipe",
            "km_inicial", "km_final",
        ]
        widgets = {
            "identificacao": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Ex.: VTR 01",
            }),
            "modelo": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Ex.: Duster",
            }),
            "tipo_servico": forms.Select(attrs={"class": "form-select"}),
            "equipe": forms.Select(attrs={"class": "form-select"}),
            "km_inicial": forms.NumberInput(attrs={
                "class": "form-control", "min": "0", "step": "1",
                "placeholder": "Será informada pelo GCM",
            }),
            "km_final": forms.NumberInput(attrs={
                "class": "form-control", "min": "0", "step": "1",
                "placeholder": "Ex.: 15120",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.plantao = kwargs.pop("plantao", None)
        super().__init__(*args, **kwargs)

        if self.plantao is None and self.instance.pk:
            self.plantao = self.instance.plantao
        if self.plantao is not None:
            self.instance.plantao = self.plantao

        equipes = Equipe.objects.filter(ativa=True)
        if self.instance.pk and self.instance.equipe_id:
            equipes = Equipe.objects.filter(
                pk__in=list(equipes.values_list("pk", flat=True))
                + [self.instance.equipe_id]
            )
        self.fields["equipe"].queryset = equipes.order_by("nome")
        self.fields["equipe"].empty_label = "Selecione uma equipe (opcional no extraordinário)"

        self.fields["identificacao"].label = "Identificação da viatura"
        self.fields["modelo"].label = "Modelo da viatura"
        self.fields["tipo_servico"].label = "Tipo de serviço"
        self.fields["equipe"].label = "Equipe"
        self.fields["equipe"].help_text = (
            "Ordinário: obrigatório, com uma única equipe por data. "
            "Extraordinário: opcional; ao selecionar uma equipe, "
            "seus integrantes disponíveis serão adicionados automaticamente."
        )
        self.fields["km_inicial"].label = "Quilometragem inicial"
        self.fields["km_final"].label = "Quilometragem final"
        self.fields["km_inicial"].required = False
        self.fields["km_final"].required = False
        self.fields["equipe"].required = False
        self.fields["km_inicial"].widget.attrs.pop("required", None)
        self.fields["km_final"].widget.attrs.pop("required", None)

    def clean(self):
        dados = super().clean()
        if self.plantao is None:
            raise forms.ValidationError("Não foi possível identificar o plantão.")

        identificacao = dados.get("identificacao")
        tipo = dados.get("tipo_servico")
        equipe = dados.get("equipe")
        inicial = dados.get("km_inicial")
        final = dados.get("km_final")

        if identificacao and ViaturaPlantao.objects.filter(
            plantao=self.plantao, identificacao=identificacao,
        ).exclude(pk=self.instance.pk).exists():
            self.add_error(
                "identificacao",
                "Já existe uma viatura com essa identificação neste plantão.",
            )

        ordinarias = ViaturaPlantao.objects.filter(
            plantao__data=self.plantao.data,
            tipo_servico="ORDINARIO",
            equipe__isnull=False,
        ).exclude(pk=self.instance.pk)

        if tipo == "ORDINARIO":
            if not equipe:
                self.add_error(
                    "equipe",
                    "Selecione a equipe responsável pelo serviço ordinário."
                )

            elif ViaturaPlantao.objects.filter(
                plantao__data=self.plantao.data,
                tipo_servico="EXTRAORDINARIO",
                equipe=equipe,
            ).exclude(pk=self.instance.pk).exists():
                self.add_error(
                    "equipe",
                    "Esta equipe já está vinculada a uma viatura extraordinária "
                    "nesta data. Não pode assumir também o serviço ordinário."
                )
                if tipo == "EXTRAORDINARIO" and equipe:
                    # O extraordinário aceita várias equipes, mas não a equipe
                    # que está cumprindo o serviço ordinário na mesma data.
                    if ordinarias.filter(equipe=equipe).exists():
                        self.add_error(
                            "equipe",
                            "Esta equipe já está no serviço ordinário nesta data. "
                            "Selecione outra equipe para o extraordinário.",
                        )

                if inicial is not None and final is not None and final < inicial:
                    self.add_error(
                        "km_final", "A quilometragem final não pode ser menor que a inicial."
                    )
                return dados


# =====================================================
# EFETIVO DAS VIATURAS
# =====================================================

class EfetivoViaturaForm(forms.ModelForm):
    class Meta:
        model = EfetivoViatura
        fields = ["gcm", "funcao", "observacao"]
        widgets = {
            "gcm": forms.Select(attrs={"class": "form-select"}),
            "funcao": forms.Select(attrs={"class": "form-select"}),
            "observacao": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex.: Substituição temporária",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.viatura = kwargs.pop("viatura", None)
        super().__init__(*args, **kwargs)
        if self.viatura is None and self.instance.pk:
            self.viatura = self.instance.viatura
        if self.viatura is not None:
            self.instance.viatura = self.viatura

        self.fields["gcm"].label = "GCM"
        self.fields["funcao"].label = "Função na viatura"
        self.fields["observacao"].label = "Observação"
        self.fields["observacao"].required = False

        gcms = Usuario.objects.filter(perfil="GCM", ativo=True)
        if self.viatura is not None:
            escalados = EfetivoViatura.objects.filter(
                viatura__plantao__data=self.viatura.plantao.data,
            ).exclude(pk=self.instance.pk).values_list("gcm_id", flat=True)
            gcms = gcms.exclude(pk__in=escalados)

        if self.instance.pk and self.instance.gcm_id:
            gcms = gcms | Usuario.objects.filter(pk=self.instance.gcm_id)
        self.fields["gcm"].queryset = gcms.distinct().order_by("nome")

        if self.viatura is not None:
            ocupadas = set(EfetivoViatura.objects.filter(
                viatura=self.viatura,
            ).exclude(pk=self.instance.pk).values_list("funcao", flat=True))
            self.fields["funcao"].choices = [
                (valor, descricao)
                for valor, descricao in EfetivoViatura.FUNCAO_CHOICES
                if valor not in ocupadas
            ]

    def clean(self):
        dados = super().clean()
        if self.viatura is None:
            raise forms.ValidationError("Não foi possível identificar a viatura.")

        gcm = dados.get("gcm")
        funcao = dados.get("funcao")
        outros = EfetivoViatura.objects.filter(
            viatura=self.viatura,
        ).exclude(pk=self.instance.pk)

        if outros.count() >= 4:
            raise forms.ValidationError("Esta viatura já possui quatro integrantes.")

        if funcao and outros.filter(funcao=funcao).exists():
            self.add_error("funcao", "Esta função já está ocupada na viatura.")

        if gcm and EfetivoViatura.objects.filter(
            gcm=gcm,
            viatura__plantao__data=self.viatura.plantao.data,
        ).exclude(pk=self.instance.pk).exists():
            self.add_error(
                "gcm", "Este GCM já está escalado em outra viatura nesta data."
            )
        return dados


# =====================================================
# CARTÃO PROGRAMA
# =====================================================

class CartaoProgramaForm(forms.ModelForm):

    class Meta:
        model = CartaoPrograma

        fields = [
            "observacoes",
        ]

        widgets = {
            "observacoes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Observações gerais do Cartão Programa",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.plantao = kwargs.pop("plantao", None)
        super().__init__(*args, **kwargs)

        if self.plantao is None and self.instance.pk:
            self.plantao = self.instance.plantao

        if self.plantao is not None:
            self.instance.plantao = self.plantao

        self.fields["observacoes"].label = "Observações gerais"
        self.fields["observacoes"].required = False

    def clean(self):
        cleaned_data = super().clean()

        if self.plantao is None:
            raise forms.ValidationError(
                "Não foi possível identificar o plantão do Cartão Programa."
            )

        return cleaned_data


# =====================================================

# MISSÕES DO CARTÃO PROGRAMA

# =====================================================


class MissaoCartaoForm(forms.ModelForm):


    class Meta:

        model = MissaoCartao


        fields = [

            "numero",

            "viatura",

            "escola",

            "local",

            "endereco",

            "periodo",

            "horario_inicio",

            "horario_fim",

            "tipo_missao",

            "observacoes",

        ]


        widgets = {

            "numero": forms.NumberInput(attrs={

                "class": "form-control",

                "min": "1",

                "step": "1",

            }),

            "viatura": forms.Select(attrs={

                "class": "form-select",

            }),

            "escola": forms.Select(attrs={

                "class": "form-select",

            }),

            "local": forms.TextInput(attrs={

                "class": "form-control",

                "placeholder": "Ex.: Praça de Iemanjá",

            }),

            "endereco": forms.TextInput(attrs={

                "class": "form-control",

                "placeholder": "Endereço do local da missão",

            }),

            "periodo": forms.Select(attrs={

                "class": "form-select",

            }),

            "horario_inicio": forms.TimeInput(

                format="%H:%M",

                attrs={

                    "class": "form-control",

                    "type": "time",

                }

            ),

            "horario_fim": forms.TimeInput(

                format="%H:%M",

                attrs={

                    "class": "form-control",

                    "type": "time",

                }

            ),

            "tipo_missao": forms.Select(attrs={

                "class": "form-select",

            }),

            "observacoes": forms.Textarea(attrs={

                "class": "form-control",

                "rows": 3,

                "placeholder": "Orientações e observações da missão",

            }),

        }


    def __init__(self, *args, **kwargs):

        self.cartao = kwargs.pop("cartao", None)

        super().__init__(*args, **kwargs)


        if self.cartao is None and self.instance.pk:

            self.cartao = self.instance.cartao


        if self.cartao is not None:

            self.instance.cartao = self.cartao


            self.fields["viatura"].queryset = (

                ViaturaPlantao.objects.filter(

                    plantao=self.cartao.plantao

                ).order_by("identificacao")

            )

        else:

            self.fields["viatura"].queryset = (

                ViaturaPlantao.objects.none()

            )


        self.fields["numero"].label = "Número da missão"

        self.fields["viatura"].label = "Viatura responsável"

        self.fields["escola"].label = "Escola"

        self.fields["local"].label = "Outro local"

        self.fields["endereco"].label = "Endereço"

        self.fields["periodo"].label = "Período"

        self.fields["horario_inicio"].label = "Horário inicial"

        self.fields["horario_fim"].label = "Horário final"

        self.fields["tipo_missao"].label = "Tipo de missão"

        self.fields["observacoes"].label = "Observações"


        self.fields["escola"].required = False

        self.fields["local"].required = False

        self.fields["endereco"].required = False

        self.fields["horario_inicio"].required = False

        self.fields["horario_fim"].required = False

        self.fields["observacoes"].required = False


        self.fields["horario_inicio"].input_formats = [

            "%H:%M",

            "%H:%M:%S",

        ]

        self.fields["horario_fim"].input_formats = [

            "%H:%M",

            "%H:%M:%S",

        ]


        if self.cartao is not None and not self.instance.pk:

            ultimo_numero = (

                MissaoCartao.objects.filter(

                    cartao=self.cartao

                ).order_by("-numero")

                .values_list("numero", flat=True)

                .first()

            )


            self.fields["numero"].initial = (

                (ultimo_numero or 0) + 1

            )


    def clean(self):

        cleaned_data = super().clean()


        numero = cleaned_data.get("numero")

        viatura = cleaned_data.get("viatura")

        escola = cleaned_data.get("escola")

        local = (cleaned_data.get("local") or "").strip()

        inicio = cleaned_data.get("horario_inicio")

        fim = cleaned_data.get("horario_fim")


        if self.cartao is None:

            raise forms.ValidationError(

                "Não foi possível identificar o Cartão Programa."

            )


        if numero is not None:

            existente = MissaoCartao.objects.filter(

                cartao=self.cartao,

                numero=numero,

            ).exclude(pk=self.instance.pk)


            if existente.exists():

                self.add_error(

                    "numero",

                    "Já existe uma missão com esse número neste Cartão Programa."

                )


        if viatura and viatura.plantao_id != self.cartao.plantao_id:

            self.add_error(

                "viatura",

                "A viatura deve pertencer ao mesmo plantão do Cartão Programa."

            )


        if not escola and not local:

            self.add_error(

                "local",

                "Selecione uma escola cadastrada ou informe outro local."

            )


        if inicio and fim and inicio >= fim:

            self.add_error(

                "horario_fim",

                "O horário final deve ser posterior ao horário inicial."

            )


        return cleaned_data

# =====================================================
# CADASTRO DE MISSÕES EM LOTE POR POLO
# =====================================================

class MissoesEmLoteForm(forms.Form):
    """Cria uma missão independente para cada escola selecionada.

    A persistência é feita na view, dentro de transaction.atomic().
    """

    polo = forms.TypedChoiceField(
        label="Polo",
        choices=[("", "Selecione um polo")] + [
            (str(numero), nome) for numero, nome in Escola.POLO_CHOICES
        ],
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    escolas = forms.ModelMultipleChoiceField(
        label="Escolas do polo",
        queryset=Escola.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={
            "required": "Selecione pelo menos uma escola.",
            "invalid_choice": "Uma das escolas selecionadas não é válida.",
        },
    )

    viatura = forms.ModelChoiceField(
        label="Viatura responsável",
        queryset=ViaturaPlantao.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    tipo_missao = forms.ChoiceField(
        label="Tipo de missão",
        choices=MissaoCartao._meta.get_field("tipo_missao").choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    periodo = forms.ChoiceField(
        label="Período",
        choices=MissaoCartao._meta.get_field("periodo").choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    horario_inicio = forms.TimeField(
        label="Horário inicial",
        required=False,
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(format="%H:%M", attrs={
            "class": "form-control", "type": "time",
        }),
    )

    horario_fim = forms.TimeField(
        label="Horário final",
        required=False,
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(format="%H:%M", attrs={
            "class": "form-control", "type": "time",
        }),
    )

    observacoes = forms.CharField(
        label="Observações",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": 3,
            "placeholder": "Orientações comuns às escolas selecionadas",
        }),
    )

    def __init__(self, *args, **kwargs):
        self.cartao = kwargs.pop("cartao", None)
        super().__init__(*args, **kwargs)

        if self.cartao is not None:
            self.fields["viatura"].queryset = (
                ViaturaPlantao.objects.filter(plantao=self.cartao.plantao)
                .order_by("identificacao")
            )

        # Em um POST, o polo selecionado determina quais escolas podem ser
        # validadas. Nunca confiar apenas na filtragem feita pelo navegador.
        polo = None
        if self.is_bound:
            polo = self.data.get(self.add_prefix("polo"))
        else:
            polo = self.initial.get("polo")

        try:
            polo_numero = int(polo)
        except (TypeError, ValueError):
            polo_numero = None

        polos_validos = {numero for numero, _ in Escola.POLO_CHOICES}
        if polo_numero in polos_validos:
            self.fields["escolas"].queryset = (
                Escola.objects.filter(polo=polo_numero, ativa=True)
                .order_by("nome")
            )

    def clean(self):
        cleaned_data = super().clean()

        if self.cartao is None:
            raise forms.ValidationError(
                "Não foi possível identificar o Cartão Programa."
            )

        polo = cleaned_data.get("polo")
        escolas = cleaned_data.get("escolas")
        inicio = cleaned_data.get("horario_inicio")
        fim = cleaned_data.get("horario_fim")
        viatura = cleaned_data.get("viatura")

        if polo is not None and polo not in {
            numero for numero, _ in Escola.POLO_CHOICES
        }:
            self.add_error("polo", "Selecione um polo válido.")

        if escolas and any(
            escola.polo != polo or not escola.ativa for escola in escolas
        ):
            self.add_error(
                "escolas", "Selecione somente escolas ativas do polo informado."
            )

        if viatura and viatura.plantao_id != self.cartao.plantao_id:
            self.add_error(
                "viatura", "A viatura deve pertencer ao plantão do cartão."
            )

        if inicio and fim and inicio >= fim:
            self.add_error(
                "horario_fim", "O horário final deve ser posterior ao inicial."
            )

        return cleaned_data
