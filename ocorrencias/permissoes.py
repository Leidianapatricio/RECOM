from django.db.models import Q
from django.http import Http404

from cartao_programa.models import (
    CartaoPrograma,
    EfetivoViatura,
)

from usuarios.models import Usuario


# ==========================================================
# IDENTIFICAR USUÁRIO
# ==========================================================

def obter_usuario_recom(request):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return None

    return Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()


# ==========================================================
# PERMISSÕES DOS GESTORES
# ==========================================================

def pode_gerenciar_ocorrencias(request, usuario=None):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    if request.user.is_superuser:
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return bool(
        usuario
        and usuario.ativo
        and usuario.perfil in (
            "ADMIN",
            "COORDENADOR",
        )
    )


# ==========================================================
# PERMISSÃO DE CONSULTA
# ==========================================================

def pode_consultar_ocorrencias(request, usuario=None):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    if pode_gerenciar_ocorrencias(request, usuario):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return bool(
        usuario
        and usuario.ativo
        and usuario.perfil in (
            "GCM",
            "MEDIADOR",
        )
    )


# ==========================================================
# PERMISSÃO DE CADASTRO
# ==========================================================

def pode_cadastrar_ocorrencias(request, usuario=None):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    if pode_gerenciar_ocorrencias(request, usuario):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return bool(
        usuario
        and usuario.ativo
        and usuario.perfil == "GCM"
    )


# ==========================================================
# CARTÕES PROGRAMA AUTORIZADOS
# ==========================================================

def cartoes_disponiveis(request, usuario=None, data=None):

    cartoes = CartaoPrograma.objects.none()

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return cartoes

    if usuario is None:
        usuario = obter_usuario_recom(request)

    if pode_gerenciar_ocorrencias(request, usuario):

        cartoes = CartaoPrograma.objects.all()

    elif (
        usuario
        and usuario.ativo
        and usuario.perfil == "GCM"
    ):

        cartoes = CartaoPrograma.objects.filter(
            plantao__viaturas__efetivo__gcm=usuario
        ).distinct()

    if data is not None:

        cartoes = cartoes.filter(
            plantao__data=data
        )

    return (
        cartoes
        .select_related("plantao")
        .order_by(
            "-plantao__data",
            "-pk",
        )
    )


# ==========================================================
# VERIFICAR INTEGRANTE DO CARTÃO PROGRAMA
# ==========================================================

def integrante_do_cartao_programa(
    usuario,
    cartao_programa,
):

    if (
        usuario is None
        or not usuario.ativo
        or usuario.perfil != "GCM"
        or cartao_programa is None
    ):
        return False

    return EfetivoViatura.objects.filter(
        gcm=usuario,
        viatura__plantao_id=cartao_programa.plantao_id,
    ).exists()


# ==========================================================
# FILTRO DE OCORRÊNCIAS AUTORIZADAS
# ==========================================================

def filtro_ocorrencias_gcm(usuario):

    if (
        usuario is None
        or not usuario.ativo
        or usuario.perfil != "GCM"
    ):
        return Q(pk__in=[])

    escalas = EfetivoViatura.objects.filter(
        gcm=usuario
    )

    plantoes = escalas.values(
        "viatura__plantao_id"
    )

    viaturas = escalas.values(
        "viatura_id"
    )

    return (

        # Ocorrências registradas pelo próprio GCM.

        Q(
            registrado_por_id=usuario.user_id
        )

        # Ocorrências compartilhadas pelo Cartão Programa.

        | Q(
            cartao_programa__isnull=False,
            cartao_programa__plantao_id__in=plantoes,
        )

        # Ocorrências antigas vinculadas à viatura.

        | Q(
            cartao_programa__isnull=True,
            viatura_id__in=viaturas,
        )

    )


# ==========================================================
# FILTRAR OCORRÊNCIAS POR USUÁRIO
# ==========================================================

def filtrar_ocorrencias(
    request,
    queryset,
    usuario=None,
):

    if not pode_consultar_ocorrencias(
        request,
        usuario,
    ):
        return queryset.none()

    if pode_gerenciar_ocorrencias(
        request,
        usuario,
    ):
        return queryset

    if usuario is None:
        usuario = obter_usuario_recom(request)

    # Preserva a consulta do perfil MEDIADOR.

    if usuario and usuario.perfil == "MEDIADOR":
        return queryset

    return queryset.filter(
        filtro_ocorrencias_gcm(usuario)
    ).distinct()


# ==========================================================
# PERMISSÃO DE VISUALIZAÇÃO INDIVIDUAL
# ==========================================================

def pode_visualizar_ocorrencia(
    request,
    ocorrencia,
    usuario=None,
):

    if not pode_consultar_ocorrencias(
        request,
        usuario,
    ):
        return False

    if pode_gerenciar_ocorrencias(
        request,
        usuario,
    ):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    if usuario and usuario.perfil == "MEDIADOR":
        return True

    return pode_editar_ocorrencia(
        request,
        ocorrencia,
        usuario,
    )


# ==========================================================
# PERMISSÃO DE EDIÇÃO
# ==========================================================

def pode_editar_ocorrencia(
    request,
    ocorrencia,
    usuario=None,
):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return False

    if pode_gerenciar_ocorrencias(
        request,
        usuario,
    ):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    if (
        usuario is None
        or not usuario.ativo
        or usuario.perfil != "GCM"
    ):
        return False

    # ------------------------------------------------------
    # AUTOR ORIGINAL
    # ------------------------------------------------------

    if ocorrencia.registrado_por_id == request.user.pk:
        return True

    # ------------------------------------------------------
    # INTEGRANTES DO MESMO CARTÃO PROGRAMA
    # ------------------------------------------------------

    if ocorrencia.cartao_programa_id:

        return integrante_do_cartao_programa(
            usuario,
            ocorrencia.cartao_programa,
        )

    # ------------------------------------------------------
    # OCORRÊNCIAS ANTIGAS VINCULADAS À VIATURA
    # ------------------------------------------------------

    if ocorrencia.viatura_id:

        return EfetivoViatura.objects.filter(
            gcm=usuario,
            viatura_id=ocorrencia.viatura_id,
        ).exists()

    return False


# ==========================================================
# PERMISSÃO DE EXCLUSÃO
# ==========================================================

def pode_excluir_ocorrencia(
    request,
    ocorrencia,
    usuario=None,
):

    return pode_editar_ocorrencia(
        request,
        ocorrencia,
        usuario,
    )


# ==========================================================
# BLOQUEAR ACESSO NÃO AUTORIZADO
# ==========================================================

def verificar_permissao(permitido):

    if not permitido:

        raise Http404(
            "Ocorrência não encontrada "
            "ou acesso não autorizado."
        )