from django.urls import path

from . import views


app_name = "mediacao"


urlpatterns = [

    # ==========================================
    # PLANEJAMENTO DE MEDIAÇÃO
    # ==========================================

    path(
        "planejar/",
        views.planejar_mediacao,
        name="planejar_mediacao"
    ),

    path(
        "planejamentos/",
        views.listar_planejamentos,
        name="listar_planejamentos"
    ),

    path(
        "planejamentos/<int:pk>/editar/",
        views.editar_planejamento,
        name="editar_planejamento"
    ),

    # ==========================================
    # ATIVIDADES DE MEDIAÇÃO
    # ==========================================

    path(
        "atividades/registrar/",
        views.registrar_atividade,
        name="registrar_atividade"
    ),

    path(
        "atividades/",
        views.listar_atividades,
        name="listar_atividades"
    ),

    path(
        "atividades/<int:pk>/",
        views.detalhe_atividade,
        name="detalhe_atividade"
    ),

    path(
        "atividades/<int:pk>/editar/",
        views.editar_atividade,
        name="editar_atividade"
    ),

]