
from django.urls import path

from . import views
from . import views_relatorios


app_name = "core"


urlpatterns = [

    # =========================================================
    # PÁGINA INICIAL
    # =========================================================

    path(
        "",
        views.home,
        name="home"
    ),

    # =========================================================
    # AUTENTICAÇÃO
    # =========================================================

    path(
        "login/",
        views.login_view,
        name="login"
    ),

    path(
        "primeiro-acesso/",
        views.primeiro_acesso,
        name="primeiro_acesso"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    # =========================================================
    # DASHBOARDS
    # =========================================================

    path(
        "dashboard/admin/",
        views.dashboard_admin,
        name="dashboard_admin"
    ),

    path(
        "dashboard/coordenador/",
        views.dashboard_coordenador,
        name="dashboard_coordenador"
    ),

    path(
        "dashboard/gcm/",
        views.dashboard_gcm,
        name="dashboard_gcm"
    ),

    path(
        "dashboard/mediador/",
        views.dashboard_mediador,
        name="dashboard_mediador"
    ),

    # =========================================================
    # RELATÓRIOS
    # =========================================================

    # Página principal dos relatórios
    path(
        "relatorios/",
        views_relatorios.relatorios,
        name="relatorios"
    ),

    # Relatório de problemáticas
    path(
        "relatorios/problematicas/",
        views_relatorios.relatorio_problematicas,
        name="relatorio_problematicas"
    ),

    # Relatório de visitas
    path(
        "relatorios/visitas/",
        views_relatorios.relatorio_visitas,
        name="relatorio_visitas"
    ),

    # =========================================================
    # EXPORTAÇÃO DE RELATÓRIOS DE VISITAS
    # =========================================================

    # Exportar todas as visitas filtradas para PDF
    path(
        "relatorios/visitas/pdf/",
        views_relatorios.exportar_visitas_pdf,
        name="exportar_visitas_pdf"
    ),

    # Exportar todas as visitas filtradas para CSV
    path(
        "relatorios/visitas/csv/",
        views_relatorios.exportar_visitas_csv,
        name="exportar_visitas_csv"
    ),

]
