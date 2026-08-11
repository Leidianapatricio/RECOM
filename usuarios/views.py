from django.core.paginator import Paginator
from django.shortcuts import render

from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from .models import Usuario

def listar_usuarios(request):
    usuarios = Usuario.objects.all().order_by("nome")
    paginator = Paginator(usuarios, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "usuarios/listar.html", {
        "page_obj": page_obj
    })

def criar_usuario(request):
    if request.method == "POST":
        nome = request.POST.get("nome")
        cpf = request.POST.get("cpf")
        cartao_sus = request.POST.get("cartao_sus")
        sexo = request.POST.get("sexo")
        email = request.POST.get("email")
        telefone = request.POST.get("telefone")

        username = cpf.replace(".", "").replace("-", "")

        user = User.objects.create_user(
            username=username,
            password=username
          
        )

        Usuario.objects.create(
            user=user,
            nome=nome,
            cpf=cpf,
            cartao_sus=cartao_sus,
            sexo=sexo,
            email=email,
            telefone=telefone
        )

        return redirect("usuarios:listar")

    return render(request, "usuarios/form.html")

def minhas_notificacoes(request):

    return render(
        request,
        "usuarios/notificacoes.html"
    )
