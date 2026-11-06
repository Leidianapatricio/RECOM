
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from cartao_programa.models import ViaturaPlantao


# ==========================================================
# OCORRÊNCIA
# ==========================================================

class Ocorrencia(models.Model):

    class Categoria(models.TextChoices):
        TRANSITO = "TRANSITO", "Trânsito"
        VIOLENCIA = "VIOLENCIA", "Violência e Criminalidade"

    class NaturezaAtuacao(models.TextChoices):
        DIRETO = "DIRETO", "Atendimento direto"
        APOIO = "APOIO", "Apoio a outra equipe"

    class TipoOcorrencia(models.TextChoices):
        SINISTRO = "SINISTRO", "Sinistro de trânsito"
        FURTO = "FURTO", "Furto"
        ROUBO = "ROUBO", "Roubo"
        AMEACA = "AMEACA", "Ameaça"
        AGRESSAO = "AGRESSAO", "Agressão"

    # ------------------------------------------------------
    # IDENTIFICAÇÃO DA EQUIPE RESPONSÁVEL
    # ------------------------------------------------------

    viatura = models.ForeignKey(
        ViaturaPlantao,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        verbose_name="Viatura responsável",
        null=True,
        blank=True,
        help_text=(
            "Viatura responsável pelo atendimento, "
            "conforme a escala do Cartão Programa."
        ),
    )

    # ------------------------------------------------------
    # DADOS GERAIS
    # ------------------------------------------------------

    data = models.DateField(
        "Data da ocorrência"
    )

    horario = models.TimeField(
        "Horário"
    )

    local = models.CharField(
        "Local da ocorrência",
        max_length=255
    )

    bairro = models.CharField(
        "Bairro",
        max_length=120,
        blank=True
    )

    # ------------------------------------------------------
    # ACIONAMENTO E NATUREZA DA ATUAÇÃO
    # ------------------------------------------------------

    acionamento_cicc = models.BooleanField(
        "Acionamento do CICC?",
        default=False
    )

    natureza_atuacao = models.CharField(
        "Natureza da atuação",
        max_length=10,
        choices=NaturezaAtuacao.choices,
        default=NaturezaAtuacao.DIRETO
    )

    equipe_apoiada = models.CharField(
        "Equipe apoiada",
        max_length=150,
        blank=True
    )

    # ------------------------------------------------------
    # CLASSIFICAÇÃO
    # ------------------------------------------------------

    categoria = models.CharField(
        "Categoria",
        max_length=20,
        choices=Categoria.choices
    )

    tipo_ocorrencia = models.CharField(
        "Tipo da ocorrência",
        max_length=20,
        choices=TipoOcorrencia.choices
    )

    possui_vitima = models.BooleanField(
        "Houve vítima?",
        default=False
    )

    # ------------------------------------------------------
    # RELATO E PROVIDÊNCIAS
    # ------------------------------------------------------

    relato = models.TextField(
        "Relato da ocorrência"
    )

    providencias = models.TextField(
        "Providências adotadas",
        blank=True
    )

    orgaos_acionados = models.TextField(
        "Órgãos acionados",
        blank=True,
        help_text=(
            "Ex.: SAMU, Bombeiros, PRF, Polícia Militar."
        )
    )

    # ------------------------------------------------------
    # AUTORIA E AUDITORIA
    # ------------------------------------------------------

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ocorrencias_registradas",
        verbose_name="Registrado por"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    # ------------------------------------------------------
    # CONFIGURAÇÕES E RESTRIÇÕES
    # ------------------------------------------------------

    class Meta:
        ordering = [
            "-data",
            "-horario",
            "-id"
        ]

        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "viatura",
                    "data",
                    "horario"
                ],
                name="unique_ocorrencia_viatura_data_hora"
            )
        ]

    # ------------------------------------------------------
    # VALIDAÇÕES
    # ------------------------------------------------------

    def clean(self):
        super().clean()

        erros = {}

        # A equipe apoiada só é obrigatória quando
        # a atuação for de apoio a outra equipe.

        if self.natureza_atuacao == self.NaturezaAtuacao.APOIO:

            if not (self.equipe_apoiada or "").strip():
                erros["equipe_apoiada"] = (
                    "Informe a equipe que recebeu o apoio."
                )

        else:
            self.equipe_apoiada = ""

        # Validação da categoria e do tipo.

        tipos_transito = {
            self.TipoOcorrencia.SINISTRO
        }

        tipos_violencia = {
            self.TipoOcorrencia.FURTO,
            self.TipoOcorrencia.ROUBO,
            self.TipoOcorrencia.AMEACA,
            self.TipoOcorrencia.AGRESSAO,
        }

        if (
            self.categoria == self.Categoria.TRANSITO
            and self.tipo_ocorrencia not in tipos_transito
        ):
            erros["tipo_ocorrencia"] = (
                "Selecione um tipo de ocorrência de trânsito."
            )

        if (
            self.categoria == self.Categoria.VIOLENCIA
            and self.tipo_ocorrencia not in tipos_violencia
        ):
            erros["tipo_ocorrencia"] = (
                "Selecione um tipo de violência ou criminalidade."
            )

        # A data da ocorrência deve corresponder
        # à data do plantão da viatura.

        if self.viatura_id and self.data:

            if self.viatura.plantao.data != self.data:
                erros["data"] = (
                    "A data da ocorrência deve corresponder "
                    "à data do plantão da viatura."
                )

        # Verifica duplicidade para apresentar uma
        # mensagem amigável antes de salvar.

        if self.viatura_id and self.data and self.horario:

            duplicada = Ocorrencia.objects.filter(
                viatura_id=self.viatura_id,
                data=self.data,
                horario=self.horario
            ).exclude(
                pk=self.pk
            ).exists()

            if duplicada:
                erros["horario"] = (
                    "Já existe uma ocorrência registrada "
                    "para esta viatura, nesta data e horário. "
                    "Consulte o registro existente."
                )

        if erros:
            raise ValidationError(erros)

    # ------------------------------------------------------
    # REPRESENTAÇÃO
    # ------------------------------------------------------

    def __str__(self):
        return (
            f"Ocorrência #{self.pk or 'Nova'} - "
            f"{self.get_categoria_display()} - "
            f"{self.data:%d/%m/%Y}"
        )


