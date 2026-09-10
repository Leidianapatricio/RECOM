from django.contrib import admin

from .models import Escola, EscolaProblematica, TipoProblematica


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


@admin.register(TipoProblematica)
class TipoProblematicaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "ativa",
        "criado_em",
    )

    list_filter = (
        "ativa",
    )

    search_fields = (
        "nome",
        "descricao",
    )

    ordering = (
        "nome",
    )


@admin.register(EscolaProblematica)
class EscolaProblematicaAdmin(admin.ModelAdmin):
    list_display = (
        "escola",
        "tipo_problematica",
        "situacao",
        "data_registro",
    )

    list_filter = (
        "situacao",
        "tipo_problematica",
        "escola__polo",
    )

    search_fields = (
        "escola__nome",
        "tipo_problematica__nome",
        "observacoes",
    )

    ordering = (
        "escola__nome",
        "tipo_problematica__nome",
    )

    autocomplete_fields = (
        "escola",
        "tipo_problematica",
    )