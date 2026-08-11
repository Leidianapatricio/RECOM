from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import UnidadeSaudeForm, ProfissionalForm
from .models import UnidadeSaude, Profissional


def listar_unidades(request):
    pesquisa = request.GET.get("q")
    unidades = UnidadeSaude.objects.all().order_by("nome")

    if pesquisa:
        unidades = unidades.filter(nome__icontains=pesquisa)

    paginator = Paginator(unidades, 10)
    page = request.GET.get("page")
    unidades = paginator.get_page(page)

    return render(request, "unidades/listar.html", {
        "unidades": unidades,
        "pesquisa": pesquisa,
    })


def criar_unidade(request):
    form = UnidadeSaudeForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Unidade cadastrada com sucesso.")
            return redirect("unidades:listar")

    return render(request, "unidades/form.html", {
        "form": form,
        "titulo": "Nova Unidade de Saúde",
        "descricao": "Cadastre uma nova unidade de saúde.",
    })


def editar_unidade(request, id):
    unidade = get_object_or_404(UnidadeSaude, id=id)
    form = UnidadeSaudeForm(request.POST or None, instance=unidade)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Unidade atualizada com sucesso.")
            return redirect("unidades:listar")

    return render(request, "unidades/form.html", {
        "form": form,
        "titulo": "Editar Unidade de Saúde",
        "descricao": "Atualize as informações da unidade.",
    })


def excluir_unidade(request, id):
    unidade = get_object_or_404(UnidadeSaude, id=id)

    if request.method == "POST":
        unidade.delete()
        messages.success(request, "Unidade excluída com sucesso.")
        return redirect("unidades:listar")

    return render(request, "unidades/excluir.html", {
        "unidade": unidade,
    })


def listar_profissionais(request):
    pesquisa = request.GET.get("q")
    profissionais = Profissional.objects.select_related("unidade").order_by("nome")

    if pesquisa:
        profissionais = profissionais.filter(nome__icontains=pesquisa)

    paginator = Paginator(profissionais, 10)
    page = request.GET.get("page")
    profissionais = paginator.get_page(page)

    return render(request, "profissionais/listar.html", {
        "profissionais": profissionais,
        "pesquisa": pesquisa,
    })


def criar_profissional(request):
    form = ProfissionalForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            profissional = form.save(commit=False)

            cpf_limpo = profissional.cpf.replace(".", "").replace("-", "")
            primeiro_nome = profissional.nome.split()[0].lower()

            user, criado = User.objects.get_or_create(
                username=cpf_limpo
            )

            if criado:
                user.set_password(primeiro_nome)
                user.first_name = profissional.nome
                user.email = profissional.email or ""
                user.save()

            profissional.user = user
            profissional.save()

            messages.success(
                request,
                f"Profissional cadastrado com sucesso. Senha inicial: {primeiro_nome}"
            )

            return redirect("unidades:listar_profissionais")

    return render(request, "profissionais/form.html", {
        "form": form,
        "titulo": "Novo Profissional",
        "descricao": "Cadastre um profissional de saúde.",
    })

def editar_profissional(request, id):
    profissional = get_object_or_404(Profissional, id=id)
    form = ProfissionalForm(request.POST or None, instance=profissional)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profissional atualizado com sucesso.")
            return redirect("unidades:listar_profissionais")

    return render(request, "profissionais/form.html", {
        "form": form,
        "titulo": "Editar Profissional",
        "descricao": "Atualize os dados do profissional.",
    })


def excluir_profissional(request, id):
    profissional = get_object_or_404(Profissional, id=id)

    if request.method == "POST":
        profissional.delete()
        messages.success(request, "Profissional excluído com sucesso.")

    return redirect("unidades:listar_profissionais")