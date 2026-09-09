from django.contrib import admin

from .models import Escola


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "polo",
        "gestor",
        "telefone",
        "monitoramento",
        "botao_panico",
        "quantidade_alunos",
        "quantidade_alunos_pcd",
        "ativa",
    )

    list_filter = (
        "polo",
        "monitoramento",
        "botao_panico",
        "ativa",
    )

    search_fields = (
        "nome",
        "gestor",
        "endereco",
        "telefone",
    )

    ordering = (
        "polo",
        "nome",
    )