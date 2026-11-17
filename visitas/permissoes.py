"""Permissões compartilhadas de visitas escolares do RECOM."""

from datetime import datetime

from django.conf import settings
from django.db.models import Q, F
from django.utils import timezone

from cartao_programa.models import (
    CartaoPrograma,
    EfetivoViatura,
)

from usuarios.models import Usuario


CORTE_PADRAO = "2026-11-05T00:00:00-03:00"

CORTE_VISITAS_AVULSAS = "2026-11-16T00:00:00-03:00"


# =========================================================
# IDENTIFICAR USUÁRIO ATIVO
# =========================================================

def usuario_recom_ativo(request):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return None

    return Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()


# =========================================================
# ADMINISTRADOR E COORDENADOR
# =========================================================

def gestor_de_visitas(request, usuario=None):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    if request.user.is_superuser:
        return True

    usuario = usuario or usuario_recom_ativo(request)

    return bool(
        usuario
        and usuario.ativo
        and usuario.user_id == request.user.pk
        and usuario.perfil in (
            "ADMIN",
            "COORDENADOR",
        )
    )


# =========================================================
# DATA LIMITE DAS VISITAS LEGADAS
# =========================================================

def limite_visitas_legadas():

    valor = getattr(
        settings,
        "RECOM_VISITAS_LEGADAS_ATE",
        CORTE_PADRAO,
    )

    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)

    if timezone.is_naive(valor):

        valor = timezone.make_aware(
            valor,
            timezone.get_current_timezone(),
        )

    return valor


# =========================================================
# IDENTIFICAR VISITAS LEGADAS
# =========================================================

def visita_legada(visita):

    criado = visita.criado_em

    if criado is None:
        return False

    if timezone.is_naive(criado):

        criado = timezone.make_aware(
            criado,
            timezone.get_current_timezone(),
        )

    # Visitas avulsas criadas até 15/11/2026.
    if not visita.missao_cartao_id:

        limite = datetime.fromisoformat(
            CORTE_VISITAS_AVULSAS
        )

    else:

        # Preserva a regra das visitas programadas.
        limite = limite_visitas_legadas()

    return criado < limite


# =========================================================
# CARTÕES PROGRAMA DISPONÍVEIS
# =========================================================

def cartoes_disponiveis(usuario_auth):

    qs = CartaoPrograma.objects.select_related(
        "plantao"
    )

    if (
        not usuario_auth
        or not usuario_auth.is_authenticated
        or not usuario_auth.is_active
    ):
        return qs.none()

    if usuario_auth.is_superuser:
        return qs

    usuario = Usuario.objects.filter(
        user=usuario_auth,
        ativo=True,
    ).first()

    if not usuario:
        return qs.none()

    if usuario.perfil in (
        "ADMIN",
        "COORDENADOR",
    ):
        return qs

    if usuario.perfil != "GCM":
        return qs.none()

    return qs.filter(
        plantao_id__in=EfetivoViatura.objects.filter(
            gcm_id=usuario.pk
        ).values(
            "viatura__plantao_id"
        )
    )


# =========================================================
# VERIFICAR EFETIVO DO CARTÃO PROGRAMA
# =========================================================

def integrante_do_cartao_programa(
    cartao_programa,
    usuario,
):

    return bool(
        usuario
        and usuario.ativo
        and usuario.perfil == "GCM"
        and cartao_programa
        and EfetivoViatura.objects.filter(
            gcm_id=usuario.pk,
            viatura__plantao_id=cartao_programa.plantao_id,
        ).exists()
    )


# =========================================================
# VERIFICAR ESCALA DA VISITA
# =========================================================

def integrante_da_equipe_na_data(
    visita,
    usuario,
):

    if (
        not usuario
        or not usuario.ativo
        or usuario.perfil != "GCM"
        or not visita.data_visita
    ):
        return False

    # -----------------------------------------------------
    # VISITAS PROGRAMADAS
    # -----------------------------------------------------

    if visita.missao_cartao_id:

        missao = visita.missao_cartao

        return (
            missao.cartao.plantao_id
            == missao.viatura.plantao_id

            and missao.cartao.plantao.data
            == visita.data_visita

            and EfetivoViatura.objects.filter(
                gcm_id=usuario.pk,
                viatura_id=missao.viatura_id,
            ).exists()
        )

    # -----------------------------------------------------
    # VISITAS AVULSAS
    # -----------------------------------------------------

    if visita.cartao_programa_id:

        cartao = visita.cartao_programa

        return (
            cartao.plantao.data
            == visita.data_visita

            and integrante_do_cartao_programa(
                cartao,
                usuario,
            )
        )

    return False


# =========================================================
# PERMISSÕES DE EDIÇÃO E EXCLUSÃO
# =========================================================

def _pode_alterar_visita(
    request,
    visita,
    usuario=None,
):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    # ADMINISTRADOR E COORDENADOR
    if gestor_de_visitas(request, usuario):
        return True

    usuario = usuario or usuario_recom_ativo(request)

    if (
        not usuario
        or not usuario.ativo
        or usuario.user_id != request.user.pk
        or usuario.perfil != "GCM"
    ):
        return False

    # VISITAS LEGADAS
    if visita_legada(visita):
        return True

    # AUTOR DA VISITA AVULSA
    # Pode editar e excluir, mesmo sem Cartão Programa.

    if (
        not visita.missao_cartao_id
        and visita.registrado_por_id == usuario.pk
    ):
        return True

    # INTEGRANTES DA ESCALA
    return integrante_da_equipe_na_data(
        visita,
        usuario,
    )


# =========================================================
# PERMISSÃO PARA EDITAR
# =========================================================

def pode_editar_visita(
    request,
    visita,
    usuario=None,
):

    return _pode_alterar_visita(
        request,
        visita,
        usuario,
    )


# =========================================================
# PERMISSÃO PARA EXCLUIR
# =========================================================

def pode_excluir_visita(
    request,
    visita,
    usuario=None,
):

    return _pode_alterar_visita(
        request,
        visita,
        usuario,
    )


# =========================================================
# FILTRO DAS VISITAS AVULSAS
# HISTÓRICO DE ATIVIDADES E EXPORTAÇÕES
# =========================================================

def filtro_visitas_avulsas_gcm(usuario):

    if (
        not usuario
        or not usuario.ativo
        or usuario.perfil != "GCM"
    ):
        return Q(pk__in=[])

    plantoes = EfetivoViatura.objects.filter(
        gcm_id=usuario.pk
    ).values(
        "viatura__plantao_id"
    )

    return Q(
        missao_cartao__isnull=True
    ) & (

        # Visitas avulsas legadas.
        Q(
            criado_em__lt=datetime.fromisoformat(
                CORTE_VISITAS_AVULSAS
            )
        )

        # Visitas registradas pelo próprio GCM.
        | Q(
            registrado_por_id=usuario.pk
        )

        # Visitas dos integrantes do mesmo cartão.
        | Q(
            cartao_programa__plantao_id__in=plantoes,
            cartao_programa__plantao__data=F(
                "data_visita"
            ),
        )
    )