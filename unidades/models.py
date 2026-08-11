from django.db import models
from django.contrib.auth.models import User


class UnidadeSaude(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=200)
    contato = models.CharField(max_length=50)

    def __str__(self):
        return self.nome


class Profissional(models.Model):

    CONSELHO_CHOICES = [
        ("CRM", "CRM"),
        ("COREN", "COREN"),
        ("CRO", "CRO"),
        ("CRF", "CRF"),
        ("CRBM", "CRBM"),
        ("OUTRO", "Outro"),
    ]

    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, unique=True)

    conselho = models.CharField(
        max_length=10,
        choices=CONSELHO_CHOICES
    )

    registro = models.CharField(max_length=30)

    especialidade = models.CharField(max_length=100)

    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    unidade = models.ForeignKey(
        UnidadeSaude,
        on_delete=models.CASCADE,
        related_name="profissionais"
    )

    def __str__(self):
        return self.nome