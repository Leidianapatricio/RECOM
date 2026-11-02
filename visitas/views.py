
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cartao_programa.models import EfetivoViatura, MissaoCartao
from usuarios.models import Usuario

from .forms import RondaVisitaForm, dados_da_missao
from .models import RondaVisita


# =========================================================
# FUNÇÕES AUXILIARES - CONTROLE DE ACESSO
# =========================================================

def obter_usuario_recom(request):
    """
    Retorna o usuário RECOM vinculado ao usuário Django.

    Superusuários Django podem não possuir cadastro
    no modelo Usuario.
    """

    if not request.user.is_authenticated:
        raise PermissionDenied(
            "É necessário estar autenticado."
        )

    if not request.user.is_active:
        raise PermissionDenied(
            "Usuário inativo."
        )

    usuario = Usuario.objects.filter(
        user=request.user
    ).first()

    if usuario is None or not usuario.ativo:

        if request.user.is_superuser:
            return None

        raise PermissionDenied(
            "Usuário RECOM não encontrado ou inativo."
        )

    return usuario


def pode_gerenciar_visitas(request):
    """
    Administradores e coordenadores podem
    gerenciar os registros de visitas.
    """

    usuario = obter_usuario_recom(request)

    if request.user.is_superuser:
        return True

    return (
        usuario is not None
        and usuario.perfil in [
            "ADMIN",
            "COORDENADOR",
        ]
    )


def validar_acesso_missao(request, missao):
    """
    Verifica se o GCM pode registrar visitas
    vinculadas à missão do Cartão Programa.

    C  = Comandante: permitido
    M  = Motorista: não permitido
    P1 = Patrulheiro 1: permitido
    P2 = Patrulheiro 2: permitido
    """

    # Confere a integridade do vínculo entre
    # missão, cartão e plantão da viatura.
    if (
        missao.cartao.plantao_id
        != missao.viatura.plantao_id
    ):
        raise PermissionDenied(
            "A missão não corresponde ao plantão "
            "da viatura."
        )

    # Administradores e coordenadores podem
    # gerenciar visitas vinculadas às missões.
    if pode_gerenciar_visitas(request):
        return

    usuario = obter_usuario_recom(request)

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para "
            "registrar visitas nesta missão."
        )

    # A função considerada é a função do GCM
    # na viatura deste plantão, e não sua
    # função habitual na equipe.
    escala = EfetivoViatura.objects.filter(
        viatura_id=missao.viatura_id,
        gcm=usuario,
    ).first()

    if escala is None:
        raise PermissionDenied(
            "Esta missão não pertence à sua escala."
        )

    if escala.funcao == "M":
        raise PermissionDenied(
            "O Motorista possui acesso somente "
            "de visualização às missões. "
            "O registro de visitas é reservado "
            "ao Comandante e aos Patrulheiros."
        )

    if escala.funcao not in ["C", "P1", "P2"]:
        raise PermissionDenied(
            "Sua função não permite registrar "
            "visitas nesta missão."
        )


def obter_missao_autorizada(request, missao_id):
    """
    Recupera a missão e verifica as permissões
    do usuário antes de permitir o registro.
    """

    missao = get_object_or_404(
        MissaoCartao.objects.select_related(
            "escola",
            "viatura",
            "cartao__plantao",
        ),
        pk=missao_id,
    )

    validar_acesso_missao(
        request,
        missao
    )

    if missao.escola_id is None:
        raise PermissionDenied(
            "Esta missão não possui escola "
            "vinculada para registrar visita."
        )

    return missao


def adicionar_erros_modelo(form, erro):
    """
    Exibe os erros do full_clean() diretamente
    no formulário, quando possível.
    """

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():

            if campo in form.fields:
                form.add_error(
                    campo,
                    erros
                )

            else:
                form.add_error(
                    None,
                    erros
                )

    else:
        form.add_error(
            None,
            erro
        )


def redirecionar_apos_visita(request, visita):
    """
    Define o destino após cadastrar ou editar.

    GCM que registrou uma missão retorna
    ao próprio Cartão Programa.

    Visitas avulsas e registros administrativos
    retornam ao detalhe da escola.
    """

    usuario = obter_usuario_recom(request)

    if (
        visita.missao_cartao_id
        and usuario is not None
        and usuario.perfil == "GCM"
    ):
        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    return redirect(
        "escolas:detalhe_escola",
        pk=visita.escola_id
    )


# =========================================================
# CADASTRAR VISITA
# =========================================================

