from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),

    path("", include("core.urls")),
    path("usuarios/", include("usuarios.urls")),

    path("admin/", admin.site.urls),
]