
from django.urls import path

from . import views


app_name = "ocorrencias"


urlpatterns = [

    # Listagem de ocorrências
    path(
        "",
        views.listar_ocorrencias,
        name="listar_ocorrencias",
    ),

    # Cadastro de ocorrência
    path(
        "nova/",
        views.cadastrar_ocorrencia,
        name="cadastrar_ocorrencia",
    ),

    # Visualização dos detalhes
    path(
        "<int:pk>/",
        views.detalhe_ocorrencia,
        name="detalhe_ocorrencia",
    ),

    # Edição de ocorrência
    path(
        "<int:pk>/editar/",
        views.editar_ocorrencia,
        name="editar_ocorrencia",
    ),

    # Exclusão de ocorrência
    path(
        "<int:pk>/excluir/",
        views.excluir_ocorrencia,
        name="excluir_ocorrencia",
    ),

]
