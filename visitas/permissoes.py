"""Permissões de edição e exclusão das visitas escolares do RECOM.

Visitas criadas antes de 05/11/2026 são legadas, mesmo com autor identificado.
Visitas criadas a partir dessa data exigem escala na equipe/viatura da visita.
As regras de CADASTRO de novas visitas continuam em visitas/views.py.
"""

from datetime import datetime

from django.conf import settings
from django.utils import timezone

from cartao_programa.models import EfetivoViatura
from usuarios.models import Usuario

CORTE_PADRAO = "2026-11-05T00:00:00-03:00"


def usuario_recom_ativo(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return None
    return Usuario.objects.filter(user=request.user, ativo=True).first()


def gestor_de_visitas(request, usuario=None):
    if not request.user.is_authenticated or not request.user.is_active:
        return False
    if request.user.is_superuser:
        return True
    if usuario is None:
        usuario = usuario_recom_ativo(request)
    return bool(usuario is not None and usuario.ativo and usuario.perfil in ("ADMIN", "COORDENADOR"))


def limite_visitas_legadas():
    valor = getattr(settings, "RECOM_VISITAS_LEGADAS_ATE", CORTE_PADRAO)
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if timezone.is_naive(valor):
        valor = timezone.make_aware(valor, timezone.get_current_timezone())
    return valor


def visita_legada(visita):
    """Toda visita CRIADA antes do corte é legada, com ou sem responsável."""
    criado_em = visita.criado_em
    if criado_em is None:
        return False
    if timezone.is_naive(criado_em):
        criado_em = timezone.make_aware(criado_em, timezone.get_current_timezone())
    return criado_em < limite_visitas_legadas()


def integrante_da_equipe_na_data(visita, usuario):
    """Confirma a escala efetiva da data da visita, inclusive para motorista."""
    if usuario is None or not usuario.ativo or usuario.perfil != "GCM":
        return False
    if visita.data_visita is None:
        return False

    escalas = EfetivoViatura.objects.filter(
        gcm_id=usuario.pk,
        viatura__plantao__data=visita.data_visita,
    )

    if visita.missao_cartao_id:
        missao = visita.missao_cartao
        if missao.cartao.plantao_id != missao.viatura.plantao_id:
            return False
        if missao.viatura.plantao.data != visita.data_visita:
            return False
        return escalas.filter(viatura_id=missao.viatura_id).exists()

    # Visita avulsa: quando há viatura vinculada, exigir a mesma viatura.
    # Isso impede que a escala em outra viatura da mesma equipe conceda acesso.
    if visita.viatura_id is not None:
        return escalas.filter(viatura_id=visita.viatura_id).exists()

    equipe = str(visita.equipe or "").strip().upper()
    if equipe.startswith("EQUIPE "):
        equipe = equipe[7:].strip()
    if equipe not in ("A", "B", "C", "D", "E", "F"):
        return False

    return (
        escalas.filter(viatura__equipe__nome__iexact=f"Equipe {equipe}").exists()
        or escalas.filter(viatura__equipe__nome__iexact=equipe).exists()
    )


def _pode_alterar_visita(request, visita, usuario=None):
    if gestor_de_visitas(request, usuario):
        return True
    if usuario is None:
        usuario = usuario_recom_ativo(request)
    if usuario is None or not usuario.ativo or usuario.perfil != "GCM":
        return False
    if visita_legada(visita):
        return True
    return integrante_da_equipe_na_data(visita, usuario)


def pode_editar_visita(request, visita, usuario=None):
    return _pode_alterar_visita(request, visita, usuario)


def pode_excluir_visita(request, visita, usuario=None):
    return _pode_alterar_visita(request, visita, usuario)
