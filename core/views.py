from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from escolas.models import Escola
from usuarios.models import Usuario


def limpar_cpf(cpf):
    if not cpf:
        return ""

    return (
        cpf.replace(".", "")
        .replace("-", "")
        .strip()
    )


def home(request):
    return render(request, "home.html")


def login_view(request):
    if request.method == "POST":
        identificador = request.POST.get("identificador")
        senha = request.POST.get("senha")

        cpf_limpo = limpar_cpf(identificador)

        user = authenticate(
            request,
            username=cpf_limpo,
            password=senha
        )

        # Permite acesso ao superusuário do Django
        if user is not None and user.is_superuser:
            login(request, user)
            request.session["perfil"] = "ADMIN"

            return redirect("core:dashboard_admin")

        if user is None:
            messages.error(
                request,
                "CPF ou senha inválidos."
            )
            return redirect("core:login")

        try:
            usuario = Usuario.objects.get(user=user)

        except Usuario.DoesNotExist:
            messages.error(
                request,
                "Usuário não cadastrado no Sistema RECOM."
            )
            return redirect("core:login")

        if not usuario.ativo:
            messages.error(
                request,
                "Este usuário está inativo."
            )
            return redirect("core:login")

        login(request, user)

        request.session["perfil"] = usuario.perfil

        if usuario.perfil == "ADMIN":
            return redirect("core:dashboard_admin")

        if usuario.perfil == "COORDENADOR":
            return redirect("core:dashboard_coordenador")

        if usuario.perfil == "GCM":
            return redirect("core:dashboard_gcm")

        if usuario.perfil == "MEDIADOR":
            return redirect("core:dashboard_mediador")

        messages.error(
            request,
            "Perfil de usuário inválido."
        )

        return redirect("core:login")

    return render(request, "login.html")


def logout_view(request):
    request.session.flush()
    logout(request)

    messages.success(
        request,
        "Você saiu do sistema."
    )

    return redirect("core:login")


def dashboard_admin(request):
    contexto = {
        "total_usuarios": Usuario.objects.count(),
        "total_escolas": Escola.objects.filter(ativa=True).count(),
        "total_gcms": Usuario.objects.filter(
            perfil="GCM",
            ativo=True
        ).count(),
        "total_mediadores": Usuario.objects.filter(
            perfil="MEDIADOR",
            ativo=True
        ).count(),
    }

    return render(
        request,
        "dashboard/admin.html",
        contexto
    )


def dashboard_coordenador(request):
    contexto = {
        "total_escolas": Escola.objects.filter(ativa=True).count(),
        "total_gcms": Usuario.objects.filter(
            perfil="GCM",
            ativo=True
        ).count(),
    }

    return render(
        request,
        "dashboard/coordenador.html",
        contexto
    )


def dashboard_gcm(request):
    usuario = Usuario.objects.filter(
        user=request.user
    ).first()

    return render(
        request,
        "dashboard/gcm.html",
        {
            "usuario": usuario
        }
    )


def dashboard_mediador(request):
    usuario = Usuario.objects.filter(
        user=request.user
    ).first()

    return render(
        request,
        "dashboard/mediador.html",
        {
            "usuario": usuario
        }
    )


def relatorios(request):
    contexto = {
        "total_usuarios": Usuario.objects.count(),

        "total_escolas": Escola.objects.filter(
            ativa=True
        ).count(),

        "total_gcms": Usuario.objects.filter(
            perfil="GCM",
            ativo=True
        ).count(),

        "total_mediadores": Usuario.objects.filter(
            perfil="MEDIADOR",
            ativo=True
        ).count(),
    }

    return render(
        request,
        "relatorio/relatorios.html",
        contexto
    )