@login_required
def cadastrar_visita(request):
    """
    Registra visitas avulsas ou uma única visita
    vinculada a cada missão do Cartão Programa.

    Regras:
    - C, P1 e P2 podem registrar visitas.
    - Motorista não pode registrar visitas.
    - Uma missão permite somente uma visita.
    - Missões não realizadas não permitem visitas.
    - Ao registrar a visita, a missão fica REALIZADA.
    - Visitas avulsas continuam independentes.
    """

    usuario = obter_usuario_recom(request)

    # ==========================================
    # IDENTIFICAR A MISSÃO
    # ==========================================

    missao_id = (
        request.POST.get(
            "missao_cartao_id", ""
        ).strip()
        if request.method == "POST"
        else request.GET.get(
            "missao", ""
        ).strip()
    )

    missao = (
        obter_missao_autorizada(
            request,
            missao_id
        )
        if missao_id
        else None
    )

    # ==========================================
    # VERIFICAÇÃO INICIAL
    # ==========================================

    if missao is not None:

        visita_existente = RondaVisita.objects.filter(
            missao_cartao_id=missao.pk
        ).exists()

        if (
            missao.status_execucao != "PENDENTE"
            or visita_existente
        ):
            messages.warning(
                request,
                "Esta missão já possui um resultado registrado."
            )

            return redirect(
                "cartao_programa:meu_cartao_programa"
            )

    # ==========================================
    # CADASTRAR VIA POST
    # ==========================================

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            missao=missao
        )

        if form.is_valid():

            try:

                with transaction.atomic():

                    # ==================================
                    # BLOQUEAR MISSÃO DURANTE O REGISTRO
                    # ==================================

                    if missao is not None:

                        # Bloqueia somente a linha da missão.
                        # Não realiza JOIN com campos opcionais.
                        missao_bloqueada = get_object_or_404(
                            MissaoCartao.objects.select_for_update(
                                of=("self",)
                            ),
                            pk=missao.pk
                        )

                        # Revalida a permissão do usuário.
                        validar_acesso_missao(
                            request,
                            missao_bloqueada
                        )

                        # Impede registro em missão
                        # já realizada ou não realizada.
                        if (
                            missao_bloqueada.status_execucao
                            != "PENDENTE"
                        ):
                            raise ValidationError(
                                "Esta missão já possui um "
                                "resultado registrado."
                            )

                        # Impede duplicidade mesmo quando
                        # dois GCMs tentam salvar juntos.
                        visita_existente = (
                            RondaVisita.objects.filter(
                                missao_cartao_id=missao_bloqueada.pk
                            ).exists()
                        )

                        if visita_existente:
                            raise ValidationError(
                                "Já existe uma visita registrada "
                                "para esta missão."
                            )

                        missao = missao_bloqueada

                    # ==================================
                    # PREPARAR VISITA
                    # ==================================

                    visita = form.save(
                        commit=False
                    )

                    # O vínculo é definido pelo servidor.
                    visita.missao_cartao = missao

                    if missao is not None:

                        # Preserva escola, equipe e data
                        # determinadas pelo Cartão Programa.
                        for campo, valor in dados_da_missao(
                            missao
                        ).items():

                            setattr(
                                visita,
                                campo,
                                valor
                            )

                    # ==================================
                    # VALIDAR E SALVAR VISITA
                    # ==================================

                    visita.full_clean()
                    visita.save()

                    # ==================================
                    # ATUALIZAR STATUS DA MISSÃO
                    # ==================================

                    if missao is not None:

                        missao.status_execucao = "REALIZADA"

                        missao.motivo_nao_realizacao = ""

                        missao.registrado_por = usuario

                        missao.atualizado_execucao_em = (
                            timezone.now()
                        )

                        missao.save(
                            update_fields=[
                                "status_execucao",
                                "motivo_nao_realizacao",
                                "registrado_por",
                                "atualizado_execucao_em",
                            ]
                        )

            # ==========================================
            # TRATAMENTO DE ERROS
            # ==========================================

            except ValidationError as erro:

                adicionar_erros_modelo(
                    form,
                    erro
                )

            except IntegrityError:

                form.add_error(
                    None,
                    "Esta missão já possui uma visita "
                    "ou ocorreu um conflito ao salvar. "
                    "Atualize a página e tente novamente."
                )

            else:

                messages.success(
                    request,
                    "Visita registrada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    visita
                )

    # ==========================================
    # ABRIR FORMULÁRIO VIA GET
    # ==========================================

    else:

        initial = {}

        if missao is not None:

            initial["escola"] = (
                missao.escola_id
            )

            initial["data_visita"] = (
                missao.cartao.plantao.data
            )

        else:

            escola_id = request.GET.get(
                "escola"
            )

            if escola_id:
                initial["escola"] = escola_id

        form = RondaVisitaForm(
            initial=initial,
            missao=missao
        )

    # ==========================================
    # RENDERIZAR FORMULÁRIO
    # ==========================================

    return render(
        request,
        "visitas/form_visita.html",
        {
            "form": form,
            "modo_edicao": False,
            "missao_cartao": missao,
            "missao_cartao_id": (
                missao.pk
                if missao is not None
                else None
            ),
            "usuario": usuario,
        }
    )


