from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from escolas.models import (
    Escola,
    EscolaProblematica,
)

from mediacao.models import (
    PlanejamentoMediacao,
    AtividadeMediacao,
)

from usuarios.models import Usuario
from visitas.models import RondaVisita

def home(request):
    return render(
        request,
        "home.html"
    )

def redirecionar_por_perfil(usuario):
    if usuario.perfil == "ADMIN":
        return redirect("core:dashboard_admin")

    if usuario.perfil == "COORDENADOR":
        return redirect("core:dashboard_coordenador")

    if usuario.perfil == "GCM":
        return redirect("core:dashboard_gcm")

    if usuario.perfil == "MEDIADOR":
        return redirect("core:dashboard_mediador")

    return redirect("core:home")


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        if not request.user.is_active:
            logout(request)
            messages.error(request, "Este usuário está inativo.")
            return redirect("core:login")

        if request.user.is_superuser:
            return redirect("core:dashboard_admin")

        try:
            usuario = request.user.usuario
        except Usuario.DoesNotExist:
            logout(request)
            messages.error(
                request,
                "Usuário sem perfil cadastrado no sistema."
            )
            return redirect("core:login")

        if not usuario.ativo:
            logout(request)
            messages.error(
                request,
                "Este usuário está inativo. Procure o administrador."
            )
            return redirect("core:login")

        if usuario.primeiro_acesso:
            return redirect("core:primeiro_acesso")

        return redirecionar_por_perfil(usuario)

    if request.method == "POST":
        matricula = request.POST.get("matricula", "").strip()
        senha = request.POST.get("senha", "")

        if not matricula or not senha:
            messages.error(
                request,
                "Informe a matrícula e a senha."
            )
            return render(request, "login.html")

        user = authenticate(
            request,
            username=matricula,
            password=senha
        )

        if user is None:
            messages.error(
                request,
                "Matrícula ou senha inválidos."
            )
            return render(request, "login.html")

        if not user.is_active:
            messages.error(
                request,
                "Este usuário está inativo."
            )
            return render(request, "login.html")

        # O superusuário Django pode usar login alfanumérico (ex.: admin).
        # Os demais usuários RECOM devem usar matrícula numérica.
        if not user.is_superuser and not matricula.isdigit():
            messages.error(
                request,
                "A matrícula deve conter somente números."
            )
            return render(request, "login.html")

        # Mantém o acesso do superusuário do Django.
        if user.is_superuser:
            login(request, user)
            return redirect("core:dashboard_admin")

        try:
            usuario = user.usuario
        except Usuario.DoesNotExist:
            messages.error(
                request,
                "Usuário sem perfil cadastrado no sistema."
            )
            return render(request, "login.html")

        if not usuario.ativo:
            messages.error(
                request,
                "Este usuário está inativo. Procure o administrador."
            )
            return render(request, "login.html")

        login(request, user)

        if usuario.primeiro_acesso:
            return redirect("core:primeiro_acesso")

        return redirecionar_por_perfil(usuario)

    return render(request, "login.html")


@never_cache
def primeiro_acesso(request):
    if not request.user.is_authenticated:
        return redirect("core:login")

    if request.user.is_superuser:
        return redirect("core:dashboard_admin")

    try:
        usuario = request.user.usuario
    except Usuario.DoesNotExist:
        logout(request)
        messages.error(
            request,
            "Usuário sem perfil cadastrado no sistema."
        )
        return redirect("core:login")

    if not usuario.ativo:
        logout(request)
        messages.error(
            request,
            "Este usuário está inativo. Procure o administrador."
        )
        return redirect("core:login")

    # Se já realizou o primeiro acesso, não permite voltar
    # à tela de definição da senha inicial.
    if not usuario.primeiro_acesso:
        return redirecionar_por_perfil(usuario)

    if request.method == "POST":
        nova_senha = request.POST.get("nova_senha", "")
        confirmar_senha = request.POST.get("confirmar_senha", "")

        if not nova_senha or not confirmar_senha:
            messages.error(
                request,
                "Informe a nova senha e a confirmação."
            )
            return render(request, "primeiro_acesso.html")

        if not nova_senha.isdigit() or len(nova_senha) != 4:
            messages.error(
                request,
                "A nova senha deve conter exatamente 4 números."
            )
            return render(request, "primeiro_acesso.html")

        if nova_senha == "1234":
            messages.error(request, "A nova senha deve ser diferente da senha provisória.")
            return render(request, "primeiro_acesso.html")

        if nova_senha != confirmar_senha:
            messages.error(
                request,
                "As senhas informadas não coincidem."
            )
            return render(request, "primeiro_acesso.html")

        request.user.set_password(nova_senha)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)

        usuario.primeiro_acesso = False
        usuario.save(update_fields=["primeiro_acesso"])


        messages.success(
            request,
            "Senha cadastrada com sucesso."
        )

        return redirecionar_por_perfil(usuario)

    return render(request, "primeiro_acesso.html")


def logout_view(request):
    logout(
        request
    )

    messages.success(
        request,
        "Você saiu do sistema."
    )

    return redirect(
        "core:login"
    )

