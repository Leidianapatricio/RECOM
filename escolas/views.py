from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EscolaForm, EscolaProblematicaForm
from .models import Escola, EscolaProblematica


def listar_escolas(request):
    escolas = Escola.objects.all().order_by(
        "polo",
        "nome"
    )

    busca = request.GET.get(
        "busca",
        ""
    ).strip()

    polo = request.GET.get(
        "polo",
        ""
    ).strip()

    bairro = request.GET.get(
        "bairro",
        ""
    ).strip()

    situacao = request.GET.get(
        "situacao",
        "ativas"
    ).strip()

    # Filtro por situação
    if situacao == "ativas":
        escolas = escolas.filter(
            ativa=True
        )

    elif situacao == "inativas":
        escolas = escolas.filter(
            ativa=False
        )

    # Se for "todas", não aplica filtro de ativa/inativa

    # Busca geral
    if busca:
        escolas = escolas.filter(
            Q(nome__icontains=busca)
            | Q(endereco__icontains=busca)
            | Q(bairro__icontains=busca)
            | Q(gestor__icontains=busca)
        )

    # Filtro por polo
    if polo:
        escolas = escolas.filter(
            polo=polo
        )

    # Filtro por bairro
    if bairro:
        escolas = escolas.filter(
            bairro__iexact=bairro
        )

    # Lista de bairros para o select
    bairros = (
        Escola.objects
        .exclude(bairro="")
        .values_list(
            "bairro",
            flat=True
        )
        .distinct()
        .order_by("bairro")
    )

    # Paginação
    paginator = Paginator(
        escolas,
        10
    )

    numero_pagina = request.GET.get(
        "page"
    )

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


def cadastrar_escola(request):
    if request.method == "POST":
        form = EscolaForm(
            request.POST
        )

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
        {
            "form": form
        }
    )


def detalhe_escola(request, pk):
    escola = get_object_or_404(
        Escola,
        pk=pk
    )

    # Histórico de visitas da escola
    visitas = escola.visitas.all().order_by(
        "-data_visita",
        "-horario"
    )

    contexto = {
        "escola": escola,
        "visitas": visitas,
    }

    return render(
        request,
        "escolas/detalhe_escola.html",
        contexto
    )


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