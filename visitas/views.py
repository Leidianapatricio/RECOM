from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RondaVisitaForm
from .models import RondaVisita


def cadastrar_visita(request):

    if request.method == "POST":
        form = RondaVisitaForm(
            request.POST
        )

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
        escola_id = request.GET.get(
            "escola"
        )

        initial = {}

        if escola_id:
            initial["escola"] = escola_id

        form = RondaVisitaForm(
            initial=initial
        )

    return render(
        request,
        "visitas/form_visita.html",
        {
            "form": form,
        }
    )


@require_POST
def excluir_visita(request, pk):

    visita = get_object_or_404(
        RondaVisita,
        pk=pk
    )

    escola_id = visita.escola.pk

    visita.delete()

    messages.success(
        request,
        "Visita excluída com sucesso."
    )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola_id
    )