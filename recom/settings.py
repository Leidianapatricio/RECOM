"""
Django settings for recom project.

Projeto RECOM - Ronda Escolar Comunitária
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# CAMINHO BASE DO PROJETO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# CARREGAR VARIÁVEIS DO .ENV
# ============================================================

# No computador local, utiliza o arquivo .env.
# Na Vercel, as variáveis serão configuradas pelo painel.
load_dotenv(BASE_DIR / ".env")


# ============================================================
# AMBIENTE
# ============================================================

# A Vercel disponibiliza VERCEL=1 automaticamente.
IS_VERCEL = os.getenv("VERCEL") == "1"


# ============================================================
# CONFIGURAÇÕES BÁSICAS
# ============================================================

# Em produção a chave será definida pela variável
# DJANGO_SECRET_KEY no painel da Vercel.
#
# A chave abaixo é apenas para desenvolvimento local.
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-chave-apenas-para-desenvolvimento-local",
)


# DEBUG:
#
# Localmente:
# DEBUG=True por padrão.
#
# Na Vercel:
# DEBUG=False automaticamente.
if IS_VERCEL:
    DEBUG = False
else:
    DEBUG = os.getenv(
        "DJANGO_DEBUG",
        "True"
    ).lower() in (
        "true",
        "1",
        "yes",
    )


# ============================================================
# HOSTS PERMITIDOS
# ============================================================

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".vercel.app",
]


# Permite acrescentar outros hosts através do .env
# ou das variáveis da Vercel.
EXTRA_ALLOWED_HOSTS = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    ""
)

if EXTRA_ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(
        host.strip()
        for host in EXTRA_ALLOWED_HOSTS.split(",")
        if host.strip()
    )


# URL específica gerada pela Vercel.
VERCEL_URL = os.getenv("VERCEL_URL")

if VERCEL_URL:
    ALLOWED_HOSTS.append(VERCEL_URL)


# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
]


EXTRA_CSRF_ORIGINS = os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ""
)

if EXTRA_CSRF_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(
        origin.strip()
        for origin in EXTRA_CSRF_ORIGINS.split(",")
        if origin.strip()
    )


# ============================================================
# APLICAÇÕES INSTALADAS
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps do projeto RECOM
    "core",
    "usuarios",
    "escolas",
    "cartao_programa",
    "visitas",
    "ocorrencias",
    "acoes_educativas",
    "mediacao",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URLS
# ============================================================

ROOT_URLCONF = "recom.urls"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "recom.wsgi.application"


# ============================================================
# BANCO DE DADOS
# POSTGRESQL
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",

        "NAME": os.getenv(
            "POSTGRES_DB",
            "Recom",
        ),

        "USER": os.getenv(
            "POSTGRES_USER",
            "postgres",
        ),

        "PASSWORD": os.getenv(
            "POSTGRES_PASSWORD",
            "",
        ),

        "HOST": os.getenv(
            "POSTGRES_HOST",
            "localhost",
        ),

        "PORT": os.getenv(
            "POSTGRES_PORT",
            "5433",
        ),

        # Em aplicações serverless é melhor não manter
        # conexões persistentes entre execuções.
        "CONN_MAX_AGE": 0,
    }
}


# ============================================================
# SSL DO POSTGRESQL
# ============================================================

# O Supabase exige conexão segura.
#
# Localmente esta configuração não é aplicada,
# a menos que POSTGRES_SSLMODE seja definida.

POSTGRES_SSLMODE = os.getenv(
    "POSTGRES_SSLMODE",
    ""
)

if POSTGRES_SSLMODE:
    DATABASES["default"]["OPTIONS"] = {
        "sslmode": POSTGRES_SSLMODE,
    }


# ============================================================
# VALIDAÇÃO DE SENHAS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNACIONALIZAÇÃO
# ============================================================

LANGUAGE_CODE = "pt-br"

LANGUAGES = [
    ("pt-br", "Português do Brasil"),
    ("en", "English"),
]

TIME_ZONE = "America/Fortaleza"

USE_I18N = True

USE_TZ = True


# ============================================================
# ARQUIVOS DE TRADUÇÃO
# ============================================================

LOCALE_PATHS = [
    BASE_DIR / "locale",
]


# ============================================================
# ARQUIVOS ESTÁTICOS
# ============================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA PARA PRODUÇÃO
# ============================================================

if IS_VERCEL:

    # Informa ao Django que a requisição original
    # foi realizada via HTTPS.
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True


# ============================================================
# TIPO PADRÃO DE CHAVE PRIMÁRIA
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"