# ==========================================================
# PESSOAS ENVOLVIDAS
# ==========================================================

class PessoaEnvolvida(models.Model):

    class Papel(models.TextChoices):
        VITIMA = "VITIMA", "Vítima"
        SUSPEITO = "SUSPEITO", "Suspeito"
        CONDUTOR = "CONDUTOR", "Condutor"
        PASSAGEIRO = "PASSAGEIRO", "Passageiro"
        TESTEMUNHA = "TESTEMUNHA", "Testemunha"
        OUTRO = "OUTRO", "Outro"

    class Sexo(models.TextChoices):
        MASCULINO = "M", "Masculino"
        FEMININO = "F", "Feminino"
        NAO_INFORMADO = "NI", "Não informado"

    ocorrencia = models.ForeignKey(
        Ocorrencia,
        on_delete=models.CASCADE,
        related_name="pessoas_envolvidas"
    )

    nome = models.CharField(
        "Nome",
        max_length=200
    )

    papel = models.CharField(
        "Papel na ocorrência",
        max_length=15,
        choices=Papel.choices
    )

    idade = models.PositiveSmallIntegerField(
        "Idade",
        null=True,
        blank=True
    )

    sexo = models.CharField(
        "Sexo",
        max_length=2,
        choices=Sexo.choices,
        default=Sexo.NAO_INFORMADO
    )

    documento = models.CharField(
        "Documento",
        max_length=30,
        blank=True
    )

    observacoes = models.TextField(
        "Observações",
        blank=True
    )

    class Meta:
        verbose_name = "Pessoa envolvida"
        verbose_name_plural = "Pessoas envolvidas"

    def __str__(self):
        return (
            f"{self.nome} - "
            f"{self.get_papel_display()}"
        )


# ==========================================================
# VEÍCULOS ENVOLVIDOS
# ==========================================================

class VeiculoEnvolvido(models.Model):

    ocorrencia = models.ForeignKey(
        Ocorrencia,
        on_delete=models.CASCADE,
        related_name="veiculos_envolvidos"
    )

    placa = models.CharField(
        "Placa",
        max_length=10,
        blank=True
    )

    marca_modelo = models.CharField(
        "Marca / Modelo",
        max_length=150,
        blank=True
    )

    cor = models.CharField(
        "Cor",
        max_length=50,
        blank=True
    )

    condutor = models.ForeignKey(
        PessoaEnvolvida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veiculos_conduzidos"
    )

    danos = models.TextField(
        "Danos identificados",
        blank=True
    )

    observacoes = models.TextField(
        "Observações",
        blank=True
    )

    class Meta:
        verbose_name = "Veículo envolvido"
        verbose_name_plural = "Veículos envolvidos"

    def clean(self):
        super().clean()

        if (
            self.condutor_id
            and self.ocorrencia_id
            and self.condutor.ocorrencia_id != self.ocorrencia_id
        ):
            raise ValidationError({
                "condutor": (
                    "O condutor deve pertencer "
                    "à mesma ocorrência."
                )
            })

    def __str__(self):
        return (
            self.placa
            or self.marca_modelo
            or "Veículo sem identificação"
        )