# =========================================================
# EDITAR VISITA
# =========================================================

@login_required
def editar_visita(request, pk):
    """Edita uma visita preservando missão, escola e permissões."""
    usuario = obter_usuario_recom(request)
    visita = get_object_or_404(
        RondaVisita.objects.select_related("escola", "missao_cartao"), pk=pk
    )
    missao = visita.missao_cartao
    if missao is not None:
        validar_acesso_missao(request, missao)
    elif not pode_gerenciar_visitas(request):
        raise PermissionDenied(
            "A edição de visitas avulsas está restrita aos administradores e coordenadores."
        )

    if request.method == "POST":
        form = RondaVisitaForm(request.POST, instance=visita, missao=missao)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if missao is not None:
                        missao = MissaoCartao.objects.select_for_update().select_related(
                            "escola", "viatura", "cartao__plantao"
                        ).get(pk=missao.pk)
                        validar_acesso_missao(request, missao)
                        if missao.status_execucao == "NAO_REALIZADA":
                            raise ValidationError(
                                "Esta missão está marcada como não realizada."
                            )
                    atualizada = form.save(commit=False)
                    atualizada.missao_cartao = missao
                    if missao is not None:
                        for campo, valor in dados_da_missao(missao).items():
                            setattr(atualizada, campo, valor)
                    atualizada.full_clean()
                    atualizada.save()
                    if missao is not None and missao.status_execucao != "REALIZADA":
                        missao.status_execucao = "REALIZADA"
                        missao.motivo_nao_realizacao = ""
                        missao.save(update_fields=["status_execucao", "motivo_nao_realizacao"])
            except ValidationError as erro:
                adicionar_erros_modelo(form, erro)
            except IntegrityError:
                form.add_error(None, "Não foi possível salvar a visita devido a um conflito de dados.")
            else:
                messages.success(request, "Visita atualizada com sucesso.")
                return redirecionar_apos_visita(request, atualizada)
    else:
        form = RondaVisitaForm(instance=visita, missao=missao)

    return render(request, "visitas/form_visita.html", {
        "form": form,
        "visita": visita,
        "modo_edicao": True,
        "missao_cartao": missao,
        "missao_cartao_id": missao.pk if missao is not None else None,
        "usuario": usuario,
    })


# =========================================================
# EXCLUIR VISITA
# =========================================================

@login_required
@require_POST
def excluir_visita(request, pk):
    """Exclusão administrativa; reabre missão se sua visita for removida."""
    if not pode_gerenciar_visitas(request):
        raise PermissionDenied(
            "Somente administradores e coordenadores podem excluir registros de visitas."
        )

    # Obter a missão primeiro, e bloqueá-la antes de excluir a visita,
    # mantendo a mesma ordem de bloqueios usada no cadastro.
    referencia = get_object_or_404(RondaVisita, pk=pk)
    missao_id = referencia.missao_cartao_id
    escola_id = referencia.escola_id
    with transaction.atomic():
        missao = None
        if missao_id is not None:
            missao = MissaoCartao.objects.select_for_update().filter(pk=missao_id).first()
        visita = get_object_or_404(RondaVisita, pk=pk)
        if missao is not None and visita.missao_cartao_id != missao.pk:
            raise ValidationError("O vínculo da visita foi alterado. Atualize a página.")
        visita.delete()
        if (missao is not None and not RondaVisita.objects.filter(
                missao_cartao_id=missao.pk).exists()):
            missao.status_execucao = "PENDENTE"
            missao.motivo_nao_realizacao = ""
            missao.registrado_por = None
            missao.atualizado_execucao_em = None
            missao.save(update_fields=[
                "status_execucao", "motivo_nao_realizacao",
                "registrado_por", "atualizado_execucao_em",
            ])

    messages.success(request, "Visita excluída com sucesso.")
    return redirect("escolas:detalhe_escola", pk=escola_id)
