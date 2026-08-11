from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from exames.models import Exame, TipoExame
from unidades.models import Profissional, UnidadeSaude
from usuarios.models import Usuario


def limpar_cpf(cpf):
    if not cpf:
        return ""
    return cpf.replace(".", "").replace("-", "").strip()


def home(request):
    return render(request, "home.html")


def login_view(request):
    if request.method == "POST":
        perfil_login = request.POST.get("perfil_login")
        cpf = request.POST.get("cpf")
        identificador = request.POST.get("identificador")
        senha = request.POST.get("senha")

        if perfil_login == "CIDADAO":
            try:
                usuario = Usuario.objects.get(cpf=cpf, perfil="CIDADAO")
                login(request, usuario.user)
                request.session["perfil"] = "CIDADAO"
                return redirect("core:dashboard_cidadao")
            except Usuario.DoesNotExist:
                messages.error(request, "Cidadão não encontrado.")
                return redirect("core:login")

        if perfil_login == "PROFISSIONAL_ADMIN":
            # Primeiro tenta login como admin usando username + senha
            user = authenticate(
                request,
                username=identificador,
                password=senha
            )

            if user is not None and user.is_superuser:
                login(request, user)
                request.session["perfil"] = "ADMIN"
                return redirect("core:dashboard_admin")

            # Depois tenta login como profissional usando CPF limpo + senha
            cpf_limpo = limpar_cpf(identificador)

            user = authenticate(
                request,
                username=cpf_limpo,
                password=senha
            )

            if user is not None:
                try:
                    profissional = Profissional.objects.get(cpf=identificador)
                except Profissional.DoesNotExist:
                    try:
                        profissional = Profissional.objects.get(cpf=cpf_limpo)
                    except Profissional.DoesNotExist:
                        messages.error(request, "Profissional não encontrado.")
                        return redirect("core:login")

                login(request, user)
                request.session["perfil"] = "PROFISSIONAL"
                return redirect("core:dashboard_profissional")

            messages.error(request, "Usuário/CPF ou senha inválidos.")
            return redirect("core:login")

    return render(request, "login.html")

def logout_view(request):
    request.session.flush()
    logout(request)
    messages.success(request, "Você saiu do sistema.")
    return redirect("core:login")


def dashboard_admin(request):
    contexto = {
        "total_usuarios": Usuario.objects.count(),
        "total_unidades": UnidadeSaude.objects.count(),
        "total_profissionais": Profissional.objects.count(),
        "total_tipos_exames": TipoExame.objects.count(),
    }

    return render(request, "dashboard/admin.html", contexto)


def dashboard_cidadao(request):
    usuario = Usuario.objects.filter(user=request.user).first()

    return render(request, "dashboard/cidadao.html", {
        "usuario": usuario
    })

def dashboard_profissional(request):
    return render(
        request,
        "dashboard/profissional.html",
        {
            "perfil": "PROFISSIONAL"
        }
    )


def relatorios(request):
    status = request.GET.get("status")
    unidade_id = request.GET.get("unidade")
    tipo_id = request.GET.get("tipo")

    exames = Exame.objects.all()

    if status:
        exames = exames.filter(status=status)

    if unidade_id:
        exames = exames.filter(unidade_id=unidade_id)

    if tipo_id:
        exames = exames.filter(tipo_id=tipo_id)

    contexto = {
        "total_usuarios": Usuario.objects.count(),
        "total_unidades": UnidadeSaude.objects.count(),
        "total_profissionais": Profissional.objects.count(),
        "total_exames": exames.count(),
        "exames": exames,
        "unidades": UnidadeSaude.objects.all(),
        "tipos": TipoExame.objects.all(),
        "status_choices": Exame.STATUS_CHOICES,
        "status_selecionado": status,
        "unidade_selecionada": unidade_id,
        "tipo_selecionado": tipo_id,
    }

    return render(request, "relatorio/relatorios.html", contexto)