
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_GET


from cartao_programa.models import EfetivoViatura, MissaoCartao, ViaturaPlantao
from usuarios.models import Usuario
from .forms import obter_codigo_equipe_viatura

from .forms import RondaVisitaForm, dados_da_missao
from .models import RondaVisita
from .permissoes import (
    pode_editar_visita,
    pode_excluir_visita,
)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def obter_usuario_recom(request):
    """
    Identifica o usuário autenticado no RECOM.
    """

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        raise PermissionDenied(
            "É necessário estar autenticado e ativo."
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
    ADMIN e COORDENADOR podem gerenciar todas
    as visitas.
    """

    usuario = obter_usuario_recom(request)

    return (
        request.user.is_superuser
        or (
            usuario is not None
            and usuario.perfil in (
                "ADMIN",
                "COORDENADOR",
            )
        )
    )


def validar_acesso_missao(request, missao):
    """
    Verifica se o GCM pode registrar uma visita
    vinculada à missão do Cartão Programa.

    C, P1 e P2 podem registrar.
    M não pode registrar novas visitas.
    """

    if (
        missao.cartao.plantao_id
        != missao.viatura.plantao_id
    ):
        raise PermissionDenied(
            "A missão não corresponde ao plantão da viatura."
        )

    if pode_gerenciar_visitas(request):
        return

    usuario = obter_usuario_recom(request)

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para registrar "
            "visitas nesta missão."
        )

    escala = EfetivoViatura.objects.filter(
        viatura_id=missao.viatura_id,
        gcm=usuario,
    ).first()

    if escala is None:
        raise PermissionDenied(
            "Esta missão não pertence à sua escala."
        )

    if escala.funcao not in ("C", "P1", "P2"):
        raise PermissionDenied(
            "Sua função na viatura não permite "
            "registrar visitas nesta missão."
        )


def obter_missao_autorizada(request, missao_id):
    """
    Recupera a missão e verifica o acesso.
    """

    missao = get_object_or_404(
        MissaoCartao.objects.select_related(
            "escola",
            "viatura",
            "cartao__plantao",
        ),
        pk=missao_id,
    )

    validar_acesso_missao(request, missao)

    if missao.escola_id is None:
        raise PermissionDenied(
            "Esta missão não possui escola vinculada."
        )

    return missao


def validar_edicao_visita(request, visita):
    """
    ADMIN / COORDENADOR:
        Editam qualquer visita.

    GCM:
        Edita qualquer visita legada ou visitas da equipe
        escalada na data da visita.
    """

    if not pode_editar_visita(request, visita):
        raise PermissionDenied(
            "Você não integra a equipe escalada "
            "nesta data e não possui permissão "
            "para editar esta visita."
        )


def validar_exclusao_visita(request, visita):
    """
    ADMIN / COORDENADOR:
        Excluem qualquer visita.

    GCM:
        Exclui qualquer visita legada ou visitas da equipe
        escalada na data da visita.

    A missão nunca é excluída.
    """

    if not pode_excluir_visita(request, visita):
        raise PermissionDenied(
            "Você não possui permissão para "
            "excluir esta visita."
        )


def adicionar_erros_modelo(form, erro):
    """
    Adiciona ao formulário os erros de validação
    retornados pelo modelo.
    """

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():

            form.add_error(
                campo if campo in form.fields else None,
                erros,
            )

    else:
        form.add_error(None, erro)


def redirecionar_apos_visita(request, visita):
    """
    Após registrar ou editar:

    GCM em missão:
        Retorna ao seu Cartão Programa.

    Demais casos:
        Retorna aos detalhes da escola.
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
        pk=visita.escola_id,
    )


# =========================================================
# CADASTRAR VISITA
# =========================================================

