from django.db import models
from django.contrib.auth.models import User


class Usuario(models.Model):
    PERFIL_CHOICES = [
        ("CIDADAO", "Cidadão"),
        ("PROFISSIONAL", "Profissional de Saúde"),
        ("ADMIN", "Administrador"),
    ]

    SEXO_CHOICES = [
        ("F", "Feminino"),
        ("M", "Masculino"),
        ("O", "Outro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, unique=True)
    cartao_sus = models.CharField(max_length=20, blank=True, null=True)

    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    perfil = models.CharField(
        max_length=20,
        choices=PERFIL_CHOICES,
        default="CIDADAO"
    )

    def __str__(self):
        return self.nome