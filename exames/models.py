from django.db import models

from usuarios.models import Usuario
from unidades.models import UnidadeSaude, Profissional


class TipoExame(models.Model):
    nome = models.CharField(
        max_length=100,
        unique=True
    )

    descricao = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return self.nome


class Agendamento(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="agendamentos"
    )

    tipo_exame = models.ForeignKey(
        TipoExame,
        on_delete=models.CASCADE,
        related_name="agendamentos"
    )

    unidade = models.ForeignKey(
        UnidadeSaude,
        on_delete=models.CASCADE,
        related_name="agendamentos"
    )

    data = models.DateField()

    observacao = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.usuario.nome} - {self.tipo_exame.nome} - {self.data}"


class Exame(models.Model):

    STATUS_CHOICES = [
        ("AGENDADO", "Agendado"),
        ("REALIZADO", "Realizado"),
        ("CANCELADO", "Cancelado"),
    ]

    tipo = models.CharField(
        max_length=100
    )

    data = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AGENDADO"
    )

    resultado = models.TextField(
        blank=True,
        null=True
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="exames"
    )

    unidade = models.ForeignKey(
        UnidadeSaude,
        on_delete=models.CASCADE,
        related_name="exames"
    )

    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exames"
    )

    agendamento = models.ForeignKey(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exames"
    )

    def __str__(self):
        return f"{self.tipo} - {self.usuario.nome}"