from django.contrib import admin

from .models import Escola, GestorEscolar


class GestorEscolarInline(admin.TabularInline):
    model = GestorEscolar
    extra = 1


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "polo",
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
        "endereco",
    )

    ordering = (
        "polo",
        "nome",
    )

    inlines = [
        GestorEscolarInline,
    ]


@admin.register(GestorEscolar)
class GestorEscolarAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "escola",
        "funcao",
        "telefone",
        "ativo",
    )

    list_filter = (
        "ativo",
        "escola__polo",
    )

    search_fields = (
        "nome",
        "escola__nome",
        "telefone",
    )

    ordering = (
        "escola__nome",
        "nome",
    )


