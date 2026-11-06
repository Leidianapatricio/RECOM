
from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "visitas"


urlpatterns = [

    # ==========================================
    # VISITAS - REDIRECIONAR PARA RELATÓRIO
    # ==========================================

    path(
        "",
        RedirectView.as_view(
            pattern_name="core:relatorio_visitas",
            permanent=False,
        ),
        name="listar_visitas",
    ),

    # ==========================================
    # CADASTRAR VISITA
    # ==========================================

    path(
        "nova/",
        views.cadastrar_visita,
        name="cadastrar_visita",
    ),

    # ==========================================
    # CONSULTAR VIATURAS DO PLANTÃO
    # ==========================================

    path(
        "api/viaturas/",
        views.consultar_viaturas_visita,
        name="consultar_viaturas_visita",
    ),

    # ==========================================
    # EXCLUIR VISITA
    # ==========================================

    path(
        "<int:pk>/excluir/",
        views.excluir_visita,
        name="excluir_visita",
    ),

    # ==========================================
    # EDITAR VISITA
    # ==========================================

    path(
        "editar/<int:pk>/",
        views.editar_visita,
        name="editar_visita",
    ),

]
