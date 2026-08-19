from django.db import models
from django.contrib.auth.models import User


class Escola(models.Model):

    POLO_CHOICES = [
        (1, "Polo 1"),
        (2, "Polo 2"),
        (3, "Polo 3"),
        (4, "Polo 4"),
        (5, "Polo 5"),
        (6, "Polo 6"),
        (7, "Polo 7"),
        (8, "Polo 8"),
        (9, "Polo 9"),
    ]

    nome = models.CharField(
        max_length=200,
        unique=True
    )

    polo = models.PositiveSmallIntegerField(
        choices=POLO_CHOICES
    )

    endereco = models.CharField(
        max_length=300
    )

    monitoramento = models.BooleanField(
        default=False
    )

    botao_panico = models.BooleanField(
        default=False
    )

    quantidade_alunos = models.PositiveIntegerField(
        default=0
    )

    quantidade_alunos_pcd = models.PositiveIntegerField(
        default=0
    )

    modalidade = models.CharField(
        max_length=200,
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    ativa = models.BooleanField(
        default=True
    )

    data_inativacao = models.DateTimeField(
        blank=True,
        null=True
    )

    inativada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="escolas_inativadas"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.nome

class GestorEscolar(models.Model):

    escola = models.ForeignKey(
        Escola,
        on_delete=models.CASCADE,
        related_name="gestores"
    )

    nome = models.CharField(
        max_length=150
    )

    funcao = models.CharField(
        max_length=100,
        blank=True
    )

    telefone = models.CharField(
        max_length=20,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.nome} - {self.escola.nome}"