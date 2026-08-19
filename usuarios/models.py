from django.db import models
from django.contrib.auth.models import User


class Usuario(models.Model):
    PERFIL_CHOICES = [
        ("ADMIN", "Administrador"),
        ("COORDENADOR", "Coordenador RECOM"),
        ("GCM", "Guarda Civil Municipal"),
        ("MEDIADOR", "Mediador"),
    ]

    SEXO_CHOICES = [
        ("F", "Feminino"),
        ("M", "Masculino"),
        ("O", "Outro"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    nome = models.CharField(max_length=100)

    cpf = models.CharField(
        max_length=14,
        unique=True
    )

    matricula = models.CharField(
        max_length=30,
        unique=True
    )

    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        blank=True,
        null=True
    )

    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    perfil = models.CharField(
        max_length=20,
        choices=PERFIL_CHOICES
    )

    ativo = models.BooleanField(default=True)

    data_inativacao = models.DateTimeField(
        blank=True,
        null=True
    )

    inativado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="usuarios_inativados"
    )

    def __str__(self):
        return f"{self.nome} - {self.matricula}"