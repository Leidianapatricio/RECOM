
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from usuarios.models import Usuario

from .forms import EscolaForm, EscolaProblematicaForm
from .models import Escola, EscolaProblematica


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def obter_permissoes_visitas(request):
    """
    Identifica o usuário e suas permissões.

    ADMIN / COORDENADOR:
        Podem excluir qualquer visita.

    GCM:
        Pode excluir somente visitas registradas
        por ele próprio.

    Outros perfis:
        Não podem excluir visitas.
    """

    if not request.user.is_authenticated:
        return None, False

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True
    ).first()

    pode_excluir_todas = request.user.is_superuser or (
        usuario is not None
        and usuario.perfil in ["ADMIN", "COORDENADOR"]
    )

    return usuario, pode_excluir_todas


# =========================================================
# LISTAR ESCOLAS
# =========================================================

def listar_escolas(request):

    escolas = Escola.objects.all().order_by(
        "polo",
        "nome"
    )

    busca = request.GET.get(
        "busca", ""
    ).strip()

    polo = request.GET.get(
        "polo", ""
    ).strip()

    bairro = request.GET.get(
        "bairro", ""
    ).strip()

    situacao = request.GET.get(
        "situacao", "ativas"
    ).strip()

    # ==========================================
    # FILTRO POR SITUAÇÃO
    # ==========================================

    if situacao == "ativas":
        escolas = escolas.filter(ativa=True)

    elif situacao == "inativas":
        escolas = escolas.filter(ativa=False)

    # "todas": sem filtro de situação.

    # ==========================================
    # BUSCA GERAL
    # ==========================================

    if busca:
        escolas = escolas.filter(
            Q(nome__icontains=busca)
            | Q(endereco__icontains=busca)
            | Q(bairro__icontains=busca)
            | Q(gestor__icontains=busca)
        )

    # ==========================================
    # FILTRO POR POLO
    # ==========================================

    if polo:
        escolas = escolas.filter(
            polo=polo
        )

    # ==========================================
    # FILTRO POR BAIRRO
    # ==========================================

    if bairro:
        escolas = escolas.filter(
            bairro__iexact=bairro
        )

    # ==========================================
    # BAIRROS DISPONÍVEIS
    # ==========================================

    bairros = (
        Escola.objects
        .exclude(bairro="")
        .values_list("bairro", flat=True)
        .distinct()
        .order_by("bairro")
    )

    # ==========================================
    # PAGINAÇÃO
    # ==========================================

    paginator = Paginator(escolas, 10)

    numero_pagina = request.GET.get("page")

    page_obj = paginator.get_page(
        numero_pagina
    )

    contexto = {
        "page_obj": page_obj,
        "busca": busca,
        "polo_selecionado": polo,
        "bairro_selecionado": bairro,
        "situacao_selecionada": situacao,
        "polos": Escola.POLO_CHOICES,
        "bairros": bairros,
    }

    return render(
        request,
        "escolas/listar_escolas.html",
        contexto,
    )


# =========================================================
# CADASTRAR ESCOLA
# =========================================================

def cadastrar_escola(request):

    if request.method == "POST":

        form = EscolaForm(request.POST)

        if form.is_valid():

            escola = form.save()

            messages.success(
                request,
                "Escola cadastrada com sucesso."
            )

            if "salvar_problematica" in request.POST:
                return redirect(
                    "escolas:cadastrar_problematica",
                    pk=escola.pk
                )

            return redirect(
                "escolas:listar_escolas"
            )

    else:
        form = EscolaForm()

    return render(
        request,
        "escolas/form_escola.html",
        {"form": form}
    )


# =========================================================
# DETALHES DA ESCOLA
# =========================================================

@login_required
def detalhe_escola(request, pk):

    escola = get_object_or_404(
        Escola,
        pk=pk
    )

    # ==========================================
    # IDENTIFICAR PERMISSÕES
    # ==========================================

    usuario, pode_excluir_todas = (
        obter_permissoes_visitas(request)
    )

    # ==========================================
    # HISTÓRICO DE VISITAS
    # ==========================================

    visitas = list(
        escola.visitas.select_related(
            "registrado_por"
        ).order_by(
            "-data_visita",
            "-horario"
        )
    )

    # ==========================================
    # PERMISSÕES INDIVIDUAIS
    # ==========================================

    for visita in visitas:

        visita.pode_excluir = (
            pode_excluir_todas
            or (
                usuario is not None
                and usuario.perfil == "GCM"
                and visita.registrado_por_id == usuario.pk
            )
        )

    contexto = {
        "escola": escola,
        "visitas": visitas,
        "usuario_recom": usuario,
        "pode_excluir_todas_visitas": pode_excluir_todas,
    }

    return render(
        request,
        "escolas/detalhe_escola.html",
        contexto
    )


# =========================================================
# CADASTRAR PROBLEMÁTICA
# =========================================================

