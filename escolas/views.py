from django.shortcuts import render

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EscolaForm
from .models import Escola


def listar_escolas(request):
    escolas = Escola.objects.filter(ativa=True).order_by("polo", "nome")

    contexto = {
        "escolas": escolas,
    }

    return render(
        request,
        "escolas/listar_escolas.html",
        contexto,
    )


def cadastrar_escola(request):
    if request.method == "POST":
        form = EscolaForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Escola cadastrada com sucesso.",
            )

            return redirect("escolas:listar_escolas")

    else:
        form = EscolaForm()

    contexto = {
        "form": form,
    }

    return render(
        request,
        "escolas/form_escola.html",
        contexto,
    )


def detalhe_escola(request, pk):
    escola = get_object_or_404(
        Escola,
        pk=pk,
    )

    contexto = {
        "escola": escola,
    }

    return render(
        request,
        "escolas/detalhe_escola.html",
        contexto,
    )