@login_required
def cadastrar_visita(request):

    usuario = obter_usuario_recom(request)

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
        obter_missao_autorizada(request, missao_id)
        if missao_id
        else None
    )

    # -----------------------------------------------------
    # VERIFICAR SE A MISSÃO JÁ FOI EXECUTADA
    # -----------------------------------------------------

    if missao is not None and (
        missao.status_execucao != "PENDENTE"
        or RondaVisita.objects.filter(
            missao_cartao_id=missao.pk
        ).exists()
    ):

        messages.warning(
            request,
            "Esta missão já possui um resultado registrado."
        )

        if pode_gerenciar_visitas(request):
            return redirect(
                "escolas:detalhe_escola",
                pk=missao.escola_id,
            )

        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    # -----------------------------------------------------
    # SALVAR VISITA
    # -----------------------------------------------------

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            missao=missao,
            usuario_logado=request.user,
        )

        if form.is_valid():

            try:

                with transaction.atomic():

                    if missao is not None:

                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(),
                            pk=missao.pk,
                        )

                        validar_acesso_missao(
                            request,
                            missao,
                        )

                        if missao.status_execucao != "PENDENTE":
                            raise ValidationError(
                                "Esta missão já possui "
                                "um resultado registrado."
                            )

                        if RondaVisita.objects.filter(
                            missao_cartao_id=missao.pk
                        ).exists():
                            raise ValidationError(
                                "Já existe uma visita "
                                "registrada para esta missão."
                            )

                    visita = form.save(commit=False)

                    visita.missao_cartao = missao

                    # Identifica quem cadastrou a visita.
                    visita.registrado_por = usuario

                    if missao is not None:

                        for campo, valor in dados_da_missao(
                            missao
                        ).items():
                            setattr(
                                visita,
                                campo,
                                valor,
                            )

                    visita.full_clean()
                    visita.save()

                    # Atualiza a execução da missão.
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

            except ValidationError as erro:

                adicionar_erros_modelo(
                    form,
                    erro,
                )

            except IntegrityError:

                form.add_error(
                    None,
                    "Esta missão já possui uma visita "
                    "ou ocorreu um conflito ao salvar."
                )

            else:

                messages.success(
                    request,
                    "Visita registrada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    visita,
                )

    else:

        initial = {}

        if missao is not None:

            initial["escola"] = missao.escola_id
            initial["data_visita"] = (
                missao.cartao.plantao.data
            )

        elif request.GET.get("escola"):

            initial["escola"] = (
                request.GET["escola"]
            )

        form = RondaVisitaForm(
            initial=initial,
            missao=missao,
            usuario_logado=request.user,
        )

    contexto = {
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

    return render(
        request,
        "visitas/form_visita.html",
        contexto,
    )


# =========================================================
# EDITAR VISITA
# =========================================================

@login_required
def editar_visita(request, pk):

    usuario = obter_usuario_recom(request)

    visita = get_object_or_404(
        RondaVisita.objects.select_related(
            "escola",
            "missao_cartao",
            "missao_cartao__viatura__plantao",
            "missao_cartao__cartao__plantao",
        ),
        pk=pk,
    )

    # -----------------------------------------------------
    # VERIFICAR PERMISSÃO DE EDIÇÃO
    # -----------------------------------------------------

    validar_edicao_visita(
        request,
        visita,
    )

    missao = visita.missao_cartao

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            instance=visita,
            missao=missao,
            usuario_logado=request.user,
        )

        if form.is_valid():

            try:

                with transaction.atomic():

                    # Bloqueia o registro para edição.
                    visita = get_object_or_404(
                        RondaVisita.objects.select_for_update(),
                        pk=pk,
                    )

                    # Verifica novamente a permissão.
                    validar_edicao_visita(
                        request,
                        visita,
                    )

                    missao = visita.missao_cartao

                    if missao is not None:

                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(),
                            pk=missao.pk,
                        )

                        if (
                            missao.status_execucao
                            == "NAO_REALIZADA"
                        ):
                            raise ValidationError(
                                "Esta missão está marcada "
                                "como não realizada."
                            )

                    # Impede trocar a viatura de uma visita já registrada.
                    # O histórico deve preservar o plantão original.
                    viatura_nova = form.cleaned_data.get("viatura")
                    if (
                        visita.viatura_id is not None
                        and viatura_nova is not None
                        and viatura_nova.pk != visita.viatura_id
                    ):
                        raise ValidationError(
                            "Não é permitido alterar a viatura de uma visita "
                            "já registrada."
                        )

                    # Atualiza a instância bloqueada.
                    form.instance = visita

                    atualizada = form.save(
                        commit=False
                    )

                    # Preserva a missão original.
                    atualizada.missao_cartao = missao
                    # Visitas sem missão não devem ficar vinculadas
                    # a uma viatura do plantão.
                    if missao is None:
                        atualizada.viatura = None

                    # Preserva o autor original.
                    atualizada.registrado_por_id = (
                        visita.registrado_por_id
                    )

                    if missao is not None:

                        for campo, valor in dados_da_missao(
                            missao
                        ).items():

                            setattr(
                                atualizada,
                                campo,
                                valor,
                            )

                    atualizada.full_clean()
                    atualizada.save()

                    if (
                        missao is not None
                        and missao.status_execucao
                        != "REALIZADA"
                    ):

                        missao.status_execucao = "REALIZADA"
                        missao.motivo_nao_realizacao = ""

                        missao.save(
                            update_fields=[
                                "status_execucao",
                                "motivo_nao_realizacao",
                            ]
                        )

            except ValidationError as erro:

                adicionar_erros_modelo(
                    form,
                    erro,
                )

            except IntegrityError:

                form.add_error(
                    None,
                    "Não foi possível salvar a visita "
                    "devido a um conflito de dados."
                )

            else:

                messages.success(
                    request,
                    "Visita atualizada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    atualizada,
                )

    else:

        form = RondaVisitaForm(
            instance=visita,
            missao=missao,
            usuario_logado=request.user,
        )

    contexto = {
        "form": form,
        "visita": visita,
        "modo_edicao": True,
        "missao_cartao": missao,
        "missao_cartao_id": (
            missao.pk
            if missao is not None
            else None
        ),
        "usuario": usuario,
    }

    return render(
        request,
        "visitas/form_visita.html",
        contexto,
    )


