
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from escolas.models import Escola
from usuarios.models import Usuario


# ============================================================
# PLANEJAMENTO DE MEDIAÇÃO
# ============================================================

class PlanejamentoMediacao(models.Model):

    STATUS_CHOICES = [
        ("PLANEJADA", "Planejada"),
        ("REALIZADA", "Realizada"),
        ("REAGENDADA", "Reagendada"),
        ("CANCELADA", "Cancelada"),
    ]

    data = models.DateField(
        verbose_name="Data prevista"
    )

    escola = models.ForeignKey(
        Escola,
        on_delete=models.PROTECT,
        related_name="planejamentos_mediacao",
        verbose_name="Escola"
    )

    mediador = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="planejamentos_mediacao",
        verbose_name="Mediador responsável"
    )

    mediacoes_previstas = models.TextField(
        verbose_name="Mediações previstas / Observações",
        help_text=(
            "Descreva as atividades, temas e estratégias "
            "de mediação previstas para a escola."
        )
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PLANEJADA",
        verbose_name="Situação do planejamento"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            "-data",
            "escola__nome",
        ]

        verbose_name = "Planejamento de mediação"
        verbose_name_plural = "Planejamentos de mediação"

    def clean(self):
        super().clean()

        erros = {}

        if self.escola_id and not self.escola.ativa:
            erros["escola"] = (
                "Selecione uma escola ativa."
            )

        if self.mediador_id:
            if self.mediador.perfil != "MEDIADOR":
                erros["mediador"] = (
                    "O responsável deve possuir "
                    "o perfil Mediador."
                )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f"{self.escola.nome} - "
            f"{self.data.strftime('%d/%m/%Y')}"
        )


# ============================================================
# REGISTRO DE ATIVIDADE DE MEDIAÇÃO
# ============================================================

class AtividadeMediacao(models.Model):

    TURNO_CHOICES = [
        ("MANHA", "Manhã"),
        ("TARDE", "Tarde"),
        ("NOITE", "Noite"),
    ]

    planejamento = models.ForeignKey(
        PlanejamentoMediacao,
        on_delete=models.PROTECT,
        related_name="atividades",
        verbose_name="Planejamento",
        null=True,
        blank=True,
        help_text=(
            "Permite registrar atividades realizadas "
            "sem planejamento prévio."
        )
    )

    escola = models.ForeignKey(
        Escola,
        on_delete=models.PROTECT,
        related_name="atividades_mediacao",
        verbose_name="Escola"
    )

    mediador_responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="atividades_mediacao",
        verbose_name="Mediador responsável"
    )

    data = models.DateField(
        default=timezone.localdate,
        verbose_name="Data da atividade"
    )

    turno = models.CharField(
        max_length=10,
        choices=TURNO_CHOICES,
        verbose_name="Turno"
    )

    diretor = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Diretor(a)"
    )

    coordenador = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Coordenador(a)"
    )

    inspetor_1 = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Inspetor(a) 1"
    )

    inspetor_2 = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Inspetor(a) 2"
    )

    turma = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Turma"
    )

    # ========================================================
    # PÚBLICO ATENDIDO
    # ========================================================

    alunos = models.PositiveIntegerField(
        default=0,
        verbose_name="Alunos atendidos"
    )

    profissionais = models.PositiveIntegerField(
        default=0,
        verbose_name="Profissionais atendidos"
    )

    familiares = models.PositiveIntegerField(
        default=0,
        verbose_name="Familiares atendidos"
    )

    outros_publico = models.PositiveIntegerField(
        default=0,
        verbose_name="Outros participantes"
    )

    quantidade_homens = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantidade de homens (H)"
    )

    quantidade_mulheres = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantidade de mulheres (M)"
    )

    # ========================================================
    # NECESSIDADES ESPECIAIS
    # Siglas preservadas conforme ficha apresentada.
    # ========================================================

    necessidade_nt = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Nt"
    )

    necessidade_aut = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Aut"
    )

    necessidade_df_f = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Df.F"
    )

    necessidade_df_i = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Df.I"
    )

    necessidade_df_v = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Df.V"
    )

    necessidade_outros = models.PositiveIntegerField(
        default=0,
        verbose_name="Necessidades especiais - Out"
    )

    # ========================================================
    # DESCRIÇÃO DA ATIVIDADE
    # ========================================================

    mediadores_presentes = models.TextField(
        verbose_name="Mediadores presentes"
    )

    tema_dinamica = models.TextField(
        verbose_name="Tema e dinâmica"
    )

    fatos_marcantes = models.TextField(
        blank=True,
        verbose_name="Fatos marcantes"
    )

    observacoes = models.TextField(
        blank=True,
        verbose_name="Observações"
    )

    # ========================================================
    # CONTROLE DE DATAS
    # ========================================================

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            "-data",
            "-criado_em",
        ]

        verbose_name = "Atividade de mediação"
        verbose_name_plural = "Atividades de mediação"

    def clean(self):
        super().clean()

        erros = {}

        if self.mediador_responsavel_id:
            if self.mediador_responsavel.perfil != "MEDIADOR":
                erros["mediador_responsavel"] = (
                    "O responsável deve possuir "
                    "o perfil Mediador."
                )

        if self.planejamento_id:

            if (
                self.escola_id
                and self.escola_id != self.planejamento.escola_id
            ):
                erros["escola"] = (
                    "A escola da atividade deve ser "
                    "a mesma escola do planejamento."
                )

            if (
                self.mediador_responsavel_id
                and self.mediador_responsavel_id
                != self.planejamento.mediador_id
            ):
                erros["mediador_responsavel"] = (
                    "O mediador responsável deve ser "
                    "o mesmo do planejamento."
                )

        if erros:
            raise ValidationError(erros)

    @property
    def total_publico(self):
        return (
            self.alunos
            + self.profissionais
            + self.familiares
            + self.outros_publico
        )

    def __str__(self):
        return (
            f"{self.escola.nome} - "
            f"{self.data.strftime('%d/%m/%Y')} - "
            f"{self.get_turno_display()}"
        )

