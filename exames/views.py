from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User
from usuarios.models import Usuario
from .models import TipoExame, Agendamento
from unidades.models import UnidadeSaude
from .forms import TipoExameForm
from .models import TipoExame
from .models import Agendamento,Exame
from .forms import AgendamentoForm



def listar_tipos(request):
    pesquisa = request.GET.get("q")
    tipos = TipoExame.objects.all().order_by("nome")

    if pesquisa:
        tipos = tipos.filter(nome__icontains=pesquisa)

    paginator = Paginator(tipos, 10)
    page = request.GET.get("page")
    tipos = paginator.get_page(page)

    return render(request, "exames/listar.html", {
        "tipos": tipos,
        "pesquisa": pesquisa,
    })


def criar_tipo(request):
    form = TipoExameForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de exame cadastrado com sucesso.")
            return redirect("exames:listar_tipos")

    return render(request, "exames/form.html", {
        "form": form,
        "titulo": "Novo Tipo de Exame",
        "descricao": "Cadastre um tipo de exame disponível no sistema.",
    })


def editar_tipo(request, id):
    tipo = get_object_or_404(TipoExame, id=id)
    form = TipoExameForm(request.POST or None, instance=tipo)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de exame atualizado com sucesso.")
            return redirect("exames:listar_tipos")

    return render(request, "exames/form.html", {
        "form": form,
        "titulo": "Editar Tipo de Exame",
        "descricao": "Atualize as informações do tipo de exame.",
    })


def excluir_tipo(request, id):
    tipo = get_object_or_404(TipoExame, id=id)

    if request.method == "POST":
        tipo.delete()
        messages.success(request, "Tipo de exame excluído com sucesso.")

    return redirect("exames:listar_tipos")

def listar_agendamentos(request):
    agendamentos = Agendamento.objects.all().order_by("-data")

    return render(request, "agendamento/listar.html", {
        "agendamentos": agendamentos
    })

def limpar_cpf(cpf):
    return cpf.replace(".", "").replace("-", "").strip()


def criar_agendamento(request):
    usuario = None
    cpf_busca = request.GET.get("cpf")

    initial = {}

    if cpf_busca:
        cpf_limpo = limpar_cpf(cpf_busca)

        usuario = (
            Usuario.objects.filter(cpf=cpf_busca).first()
            or Usuario.objects.filter(cpf=cpf_limpo).first()
        )

        if usuario:
            initial = {
                "cpf": usuario.cpf,
                "nome": usuario.nome,
                "telefone": usuario.telefone,
            }
        else:
            messages.error(request, "Cidadão não encontrado. Cadastre o usuário antes de agendar.")

    form = AgendamentoForm(request.POST or None, initial=initial)

    if request.method == "POST":
        if form.is_valid():
            cpf = form.cleaned_data["cpf"]

            usuario = (
                Usuario.objects.filter(cpf=cpf).first()
                or Usuario.objects.filter(cpf=limpar_cpf(cpf)).first()
            )

            if not usuario:
                messages.error(request, "Cidadão não encontrado.")
                return redirect("exames:criar_agendamento")

            Agendamento.objects.create(
                usuario=usuario,
                tipo_exame=form.cleaned_data["tipo_exame"],
                unidade=form.cleaned_data["unidade"],
                data=form.cleaned_data["data"],
                observacao=form.cleaned_data["observacao"],
            )

            messages.success(request, "Exame agendado com sucesso.")
            return redirect("exames:listar_agendamentos")

    return render(request, "agendamento/form.html", {
        "form": form,
        "usuario": usuario,
        "cpf_busca": cpf_busca,
        "titulo": "Agendar Exame",
        "descricao": "Busque o cidadão pelo CPF e selecione o tipo de exame.",
    })
    
    
def meus_agendamentos(request):

    usuario = Usuario.objects.get(user=request.user)

    agendamentos = (
        Agendamento.objects
        .filter(usuario=usuario)
        .select_related(
            "tipo_exame",
            "unidade"
        )
        .order_by("data")
    )

    return render(
        request,
        "exames/meus_agendamentos.html",
        {
            "agendamentos": agendamentos
        }
    )


def meu_historico(request):

    usuario = Usuario.objects.get(user=request.user)

    exames = (
        Exame.objects
        .filter(usuario=usuario)
        .select_related(
            "profissional",
            "unidade"
        )
        .order_by("-data")
    )

    return render(
        request,
        "exames/meu_historico.html",
        {
            "exames": exames
        }
    )