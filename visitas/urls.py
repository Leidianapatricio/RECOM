from django.urls import path

from . import views


app_name = "visitas"


urlpatterns = [

    path(
        "nova/",
        views.cadastrar_visita,
        name="cadastrar_visita",
    ),

    path(
        "<int:pk>/excluir/",
        views.excluir_visita,
        name="excluir_visita",
    ),
    
    path(
    "editar/<int:pk>/",
    views.editar_visita,
    name="editar_visita",
    ),

]