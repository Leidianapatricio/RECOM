from django.urls import path
from . import views

app_name = "unidades"

urlpatterns = [

    # UNIDADES
    path("", views.listar_unidades, name="listar"),
    path("nova/", views.criar_unidade, name="criar"),
    path("<int:id>/editar/", views.editar_unidade, name="editar"),
    path("<int:id>/excluir/", views.excluir_unidade, name="excluir"),

    # PROFISSIONAIS
    path("profissionais/", views.listar_profissionais, name="listar_profissionais"),
    path("profissionais/novo/", views.criar_profissional, name="criar_profissional"),
    path("profissionais/<int:id>/editar/", views.editar_profissional, name="editar_profissional"),
    path("profissionais/<int:id>/excluir/", views.excluir_profissional, name="excluir_profissional"),
]