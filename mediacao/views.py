from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from usuarios.models import Usuario

from .forms import (
    AtividadeMediacaoForm,
    PlanejamentoMediacaoForm,
)
from .models import (
    AtividadeMediacao,
    PlanejamentoMediacao,
)


# ============================================================
# CONTROLE DE ACESSO DO MEDIADOR
# ============================================================

def obter_mediador(request):
    """
    Retorna o perfil do Mediador autenticado.

    Utiliza o modelo Usuario vinculado ao auth.User,
    conforme a estrutura do RECOM.
    """

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True,
        perfil="MEDIADOR",
    ).first()

    if usuario is None:
        raise PermissionDenied(
            "Acesso permitido somente ao Mediador."
        )

    return usuario


# ============================================================
# PLANEJAMENTO DE MEDIAÇÃO
# ============================================================

@login_required
def planejar_mediacao(request):

    mediador = obter_mediador(request)

    if request.method == "POST":
        form = PlanejamentoMediacaoForm(request.POST)

        if form.is_valid():
            planejamento = form.save(commit=False)
            planejamento.mediador = mediador
            planejamento.save()

            messages.success(
                request,
                "Planejamento de mediação salvo com sucesso."
            )

            return redirect(
                "mediacao:listar_planejamentos"
            )

    else:
        form = PlanejamentoMediacaoForm()

    return render(
        request,
        "mediacao/planejar_mediacao.html",
        {
            "form": form,
            "mediador": mediador,
        }
    )


# ============================================================
# LISTAR PLANEJAMENTOS
# ============================================================

@login_required
def listar_planejamentos(request):

    mediador = obter_mediador(request)

    planejamentos = (
        PlanejamentoMediacao.objects
        .filter(mediador=mediador)
        .select_related("escola")
        .order_by("-data", "escola__nome")
    )

    return render(
        request,
        "mediacao/listar_planejamentos.html",
        {
            "planejamentos": planejamentos,
        }
    )


# ============================================================
# EDITAR PLANEJAMENTO
# ============================================================

@login_required
def editar_planejamento(request, pk):

    mediador = obter_mediador(request)

    planejamento = get_object_or_404(
        PlanejamentoMediacao,
        pk=pk,
        mediador=mediador,
    )

    if request.method == "POST":
        form = PlanejamentoMediacaoForm(
            request.POST,
            instance=planejamento,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Planejamento atualizado com sucesso."
            )

            return redirect(
                "mediacao:listar_planejamentos"
            )

    else:
        form = PlanejamentoMediacaoForm(
            instance=planejamento
        )

    return render(
        request,
        "mediacao/planejar_mediacao.html",
        {
            "form": form,
            "planejamento": planejamento,
            "mediador": mediador,
            "edicao": True,
        }
    )


# ============================================================
# REGISTRAR ATIVIDADE DE MEDIAÇÃO
# ============================================================

@login_required
def registrar_atividade(request):

    mediador = obter_mediador(request)

    planejamento_id = request.GET.get(
        "planejamento"
    )

    planejamento = None

    if planejamento_id:
        planejamento = get_object_or_404(
            PlanejamentoMediacao,
            pk=planejamento_id,
            mediador=mediador,
        )

    if request.method == "POST":
        form = AtividadeMediacaoForm(
            request.POST,
            mediador=mediador,
        )

        if form.is_valid():
            atividade = form.save(commit=False)

            atividade.mediador_responsavel = mediador

            atividade.full_clean()
            atividade.save()

            if atividade.planejamento:
                planejamento_vinculado = (
                    atividade.planejamento
                )

                planejamento_vinculado.status = (
                    "REALIZADA"
                )

                planejamento_vinculado.save(
                    update_fields=[
                        "status",
                        "atualizado_em",
                    ]
                )

            messages.success(
                request,
                "Atividade de mediação registrada com sucesso."
            )

            return redirect(
                "mediacao:listar_atividades"
            )

    else:
        initial = {}

        if planejamento:
            initial = {
                "planejamento": planejamento,
                "escola": planejamento.escola,
                "data": planejamento.data,
            }

        form = AtividadeMediacaoForm(
            initial=initial,
            mediador=mediador,
        )

    return render(
        request,
        "mediacao/registrar_atividade.html",
        {
            "form": form,
            "planejamento": planejamento,
            "mediador": mediador,
        }
    )


# ============================================================
# LISTAR ATIVIDADES
# ============================================================

@login_required
def listar_atividades(request):

    mediador = obter_mediador(request)

    atividades = (
        AtividadeMediacao.objects
        .filter(
            mediador_responsavel=mediador
        )
        .select_related(
            "escola",
            "planejamento",
        )
        .order_by(
            "-data",
            "-criado_em",
        )
    )

    return render(
        request,
        "mediacao/listar_atividades.html",
        {
            "atividades": atividades,
        }
    )


# ============================================================
# DETALHAR ATIVIDADE
# ============================================================

@login_required
def detalhe_atividade(request, pk):

    mediador = obter_mediador(request)

    atividade = get_object_or_404(
        AtividadeMediacao.objects.select_related(
            "escola",
            "planejamento",
        ),
        pk=pk,
        mediador_responsavel=mediador,
    )

    return render(
        request,
        "mediacao/detalhe_atividade.html",
        {
            "atividade": atividade,
        }
    )


# ============================================================
# EDITAR ATIVIDADE
# ============================================================

@login_required
def editar_atividade(request, pk):

    mediador = obter_mediador(request)

    atividade = get_object_or_404(
        AtividadeMediacao,
        pk=pk,
        mediador_responsavel=mediador,
    )

    if request.method == "POST":
        form = AtividadeMediacaoForm(
            request.POST,
            instance=atividade,
            mediador=mediador,
        )

        if form.is_valid():
            atividade_editada = form.save(
                commit=False
            )

            atividade_editada.mediador_responsavel = (
                mediador
            )

            atividade_editada.full_clean()
            atividade_editada.save()

            messages.success(
                request,
                "Atividade atualizada com sucesso."
            )

            return redirect(
                "mediacao:detalhe_atividade",
                pk=atividade_editada.pk,
            )

    else:
        form = AtividadeMediacaoForm(
            instance=atividade,
            mediador=mediador,
        )

    return render(
        request,
        "mediacao/registrar_atividade.html",
        {
            "form": form,
            "atividade": atividade,
            "mediador": mediador,
            "edicao": True,
        }
    )
    