# =========================================================
# EXCLUIR VISITA
# =========================================================

@login_required
@require_POST
def excluir_visita(request, pk):
    """
    Exclui uma visita autorizada.

    Se estiver vinculada a uma missão:
    - Exclui somente a visita.
    - Mantém a missão no Cartão Programa.
    - Retorna a execução para PENDENTE.
    """

    obter_usuario_recom(request)

    referencia = get_object_or_404(
        RondaVisita,
        pk=pk,
    )

    # Primeira validação de permissão.
    validar_exclusao_visita(
        request,
        referencia,
    )

    missao_id = referencia.missao_cartao_id

    with transaction.atomic():

        missao = None

        if missao_id is not None:

            missao = get_object_or_404(
                MissaoCartao.objects.select_for_update(),
                pk=missao_id,
            )

        visita = get_object_or_404(
            RondaVisita.objects.select_for_update(),
            pk=pk,
        )

        if visita.missao_cartao_id != missao_id:
            raise PermissionDenied(
                "O vínculo da visita foi alterado. "
                "Atualize a página."
            )

        # Revalida a permissão dentro da transação.
        validar_exclusao_visita(
            request,
            visita,
        )

        escola_id = visita.escola_id

        # Exclui somente a visita.
        visita.delete()

        # Reabre a missão sem excluí-la.
        if missao is not None:

            existe_outra_visita = (
                RondaVisita.objects.filter(
                    missao_cartao_id=missao.pk
                ).exists()
            )

            if not existe_outra_visita:

                missao.status_execucao = "PENDENTE"
                missao.motivo_nao_realizacao = ""
                missao.registrado_por = None
                missao.atualizado_execucao_em = None

                missao.save(
                    update_fields=[
                        "status_execucao",
                        "motivo_nao_realizacao",
                        "registrado_por",
                        "atualizado_execucao_em",
                    ]
                )

    messages.success(
        request,
        "Visita excluída com sucesso."
    )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola_id,
    )

# =========================================================
# LISTAR VISITAS - ADMINISTRADOR E COORDENADOR
# =========================================================

