
"""
RECOM - Permissões de visitas escolares.

Regras:

1. ADMIN, COORDENADOR e superusuário:
   - Podem editar e excluir qualquer visita.

2. GCM ativo:
   - Pode excluir visitas antigas sem responsável.
   - Pode editar e excluir visitas da equipe
     em que estava escalado na data da visita.

3. Motorista (M):
   - Pode editar e excluir visitas da equipe.
   - A autorização para cadastrar novas visitas
     de missão continua sendo controlada em views.py.

4. Visitas avulsas:
   - A equipe precisa ser comprovada pela escala
     efetiva da data da visita.

5. Visitas de outras equipes:
   - Não podem ser editadas ou excluídas por GCM,
     exceto quando forem visitas legadas.
"""

from datetime import datetime

from django.conf import settings
from django.utils import timezone

from cartao_programa.models import EfetivoViatura
from usuarios.models import Usuario


# =========================================================
# CONFIGURAÇÕES
# =========================================================

CORTE_PADRAO = "2026-11-05T00:00:00-03:00"


# =========================================================
# USUÁRIO RECOM ATIVO
# =========================================================

def usuario_recom_ativo(request):
    """
    Retorna o usuário RECOM ativo vinculado
    ao usuário autenticado do Django.
    """

    if not request.user.is_authenticated:
        return None

    if not request.user.is_active:
        return None

    return Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()


# =========================================================
# ADMINISTRADOR / COORDENADOR
# =========================================================

def gestor_de_visitas(request, usuario=None):
    """
    Verifica se o usuário pode gerenciar
    todas as visitas.
    """

    if not request.user.is_authenticated:
        return False

    if not request.user.is_active:
        return False

    if request.user.is_superuser:
        return True

    if usuario is None:
        usuario = usuario_recom_ativo(request)

    return bool(
        usuario is not None
        and usuario.perfil in (
            "ADMIN",
            "COORDENADOR",
        )
    )


# =========================================================
# DATA DE CORTE DAS VISITAS ANTIGAS
# =========================================================

def limite_visitas_legadas():
    """
    Obtém a data de implantação das novas regras.

    A configuração pode ser definida em:

    core/settings.py

    RECOM_VISITAS_LEGADAS_ATE =
        "2026-11-05T00:00:00-03:00"
    """

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
# IDENTIFICAR VISITAS ANTIGAS
# =========================================================

def visita_legada(visita):
    """
    Considera antigas as visitas criadas antes de
    05/11/2026 e sem responsável identificado.
    """

    data_corte = limite_visitas_legadas()

    return (
        visita.registrado_por_id is None
        and visita.criado_em is not None
        and visita.criado_em < data_corte
    )


# =========================================================
# IDENTIFICAR EQUIPE ESCALADA
# =========================================================

def integrante_da_equipe_na_data(visita, usuario):
    """
    Verifica se o GCM integrava a equipe responsável
    pela visita na data em que ela ocorreu.

    A consulta utiliza EfetivoViatura, preservando
    a escala efetiva registrada para o plantão.
    """

    if usuario is None:
        return False

    if usuario.perfil != "GCM":
        return False

    if visita.data_visita is None:
        return False

    # -----------------------------------------------------
    # ESCALAS DO GCM NA DATA DA VISITA
    # -----------------------------------------------------

    escalas = EfetivoViatura.objects.filter(
        gcm_id=usuario.pk,
        viatura__plantao__data=visita.data_visita,
    )

    # -----------------------------------------------------
    # VISITA VINCULADA A UMA MISSÃO
    # -----------------------------------------------------

    if visita.missao_cartao_id:

        missao = visita.missao_cartao

        # Confirma que missão e viatura pertencem
        # ao mesmo plantão.
        if (
            missao.cartao.plantao_id
            != missao.viatura.plantao_id
        ):
            return False

        # Confirma a data do plantão.
        if (
            missao.viatura.plantao.data
            != visita.data_visita
        ):
            return False

        # Qualquer função da viatura é válida
        # para editar e excluir: C, M, P1, P2.
        return escalas.filter(
            viatura_id=missao.viatura_id
        ).exists()

    # -----------------------------------------------------
    # VISITA AVULSA
    # -----------------------------------------------------

    equipe = str(
        visita.equipe or ""
    ).strip().upper()

    if equipe.startswith("EQUIPE "):
        equipe = equipe.replace(
            "EQUIPE ",
            "",
            1,
        ).strip()

    equipes_validas = (
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
    )

    if equipe not in equipes_validas:
        return False

    # Confirma a equipe da viatura registrada
    # no plantão daquela data.
    return (
        escalas.filter(
            viatura__equipe__nome__iexact=(
                f"Equipe {equipe}"
            )
        ).exists()
        or
        escalas.filter(
            viatura__equipe__nome__iexact=equipe
        ).exists()
    )


# =========================================================
# PERMISSÃO PARA EXCLUIR VISITA
# =========================================================

def pode_excluir_visita(request, visita, usuario=None):
    """
    Regras de exclusão:

    ADMIN / COORDENADOR:
        Podem excluir qualquer visita.

    GCM ativo:
        Pode excluir visitas legadas sem responsável.

        Também pode excluir visitas da equipe
        em que estava escalado na data da visita.

    Outros perfis:
        Sem permissão.
    """

    # -----------------------------------------------------
    # GESTORES
    # -----------------------------------------------------

    if gestor_de_visitas(request, usuario):
        return True

    # -----------------------------------------------------
    # IDENTIFICAR GCM
    # -----------------------------------------------------

    if usuario is None:
        usuario = usuario_recom_ativo(request)

    if usuario is None:
        return False

    if usuario.perfil != "GCM":
        return False

    # -----------------------------------------------------
    # VISITAS ANTIGAS
    # -----------------------------------------------------

    if visita_legada(visita):
        return True

    # -----------------------------------------------------
    # VISITAS DA EQUIPE
    # -----------------------------------------------------

    return integrante_da_equipe_na_data(
        visita,
        usuario,
    )


# =========================================================
# PERMISSÃO PARA EDITAR VISITA
# =========================================================

def pode_editar_visita(request, visita, usuario=None):
    """
    Regras de edição:

    ADMIN / COORDENADOR:
        Podem editar qualquer visita.

    GCM ativo:
        Pode editar visitas da equipe em que
        estava escalado na data da visita.

    Importante:
        Visitas legadas não possuem autorização
        universal para edição.
    """

    # -----------------------------------------------------
    # GESTORES
    # -----------------------------------------------------

    if gestor_de_visitas(request, usuario):
        return True

    # -----------------------------------------------------
    # IDENTIFICAR GCM
    # -----------------------------------------------------

    if usuario is None:
        usuario = usuario_recom_ativo(request)

    if usuario is None:
        return False

    if usuario.perfil != "GCM":
        return False

    # -----------------------------------------------------
    # EQUIPE ESCALADA
    # -----------------------------------------------------

    return integrante_da_equipe_na_data(
        visita,
        usuario,
    )
