
from django.db import models
from django.core.exceptions import ValidationError

from escolas.models import Escola


class RondaVisita(models.Model):

    # ==========================================
    # OPÇÕES DE EQUIPE
    # ==========================================

    EQUIPE_CHOICES = [
        ("A", "Equipe A"),
        ("B", "Equipe B"),
        ("C", "Equipe C"),
        ("D", "Equipe D"),
        ("E", "Equipe E"),
        ("F", "Equipe F"),
        ("EXTRA", "Equipe Extraordinário"),
    ]

    # ==========================================
    # TIPOS DE VISITA
    # ==========================================

    TIPO_VISITA_CHOICES = [
        ("ROTINA", "Visita de rotina"),
        ("ENTRADA", "Acompanhamento de entrada"),
        ("SAIDA", "Acompanhamento de saída"),
        ("EVENTO", "Acompanhamento de evento"),
        ("PALESTRA", "Palestra"),
        ("FANTOCHE", "Teatro de fantoches"),
        ("RONDAS", "Rondas"),
        ("RONDAS_PB", "Rondas e PB"),
        ("APOIO", "Apoio / atendimento"),
        ("OUTRA", "Outra"),
    ]

    # ==========================================
    # SITUAÇÃO DA VISITA
    # ==========================================

    SITUACAO_CHOICES = [
        ("SEM_ALTERACAO", "Sem alteração"),
        ("COM_ALTERACAO", "Com alteração"),
    ]

    # ==========================================
    # ESCOLA
    # ==========================================

    escola = models.ForeignKey(
        Escola,
        on_delete=models.PROTECT,
        related_name="visitas",
        verbose_name="Escola",
    )

    # ==========================================
    # MISSÃO DO CARTÃO PROGRAMA
    # ==========================================

    missao_cartao = models.ForeignKey(
        "cartao_programa.MissaoCartao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas_registradas",
        verbose_name="Missão do Cartão Programa",
        help_text=(
            "Missão vinculada à visita. "
            "Pode ficar em branco para visitas avulsas."
        ),
    )

    # ==========================================
    # VIATURA DO PLANTÃO
    # ==========================================

    viatura = models.ForeignKey(
        "cartao_programa.ViaturaPlantao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="visitas",
        verbose_name="Viatura do plantão",
        help_text=(
            "Viatura responsável pela visita. "
            "Nas visitas programadas, será definida "
            "automaticamente pela missão."
        ),
    )

    # ==========================================
    # RESPONSÁVEL PELO REGISTRO
    # ==========================================

    registrado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="visitas_registradas_por_usuario",
        verbose_name="Registrado por",
        help_text=(
            "Usuário responsável pelo cadastro da visita. "
            "Preenchido automaticamente pelo sistema."
        ),
    )

    # ==========================================
    # EQUIPE
    # ==========================================

    equipe = models.CharField(
        max_length=10,
        choices=EQUIPE_CHOICES,
        verbose_name="Equipe responsável",
    )

    # ==========================================
    # DATA E HORÁRIO
    # ==========================================

    data_visita = models.DateField(
        verbose_name="Data da visita",
    )

    horario = models.TimeField(
        verbose_name="Horário",
    )

    # ==========================================
    # TIPO DE VISITA
    # ==========================================

    tipo_visita = models.CharField(
        max_length=20,
        choices=TIPO_VISITA_CHOICES,
        default="ROTINA",
        verbose_name="Tipo de visita",
    )

    # ==========================================
    # SITUAÇÃO
    # ==========================================

    situacao = models.CharField(
        max_length=20,
        choices=SITUACAO_CHOICES,
        default="SEM_ALTERACAO",
        verbose_name="Situação",
    )

    # ==========================================
    # RELATO
    # ==========================================

    relato = models.TextField(
        blank=True,
        verbose_name="Relato da visita",
    )

    # ==========================================
    # ORIENTAÇÕES / PROVIDÊNCIAS
    # ==========================================

    orientacoes = models.TextField(
        blank=True,
        verbose_name="Orientações / providências",
    )

    # ==========================================
    # CONTROLE DE DATAS
    # ==========================================

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    # ==========================================
    # CONFIGURAÇÕES DO MODELO
    # ==========================================

    class Meta:

        ordering = [
            "-data_visita",
            "-horario",
        ]

        verbose_name = "Ronda / Visita"
        verbose_name_plural = "Rondas / Visitas"

        constraints = [
            models.UniqueConstraint(
                fields=["missao_cartao"],
                condition=models.Q(
                    missao_cartao__isnull=False
                ),
                name="unique_visita_por_missao",
            ),
        ]

    # ==========================================
    # VALIDAÇÃO
    # ==========================================

    def clean(self):

        super().clean()

        erros = {}

        if self.missao_cartao_id:

            missao = self.missao_cartao

            if not missao.escola_id:
                erros["missao_cartao"] = (
                    "Esta missão não possui escola vinculada "
                    "para registro de visita."
                )

            elif (
                self.escola_id
                and self.escola_id != missao.escola_id
            ):
                erros["escola"] = (
                    "A escola selecionada deve ser a mesma "
                    "escola da missão do Cartão Programa."
                )

            if missao.status_execucao == "NAO_REALIZADA":
                erros["missao_cartao"] = (
                    "Esta missão foi marcada como não realizada. "
                    "Não é permitido registrar uma visita."
                )

            visita_existente = (
                RondaVisita.objects.filter(
                    missao_cartao_id=self.missao_cartao_id
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if visita_existente:
                erros["missao_cartao"] = (
                    "Esta missão já possui uma visita registrada. "
                    "Consulte o Cartão Programa para visualizar "
                    "o registro realizado pela equipe."
                )

            # A viatura deve corresponder à missão.
            if (
                self.viatura_id
                and self.viatura_id != missao.viatura_id
            ):
                erros["viatura"] = (
                    "A viatura da visita deve ser a mesma "
                    "viatura vinculada à missão."
                )

            # A data deve corresponder ao plantão.
            if (
                self.data_visita
                and self.data_visita
                != missao.viatura.plantao.data
            ):
                erros["data_visita"] = (
                    "A data da visita deve corresponder "
                    "à data do plantão da missão."
                )

        # Validação para qualquer visita com viatura.
        if self.viatura_id and self.data_visita:

            if self.data_visita != self.viatura.plantao.data:
                erros["data_visita"] = (
                    "A data da visita deve corresponder "
                    "à data do plantão da viatura."
                )

        if erros:
            raise ValidationError(erros)

    # ==========================================
    # REPRESENTAÇÃO
    # ==========================================

    def __str__(self):

        return (
            f"{self.escola.nome} - "
            f"{self.data_visita.strftime('%d/%m/%Y')} - "
            f"Equipe {self.equipe}"
        )