@login_required
def listar_visitas(request):

    usuario = obter_usuario_recom(request)

    # Somente ADMIN, COORDENADOR e superusuário.
    if not pode_gerenciar_visitas(request):
        raise PermissionDenied(
            "Você não possui permissão para acessar "
            "a gestão de visitas."
        )

    # =====================================================
    # CONSULTAR VISITAS
    # =====================================================

    visitas = RondaVisita.objects.select_related(
        "escola",
        "registrado_por",
        "missao_cartao",
    ).order_by(
        "-data_visita",
        "-horario",
    )

    # =====================================================
    # FILTROS
    # =====================================================

    busca = request.GET.get(
        "busca", ""
    ).strip()

    equipe = request.GET.get(
        "equipe", ""
    ).strip()

    data_inicio = request.GET.get(
        "data_inicio", ""
    ).strip()

    data_fim = request.GET.get(
        "data_fim", ""
    ).strip()

    if busca:
        visitas = visitas.filter(
            Q(escola__nome__icontains=busca)
            | Q(relato__icontains=busca)
        )

    if equipe:
        visitas = visitas.filter(
            equipe=equipe
        )

    # Valida datas antes de aplicá-las ao banco.
    from datetime import date

    try:
        inicio = (
            date.fromisoformat(data_inicio)
            if data_inicio
            else None
        )
    except ValueError:
        inicio = None
        messages.warning(
            request,
            "Data inicial inválida."
        )

    try:
        fim = (
            date.fromisoformat(data_fim)
            if data_fim
            else None
        )
    except ValueError:
        fim = None
        messages.warning(
            request,
            "Data final inválida."
        )

    if inicio:
        visitas = visitas.filter(
            data_visita__gte=inicio
        )

    if fim:
        visitas = visitas.filter(
            data_visita__lte=fim
        )

    # =====================================================
    # PAGINAÇÃO
    # =====================================================

    paginator = Paginator(visitas, 15)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # =====================================================
    # CONTEXTO
    # =====================================================

    contexto = {
        "page_obj": page_obj,
        "usuario": usuario,
        "busca": busca,
        "equipe_selecionada": equipe,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    return render(
        request,
        "visitas/listar_visitas.html",
        contexto,
    )

# =========================================================
# CONSULTAR VIATURAS DISPONÍVEIS PARA VISITA AVULSA
# =========================================================

@login_required
@require_GET
def consultar_viaturas_visita(request):

    usuario = obter_usuario_recom(request)

    data_informada = request.GET.get(
        "data", ""
    ).strip()

    # ==============================================
    # VALIDAR DATA
    # ==============================================

    if not data_informada:

        return JsonResponse({
            "viaturas": [],
            "mensagem": "Informe a data da visita.",
        })

    try:
        data_visita = date.fromisoformat(
            data_informada
        )

    except ValueError:

        return JsonResponse(
            {
                "viaturas": [],
                "mensagem": "Data inválida.",
            },
            status=400,
        )

    # ==============================================
    # CONSULTAR VIATURAS DO PLANTÃO
    # ==============================================

    viaturas = (
        ViaturaPlantao.objects
        .select_related(
            "plantao",
            "equipe",
        )
        .filter(
            plantao__data=data_visita
        )
    )

    # ==============================================
    # FILTRAR PERMISSÕES
    # ==============================================

    if not pode_gerenciar_visitas(request):

        if (
            usuario is None
            or usuario.perfil != "GCM"
        ):

            raise PermissionDenied(
                "Você não possui permissão "
                "para consultar essas viaturas."
            )

        viaturas = viaturas.filter(
            efetivo__gcm=usuario,
            efetivo__funcao__in=[
                "C",
                "P1",
                "P2",
            ],
        )

    viaturas = viaturas.distinct().order_by(
        "identificacao",
        "pk",
    )

    # ==============================================
    # PREPARAR RESPOSTA
    # ==============================================

    resultado = []

    for viatura in viaturas:

        try:

            codigo_equipe = (
                obter_codigo_equipe_viatura(
                    viatura
                )
            )

        except ValidationError:

            # Não apresentar viaturas cuja equipe
            # não possa ser identificada.
            continue

        nome_equipe = (
            viatura.equipe.nome
            if viatura.equipe_id
            else "Equipe extraordinária"
        )

        resultado.append({
            "id": viatura.pk,
            "identificacao": viatura.identificacao,
            "equipe": codigo_equipe,
            "nome_equipe": nome_equipe,
        })

    return JsonResponse({
        "viaturas": resultado,
        "mensagem": (
            ""
            if resultado
            else "Nenhuma viatura disponível "
                 "para sua escala nesta data."
        ),
    })

