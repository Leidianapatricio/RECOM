
from django.db import models
from django.core.exceptions import ValidationError
from escolas.models import Escola


from usuarios.models import Usuario


class Equipe(models.Model):
    nome = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nome da equipe"
    )

    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição"
    )

    ativa = models.BooleanField(
        default=True,
        verbose_name="Equipe ativa"
    )

    class Meta:
        verbose_name = "Equipe"
        verbose_name_plural = "Equipes"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class IntegranteEquipe(models.Model):

    
    FUNCAO_CHOICES = [
    ("C", "Comandante"),
    ("M", "Motorista"),
    ("P1", "Patrulheiro 1"),
    ("P2", "Patrulheiro 2"),
    ]


    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.PROTECT,
        related_name="integrantes",
        verbose_name="Equipe"
    )

    gcm = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        related_name="vinculo_equipe",
        verbose_name="GCM"
    )

    funcao_habitual = models.CharField(
        max_length=20,
        choices=FUNCAO_CHOICES,
        default="P1",
        verbose_name="Função habitual"
    )

    class Meta:
        verbose_name = "Integrante da equipe"
        verbose_name_plural = "Integrantes das equipes"
        ordering = ["equipe__nome", "gcm__nome"]

    def clean(self):
        super().clean()

        if self.gcm_id and self.gcm.perfil != "GCM":
            raise ValidationError({
                "gcm": "Somente usuários com perfil GCM podem integrar equipes."
            })

    def __str__(self):
        return f"{self.gcm.nome} - {self.equipe.nome}"


class Plantao(models.Model):

    TIPO_SERVICO_CHOICES = [
        ("ORDINARIO", "Serviço Ordinário"),
        ("EXTRAORDINARIO", "Serviço Extraordinário"),
    ]

    data = models.DateField(
        verbose_name="Data do plantão"
    )

    tipo_servico = models.CharField(
        max_length=20,
        choices=TIPO_SERVICO_CHOICES,
        default="ORDINARIO"
    )

    local_descanso = models.CharField(
        max_length=150,
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Plantão"
        verbose_name_plural = "Plantões"
        ordering = ["-data"]

    def __str__(self):
        return f"Plantão {self.data:%d/%m/%Y}"



class ViaturaPlantao(models.Model):

    TIPO_SERVICO_CHOICES = [
        ("ORDINARIO", "Serviço Ordinário"),
        ("EXTRAORDINARIO", "Serviço Extraordinário"),
    ]

    plantao = models.ForeignKey(
        Plantao,
        on_delete=models.CASCADE,
        related_name="viaturas"
    )

    identificacao = models.CharField(
        max_length=30,
        verbose_name="Identificação da VTR"
    )

    modelo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Modelo do veículo"
    )

    tipo_servico = models.CharField(
        max_length=20,
        choices=TIPO_SERVICO_CHOICES,
        default="ORDINARIO",
        verbose_name="Tipo de serviço"
    )

    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.PROTECT,
        related_name="viaturas_plantoes",
        blank=True,
        null=True,
        verbose_name="Equipe fixa"
    )

    km_inicial = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="KM inicial"
    )

    km_final = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="KM final"
    )

    class Meta:
        verbose_name = "VTR do plantão"
        verbose_name_plural = "VTRs dos plantões"

        constraints = [
            models.UniqueConstraint(
                fields=["plantao", "identificacao"],
                name="unique_viatura_por_plantao"
            )
        ]

    @property
    def km_percorridos(self):
        if self.km_inicial is None or self.km_final is None:
            return None

        return self.km_final - self.km_inicial

    
    def clean(self):
        super().clean()
        erros = {}

        if self.tipo_servico == "ORDINARIO" and not self.equipe_id:
            erros["equipe"] = "Selecione a equipe responsável pelo serviço ordinário."

        if self.plantao_id and self.equipe_id:
            ordinarias = (
                ViaturaPlantao.objects.filter(
                    plantao__data=self.plantao.data,
                    tipo_servico="ORDINARIO",
                )
                .exclude(pk=self.pk)
                .exclude(equipe__isnull=True)
            )

            if self.tipo_servico == "ORDINARIO":
                if ordinarias.exclude(equipe_id=self.equipe_id).exists():
                    erros["equipe"] = (
                        "Já existe outra equipe responsável pelo serviço ordinário "
                        "nesta data. Todas as viaturas ordinárias devem usar a mesma equipe."
                    )
                elif ViaturaPlantao.objects.filter(
                    plantao__data=self.plantao.data,
                    tipo_servico="EXTRAORDINARIO",
                    equipe_id=self.equipe_id,
                ).exclude(pk=self.pk).exists():
                    erros["equipe"] = (
                        "Esta equipe já está vinculada a uma viatura extraordinária "
                        "nesta data. Não pode assumir também o serviço ordinário."
                    )

            elif self.tipo_servico == "EXTRAORDINARIO":
                if ordinarias.filter(equipe_id=self.equipe_id).exists():
                    erros["equipe"] = (
                        "A equipe do serviço extraordinário deve ser diferente "
                        "da equipe ordinária desta data."
                    )

        if (
            self.km_inicial is not None
            and self.km_final is not None
            and self.km_final < self.km_inicial
        ):
            erros["km_final"] = "A KM final não pode ser menor que a KM inicial."

        if erros:
            raise ValidationError(erros)


    def __str__(self):
        return (
            f"{self.identificacao} - "
            f"{self.get_tipo_servico_display()} - "
            f"{self.plantao.data:%d/%m/%Y}"
        )


