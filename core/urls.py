from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

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

    path(
        "relatorios/",
        views.relatorios,
        name="relatorios"
    ),
]