def cadastrar_problematica(request, pk):

    escola = get_object_or_404(
        Escola,
        pk=pk,
        ativa=True
    )

    if request.method == "POST":

        form = EscolaProblematicaForm(
            request.POST
        )

        if form.is_valid():

            tipo = form.cleaned_data[
                "tipo_problematica"
            ]

            ja_existe = EscolaProblematica.objects.filter(
                escola=escola,
                tipo_problematica=tipo
            ).exists()

            if ja_existe:

                form.add_error(
                    "tipo_problematica",
                    (
                        "Esta problemática já está "
                        "registrada para esta escola."
                    )
                )

            else:

                problematica = form.save(
                    commit=False
                )

                problematica.escola = escola
                problematica.save()

                messages.success(
                    request,
                    "Problemática registrada com sucesso."
                )

                return redirect(
                    "escolas:detalhe_escola",
                    pk=escola.pk
                )

    else:
        form = EscolaProblematicaForm()

    contexto = {
        "escola": escola,
        "form": form,
    }

    return render(
        request,
        "escolas/form_problematica.html",
        contexto
    )


# =========================================================
# EDITAR PROBLEMÁTICA
# =========================================================

def editar_problematica(
    request,
    escola_pk,
    problematica_pk
):

    escola = get_object_or_404(
        Escola,
        pk=escola_pk
    )

    problematica = get_object_or_404(
        EscolaProblematica,
        pk=problematica_pk,
        escola=escola
    )

    if request.method == "POST":

        form = EscolaProblematicaForm(
            request.POST,
            instance=problematica
        )

        if form.is_valid():

            tipo = form.cleaned_data[
                "tipo_problematica"
            ]

            ja_existe = EscolaProblematica.objects.filter(
                escola=escola,
                tipo_problematica=tipo
            ).exclude(
                pk=problematica.pk
            ).exists()

            if ja_existe:

                form.add_error(
                    "tipo_problematica",
                    (
                        "Esta problemática já está "
                        "registrada para esta escola."
                    )
                )

            else:

                form.save()

                messages.success(
                    request,
                    "Problemática atualizada com sucesso."
                )

                return redirect(
                    "escolas:detalhe_escola",
                    pk=escola.pk
                )

    else:

        form = EscolaProblematicaForm(
            instance=problematica
        )

    contexto = {
        "escola": escola,
        "problematica": problematica,
        "form": form,
        "modo_edicao": True,
    }

    return render(
        request,
        "escolas/form_problematica.html",
        contexto
    )


# =========================================================
# EXCLUIR PROBLEMÁTICA
# =========================================================

def excluir_problematica(
    request,
    escola_pk,
    problematica_pk
):

    escola = get_object_or_404(
        Escola,
        pk=escola_pk
    )

    problematica = get_object_or_404(
        EscolaProblematica,
        pk=problematica_pk,
        escola=escola
    )

    if request.method == "POST":

        nome_problematica = (
            problematica.tipo_problematica.nome
        )

        problematica.delete()

        messages.success(
            request,
            (
                f'A problemática "{nome_problematica}" '
                "foi removida da escola com sucesso."
            )
        )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola.pk
    )


# =========================================================
# EDITAR ESCOLA
# =========================================================

def editar_escola(request, pk):

    escola = get_object_or_404(
        Escola,
        pk=pk
    )

    if request.method == "POST":

        form = EscolaForm(
            request.POST,
            instance=escola
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Escola atualizada com sucesso."
            )

            return redirect(
                "escolas:detalhe_escola",
                pk=escola.pk
            )

    else:

        form = EscolaForm(
            instance=escola
        )

    return render(
        request,
        "escolas/form_escola.html",
        {
            "form": form,
            "escola": escola,
            "modo_edicao": True,
        }
    )


# =========================================================
# DESATIVAR ESCOLA
# =========================================================

def desativar_escola(request, pk):

    escola = get_object_or_404(
        Escola,
        pk=pk
    )

    if request.method == "POST":

        escola.ativa = False

        escola.save(
            update_fields=[
                "ativa",
                "atualizado_em",
            ]
        )

        messages.success(
            request,
            "Escola desativada com sucesso."
        )

        return redirect(
            "escolas:listar_escolas"
        )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola.pk
    )


# =========================================================
# ATIVAR ESCOLA
# =========================================================

def ativar_escola(request, pk):

    escola = get_object_or_404(
        Escola,
        pk=pk
    )

    if request.method == "POST":

        escola.ativa = True
        escola.data_inativacao = None

        escola.save(
            update_fields=[
                "ativa",
                "data_inativacao",
                "atualizado_em",
            ]
        )

        messages.success(
            request,
            "Escola ativada com sucesso."
        )

        return redirect(
            "escolas:detalhe_escola",
            pk=escola.pk
        )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola.pk
    )