class EfetivoViatura(models.Model):

    FUNCAO_CHOICES = [
        ("C", "Comandante"),
        ("M", "Motorista"),
        ("P1", "Patrulheiro 1"),
        ("P2", "Patrulheiro 2"),
    ]

    viatura = models.ForeignKey(
        ViaturaPlantao,
        on_delete=models.CASCADE,
        related_name="efetivo"
    )

    gcm = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="escalas_viatura"
    )

    funcao = models.CharField(
        max_length=2,
        choices=FUNCAO_CHOICES
    )

    observacao = models.CharField(
        max_length=200,
        blank=True
    )

    class Meta:
        verbose_name = "Efetivo da viatura"
        verbose_name_plural = "Efetivos das viaturas"

        constraints = [
            models.UniqueConstraint(
                fields=["viatura", "funcao"],
                name="unique_funcao_por_viatura"
            ),
            models.UniqueConstraint(
                fields=["viatura", "gcm"],
                name="unique_gcm_por_viatura"
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}

        if self.gcm_id and self.gcm.perfil != "GCM":
            erros["gcm"] = "Somente usuários com perfil GCM podem integrar o efetivo."

        if self.gcm_id and self.viatura_id:
            data = self.viatura.plantao.data

            escalas_existentes = EfetivoViatura.objects.filter(
                gcm_id=self.gcm_id,
                viatura__plantao__data=data,
            ).exclude(pk=self.pk)
            if escalas_existentes.exists():
                erros["gcm"] = "Este GCM já está escalado em outra VTR nesta data."

            # A equipe do ordinário não pode compor o efetivo extraordinário.
            if self.viatura.tipo_servico == "EXTRAORDINARIO":
                equipes_ordinarias = ViaturaPlantao.objects.filter(
                    plantao__data=data,
                    tipo_servico="ORDINARIO",
                    equipe__isnull=False,
                ).values_list("equipe_id", flat=True)
                if IntegranteEquipe.objects.filter(
                    gcm_id=self.gcm_id,
                    equipe_id__in=equipes_ordinarias,
                ).exists():
                    erros["gcm"] = (
                        "Este GCM pertence à equipe responsável pelo ordinário "
                        "nesta data e não pode integrar o extraordinário."
                    )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f"{self.gcm.nome} ({self.funcao}) - "
            f"{self.viatura.identificacao}"
        )