def verificar_acesso_dashboard(request, perfil_permitido):
    """
    Verifica se o usuário possui permissão
    para acessar determinado dashboard.
    """

    # Usuário não autenticado
    if not request.user.is_authenticated:
        messages.error(
            request,
            "Faça login para acessar o sistema."
        )
        return redirect("core:login")

    # Superusuário Django
    if request.user.is_superuser:
        if perfil_permitido == "ADMIN":
            return None

        return redirect("core:dashboard_admin")

    # Busca o perfil RECOM
    try:
        usuario = request.user.usuario
    except Usuario.DoesNotExist:
        logout(request)

        messages.error(
            request,
            "Usuário sem perfil cadastrado no sistema."
        )

        return redirect("core:login")

    # Usuário RECOM inativo
    if not usuario.ativo:
        logout(request)

        messages.error(
            request,
            "Este usuário está inativo. Procure o administrador."
        )

        return redirect("core:login")

    # Primeiro acesso ainda não concluído
    if usuario.primeiro_acesso:
        return redirect("core:primeiro_acesso")

    # Perfil correto
    if usuario.perfil == perfil_permitido:
        return None

    # Tentativa de acessar dashboard de outro perfil
    messages.warning(
        request,
        "Você não possui permissão para acessar essa página."
    )

    return redirecionar_por_perfil(usuario)

def dashboard_admin(request):
    acesso = verificar_acesso_dashboard(request, "ADMIN")
    if acesso:
        return acesso

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
        "dashboard/admin.html",
        contexto
    )


def dashboard_coordenador(request):
    acesso = verificar_acesso_dashboard(request, "COORDENADOR")
    if acesso:
        return acesso

    total_escolas = Escola.objects.count()

    escolas_ativas = Escola.objects.filter(
        ativa=True
    ).count()

    escolas_inativas = Escola.objects.filter(
        ativa=False
    ).count()

    total_problematicas = EscolaProblematica.objects.count()

    total_visitas = RondaVisita.objects.count()

    visitas_sem_alteracao = RondaVisita.objects.filter(
        situacao="SEM_ALTERACAO"
    ).count()

    visitas_com_alteracao = RondaVisita.objects.filter(
        situacao="COM_ALTERACAO"
    ).count()

    total_gcms = Usuario.objects.filter(
        perfil="GCM",
        ativo=True
    ).count()

    total_mediadores = Usuario.objects.filter(
        perfil="MEDIADOR",
        ativo=True
    ).count()

    escolas_por_polo = (
        Escola.objects
        .filter(
            ativa=True
        )
        .values(
            "polo"
        )
        .annotate(
            total=Count("id")
        )
        .order_by(
            "polo"
        )
    )

    problematicas_por_tipo = (
        EscolaProblematica.objects
        .values(
            "tipo_problematica__nome"
        )
        .annotate(
            total=Count("id")
        )
        .order_by(
            "-total",
            "tipo_problematica__nome"
        )
    )

    contexto = {
        "total_escolas": total_escolas,
        "escolas_ativas": escolas_ativas,
        "escolas_inativas": escolas_inativas,

        "total_problematicas": total_problematicas,

        "total_visitas": total_visitas,
        "visitas_sem_alteracao": visitas_sem_alteracao,
        "visitas_com_alteracao": visitas_com_alteracao,

        "total_gcms": total_gcms,
        "total_mediadores": total_mediadores,

        "escolas_por_polo": escolas_por_polo,
        "problematicas_por_tipo": problematicas_por_tipo,
    }

    return render(
        request,
        "dashboard/coordenador.html",
        contexto
    )

def dashboard_gcm(request):
    acesso = verificar_acesso_dashboard(
        request,
        "GCM"
    )

    if acesso:
        return acesso

    usuario = request.user.usuario

    return render(
        request,
        "dashboard/gcm.html",
        {
            "usuario": usuario
        }
    )


def dashboard_mediador(request):

    acesso = verificar_acesso_dashboard(
        request,
        "MEDIADOR"
    )

    if acesso:
        return acesso

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True,
        perfil="MEDIADOR",
    ).first()

    if usuario is None:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "Perfil de Mediador não encontrado."
        )

    # ==========================================
    # ESCOLAS ATIVAS
    # ==========================================

    escolas = (
        Escola.objects
        .filter(ativa=True)
        .order_by("polo", "nome")
    )

    # ==========================================
    # PLANEJAMENTOS RECENTES
    # ==========================================

    planejamentos_recentes = (
        PlanejamentoMediacao.objects
        .filter(mediador=usuario)
        .select_related("escola")
        .order_by("-data", "-criado_em")[:5]
    )

    # ==========================================
    # ATIVIDADES RECENTES
    # ==========================================

    atividades_recentes = (
        AtividadeMediacao.objects
        .filter(mediador_responsavel=usuario)
        .select_related("escola")
        .order_by("-data", "-criado_em")[:5]
    )

    contexto = {
        "usuario": usuario,
        "escolas": escolas,
        "planejamentos_recentes": planejamentos_recentes,
        "atividades_recentes": atividades_recentes,
    }

    return render(
        request,
        "dashboard/mediador.html",
        contexto
    )
