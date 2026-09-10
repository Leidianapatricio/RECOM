from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import RondaVisitaForm


def cadastrar_visita(request):

    if request.method == "POST":
        form = RondaVisitaForm(request.POST)

        if form.is_valid():
            visita = form.save()

            messages.success(
                request,
                "Visita registrada com sucesso."
            )

            return redirect(
                "escolas:detalhe_escola",
                pk=visita.escola.pk
            )

    else:
        form = RondaVisitaForm()

    return render(
        request,
        "visitas/form_visita.html",
        {
            "form": form,
        }
    )