class CartaoPrograma(models.Model):

    plantao = models.OneToOneField(
        Plantao,
        on_delete=models.PROTECT,
        related_name="cartao_programa",
        verbose_name="Plantão"
    )

    coordenador = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="cartoes_elaborados",
        verbose_name="Coordenador responsável"
    )

    observacoes = models.TextField(
        blank=True,
        verbose_name="Observações"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Cartão Programa"
        verbose_name_plural = "Cartões Programa"
        ordering = ["-plantao__data"]

    def clean(self):
        super().clean()

        if (
            self.coordenador_id
            and self.coordenador.perfil != "COORDENADOR"
        ):
            raise ValidationError({
                "coordenador": (
                    "O responsável pelo Cartão Programa "
                    "deve possuir o perfil Coordenador RECOM."
                )
            })

    def __str__(self):
        return (
            f"Cartão Programa - "
            f"{self.plantao.data:%d/%m/%Y}"
        )


class MissaoCartao(models.Model):

    MISSAO_CHOICES = [
        ("ENTRADA", "Entrada escolar"),
        ("SAIDA", "Saída escolar"),
        ("VISITA", "Visita de rotina"),
        ("RONDAS", "Rondas"),
        ("RONDAS_PB", "Rondas e PB"),
        ("PALESTRA", "Palestra"),
        ("FANTOCHE", "Teatro de fantoches"),
        ("EJA", "Educação de Jovens e Adultos (EJA)"),
        ("OUTRA", "Outra atividade"),
    ]

    PERIODO_CHOICES = [
        ("MANHA", "Manhã"),
        ("TARDE", "Tarde"),
        ("NOITE", "Noite"),
        ("INTEGRAL", "Integral"),
    ]

    cartao = models.ForeignKey(
        CartaoPrograma,
        on_delete=models.CASCADE,
        related_name="missoes",
        verbose_name="Cartão Programa"
    )

    viatura = models.ForeignKey(
        ViaturaPlantao,
        on_delete=models.PROTECT,
        related_name="missoes",
        verbose_name="VTR responsável"
    )

    numero = models.PositiveIntegerField(
        verbose_name="Número da missão"
    )

    escola = models.ForeignKey(
        Escola,
        on_delete=models.PROTECT,
        related_name="missoes_cartao",
        blank=True,
        null=True,
        verbose_name="Escola"
    )

    local = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Outro local"
    )

    endereco = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Endereço"
    )

    periodo = models.CharField(
        max_length=10,
        choices=PERIODO_CHOICES,
        verbose_name="Período"
    )

    horario_inicio = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Horário inicial"
    )

    horario_fim = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Horário final"
    )

    tipo_missao = models.CharField(
        max_length=20,
        choices=MISSAO_CHOICES,
        verbose_name="Tipo de missão"
    )

    observacoes = models.TextField(
        blank=True,
        verbose_name="Observações"
    )
    
    # ==========================================
    # CONTROLE DE EXECUÇÃO DA MISSÃO
    # ==========================================

    STATUS_EXECUCAO_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("REALIZADA", "Realizada"),
        ("NAO_REALIZADA", "Não realizada"),
    ]

    status_execucao = models.CharField(
        max_length=20,
        choices=STATUS_EXECUCAO_CHOICES,
        default="PENDENTE",
        verbose_name="Status da execução",
    )

    motivo_nao_realizacao = models.TextField(
        blank=True,
        verbose_name="Motivo da não realização",
    )

    registrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="missoes_atualizadas",
        verbose_name="GCM responsável pelo registro",
    )

    atualizado_execucao_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data e hora da atualização da execução",
    )

    class Meta:
        verbose_name = "Missão do Cartão Programa"
        verbose_name_plural = "Missões do Cartão Programa"
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["cartao", "numero"],
                name="unique_numero_missao_cartao"
            )
        ]

    def clean(self):
        super().clean()

        erros = {}

        if not self.escola_id and not self.local.strip():
            erros["local"] = (
                "Informe uma escola cadastrada ou outro local."
            )

        if (
            self.horario_inicio
            and self.horario_fim
            and self.horario_inicio >= self.horario_fim
        ):
            erros["horario_fim"] = (
                "O horário final deve ser posterior ao inicial."
            )

        if self.cartao_id and self.viatura_id:
            if (
                self.cartao.plantao_id
                != self.viatura.plantao_id
            ):
                erros["viatura"] = (
                    "A VTR deve pertencer ao mesmo plantão "
                    "do Cartão Programa."
                )
               

        if self.status_execucao == "NAO_REALIZADA":

            if not self.motivo_nao_realizacao.strip():
                erros["motivo_nao_realizacao"] = (
                    "Informe o motivo da não realização da missão."
                )

            elif len(self.motivo_nao_realizacao) > 3000:
                erros["motivo_nao_realizacao"] = (
                    "A justificativa deve ter no máximo "
                    "3000 caracteres."
                )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f"Missão {self.numero} - "
            f"{self.get_tipo_missao_display()}"
        )


