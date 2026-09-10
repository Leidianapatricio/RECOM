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
    
    path(
    "<int:pk>/problematicas/nova/",
    views.cadastrar_problematica,
    name="cadastrar_problematica"
    ),
    
    path(
    "<int:pk>/editar/",
    views.editar_escola,
    name="editar_escola"
    ),

    path(
    "<int:pk>/desativar/",
    views.desativar_escola,
    name="desativar_escola"
    ),

    path(
    "<int:pk>/ativar/",
    views.ativar_escola,
    name="ativar_escola"
    ),
]