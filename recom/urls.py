
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),

    path(
        "",
        include("core.urls"),
    ),

    path(
        "usuarios/",
        include("usuarios.urls"),
    ),

    path(
        "escolas/",
        include("escolas.urls"),
    ),

    path(
        "visitas/",
        include("visitas.urls"),
    ),

    path(
        "cartao-programa/",
        include("cartao_programa.urls"),
    ),

    path(
        "admin/",
        admin.site.urls,
    ),
    
    path(
    "mediacao/",
    include("mediacao.urls")
    ),
    
    path(
    "ocorrencias/",
    include("ocorrencias.urls"),
    ),
]
