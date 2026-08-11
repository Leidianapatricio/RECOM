from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("dashboard/admin/", views.dashboard_admin, name="dashboard_admin"),
    path("dashboard/cidadao/", views.dashboard_cidadao, name="dashboard_cidadao"),
    path("dashboard/profissional/", views.dashboard_profissional, name="dashboard_profissional"),

    path("relatorios/", views.relatorios, name="relatorios"),
]