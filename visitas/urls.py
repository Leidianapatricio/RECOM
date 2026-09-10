from django.urls import path

from . import views


app_name = "visitas"


urlpatterns = [
    path(
        "nova/",
        views.cadastrar_visita,
        name="cadastrar_visita",
    ),
]