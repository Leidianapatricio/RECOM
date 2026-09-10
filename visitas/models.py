from django.db import models

from escolas.models import Escola


class RondaVisita(models.Model):

    EQUIPE_CHOICES = [
        ("A", "Equipe A"),
        ("B", "Equipe B"),
        ("C", "Equipe C"),
        ("D", "Equipe D"),
        ("E", "Equipe E"),
        ("F", "Equipe F"),
    ]

    TIPO_VISITA_CHOICES = [
        ("ROTINA", "Visita de rotina"),
        ("SAIDA", "Acompanhamento de saída"),
        ("EVENTO", "Acompanhamento de evento"),
        ("APOIO", "Apoio / atendimento"),
        ("OUTRA", "Outra"),
    ]

    SITUACAO_CHOICES = [
        ("SEM_ALTERACAO", "Sem alteração"),
        ("COM_ALTERACAO", "Com alteração"),
    ]

    escola = models.ForeignKey(
        Escola,
        on_delete=models.PROTECT,
        related_name="visitas",
        verbose_name="Escola",
    )

    equipe = models.CharField(
        max_length=1,
        choices=EQUIPE_CHOICES,
        verbose_name="Equipe responsável",
    )

    data_visita = models.DateField(
        verbose_name="Data da visita",
    )

    horario = models.TimeField(
        verbose_name="Horário",
    )

    tipo_visita = models.CharField(
        max_length=20,
        choices=TIPO_VISITA_CHOICES,
        default="ROTINA",
        verbose_name="Tipo de visita",
    )

    situacao = models.CharField(
        max_length=20,
        choices=SITUACAO_CHOICES,
        default="SEM_ALTERACAO",
        verbose_name="Situação",
    )

    relato = models.TextField(
        blank=True,
        verbose_name="Relato da visita",
    )

    orientacoes = models.TextField(
        blank=True,
        verbose_name="Orientações / providências",
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-data_visita",
            "-horario",
        ]

        verbose_name = "Ronda / Visita"
        verbose_name_plural = "Rondas / Visitas"

    def __str__(self):
        return (
            f"{self.escola.nome} - "
            f"{self.data_visita.strftime('%d/%m/%Y')} - "
            f"Equipe {self.equipe}"
        )