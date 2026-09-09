from django.urls import path

from . import views

app_name = "escolas"

urlpatterns = [
    path(
        "",
        views.listar_escolas,
        name="listar_escolas",
    ),
    path(
        "nova/",
        views.cadastrar_escola,
        name="cadastrar_escola",
    ),
    path(
        "<int:pk>/",
        views.detalhe_escola,
        name="detalhe_escola",
    ),
]