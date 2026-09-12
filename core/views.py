from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Value,
    When,
)
from django.shortcuts import redirect, render

from escolas.models import (
    Escola,
    EscolaProblematica,
    TipoProblematica,
)
from usuarios.models import Usuario
from visitas.models import RondaVisita


def limpar_cpf(cpf):
    if not cpf:
        return ""

    return (
        cpf.replace(".", "")
        .replace("-", "")
        .strip()
    )


def home(request):
    return render(
        request,
        "home.html"
    )


def login_view(request):
    if request.method == "POST":
        identificador = request.POST.get(
            "identificador"
        )

        senha = request.POST.get(
            "senha"
        )

        cpf_limpo = limpar_cpf(
            identificador
        )

        user = authenticate(
            request,
            username=cpf_limpo,
            password=senha
        )

        # Permite acesso ao superusuário do Django
        if user is not None and user.is_superuser:
            login(
                request,
                user
            )

            request.session["perfil"] = "ADMIN"

            return redirect(
                "core:dashboard_admin"
            )

        if user is None:
            messages.error(
                request,
                "CPF ou senha inválidos."
            )

            return redirect(
                "core:login"
            )

        try:
            usuario = Usuario.objects.get(
                user=user
            )

        except Usuario.DoesNotExist:
            messages.error(
                request,
                "Usuário não cadastrado no Sistema RECOM."
            )

            return redirect(
                "core:login"
            )

        if not usuario.ativo:
            messages.error(
                request,
                "Este usuário está inativo."
            )

            return redirect(
                "core:login"
            )

        login(
            request,
            user
        )

        request.session["perfil"] = usuario.perfil

        if usuario.perfil == "ADMIN":
            return redirect(
                "core:dashboard_admin"
            )

        if usuario.perfil == "COORDENADOR":
            return redirect(
                "core:dashboard_coordenador"
            )

        if usuario.perfil == "GCM":
            return redirect(
                "core:dashboard_gcm"
            )

        if usuario.perfil == "MEDIADOR":
            return redirect(
                "core:dashboard_mediador"
            )

        messages.error(
            request,
            "Perfil de usuário inválido."
        )

        return redirect(
            "core:login"
        )

    return render(
        request,
        "login.html"
    )


def logout_view(request):
    request.session.flush()

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


def dashboard_admin(request):
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


# =============================================================
# PÁGINA PRINCIPAL DE RELATÓRIOS
# =============================================================

def relatorios(request):

    # =========================================================
    # INDICADORES GERAIS
    # =========================================================

    total_usuarios = Usuario.objects.count()

    total_escolas = Escola.objects.filter(
        ativa=True
    ).count()

    total_gcms = Usuario.objects.filter(
        perfil="GCM",
        ativo=True
    ).count()

    total_mediadores = Usuario.objects.filter(
        perfil="MEDIADOR",
        ativo=True
    ).count()


    # =========================================================
    # RESUMO DE PROBLEMÁTICAS
    # =========================================================

    total_problematicas = EscolaProblematica.objects.count()

    problematicas_ativas = EscolaProblematica.objects.filter(
        situacao="ATIVA"
    ).count()

    problematicas_em_acompanhamento = (
        EscolaProblematica.objects.filter(
            situacao="EM_ACOMPANHAMENTO"
        ).count()
    )

    problematicas_resolvidas = EscolaProblematica.objects.filter(
        situacao="RESOLVIDA"
    ).count()


    # =========================================================
    # RESUMO DE VISITAS
    # =========================================================

    total_visitas = RondaVisita.objects.count()

    visitas_sem_alteracao = RondaVisita.objects.filter(
        situacao="SEM_ALTERACAO"
    ).count()

    visitas_com_alteracao = RondaVisita.objects.filter(
        situacao="COM_ALTERACAO"
    ).count()


    # =========================================================
    # CONTEXTO
    # =========================================================

    contexto = {

        # Indicadores gerais
        "total_usuarios": total_usuarios,
        "total_escolas": total_escolas,
        "total_gcms": total_gcms,
        "total_mediadores": total_mediadores,


        # Problemáticas
        "total_problematicas": total_problematicas,
        "problematicas_ativas": problematicas_ativas,
        "problematicas_em_acompanhamento": (
            problematicas_em_acompanhamento
        ),
        "problematicas_resolvidas": problematicas_resolvidas,


        # Visitas
        "total_visitas": total_visitas,
        "visitas_sem_alteracao": visitas_sem_alteracao,
        "visitas_com_alteracao": visitas_com_alteracao,
    }


    return render(
        request,
        "relatorio/relatorios.html",
        contexto
    )


# =============================================================
# RELATÓRIO DETALHADO DE PROBLEMÁTICAS
# =============================================================

def relatorio_problematicas(request):

    # =========================================================
    # CONSULTA BASE
    # =========================================================

    problematicas = (
        EscolaProblematica.objects
        .select_related(
            "escola",
            "tipo_problematica"
        )
        .all()
        .order_by(
            "escola__nome",
            "tipo_problematica__nome"
        )
    )


    # =========================================================
    # FILTROS
    # =========================================================

    polo = request.GET.get(
        "polo",
        ""
    ).strip()

    escola_id = request.GET.get(
        "escola",
        ""
    ).strip()

    tipo_id = request.GET.get(
        "tipo",
        ""
    ).strip()

    situacao = request.GET.get(
        "situacao",
        ""
    ).strip()


    # =========================================================
    # APLICAÇÃO DOS FILTROS
    # =========================================================

    if polo:
        problematicas = problematicas.filter(
            escola__polo=polo
        )

    if escola_id:
        problematicas = problematicas.filter(
            escola_id=escola_id
        )

    if tipo_id:
        problematicas = problematicas.filter(
            tipo_problematica_id=tipo_id
        )

    if situacao:
        problematicas = problematicas.filter(
            situacao=situacao
        )


    # =========================================================
    # TOTAL
    # =========================================================

    total_problematicas = problematicas.count()


    # =========================================================
    # PAGINAÇÃO
    # =========================================================

    paginator = Paginator(
        problematicas,
        10
    )

    numero_pagina = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        numero_pagina
    )


    # =========================================================
    # ESCOLAS DO FILTRO
    # =========================================================

    escolas = Escola.objects.filter(
        ativa=True
    )

    if polo:
        escolas = escolas.filter(
            polo=polo
        )

    escolas = escolas.order_by(
        "nome"
    )


    # =========================================================
    # TIPOS DE PROBLEMÁTICA
    # =========================================================
    #
    # "Outras" permanece sempre por último.
    # =========================================================

    tipos_problematicas = (
        TipoProblematica.objects
        .filter(
            ativa=True
        )
        .annotate(
            ordem_outras=Case(
                When(
                    nome__iexact="Outras",
                    then=Value(1)
                ),
                default=Value(0),
                output_field=IntegerField()
            )
        )
        .order_by(
            "ordem_outras",
            "nome"
        )
    )


    # =========================================================
    # CONTEXTO
    # =========================================================

    contexto = {

        "page_obj": page_obj,

        "total_problematicas": total_problematicas,

        "polos": Escola.POLO_CHOICES,
        "escolas": escolas,
        "tipos_problematicas": tipos_problematicas,
        "situacoes": EscolaProblematica.SITUACAO_CHOICES,

        "polo_selecionado": polo,
        "escola_selecionada": escola_id,
        "tipo_selecionado": tipo_id,
        "situacao_selecionada": situacao,
    }


    return render(
        request,
        "relatorio/problematicas.html",
        contexto
    )


# =============================================================
# RELATÓRIO DETALHADO DE VISITAS
# =============================================================

def relatorio_visitas(request):

    # =========================================================
    # CONSULTA BASE
    # =========================================================

    visitas = (
        RondaVisita.objects
        .select_related(
            "escola"
        )
        .all()
        .order_by(
            "-data_visita",
            "-horario"
        )
    )


    # =========================================================
    # FILTROS
    # =========================================================

    polo = request.GET.get(
        "polo",
        ""
    ).strip()

    escola_id = request.GET.get(
        "escola",
        ""
    ).strip()

    equipe = request.GET.get(
        "equipe",
        ""
    ).strip()

    situacao = request.GET.get(
        "situacao",
        ""
    ).strip()

    data_inicial = request.GET.get(
        "data_inicial",
        ""
    ).strip()

    data_final = request.GET.get(
        "data_final",
        ""
    ).strip()


    # =========================================================
    # APLICAÇÃO DOS FILTROS
    # =========================================================

    if polo:
        visitas = visitas.filter(
            escola__polo=polo
        )

    if escola_id:
        visitas = visitas.filter(
            escola_id=escola_id
        )

    if equipe:
        visitas = visitas.filter(
            equipe=equipe
        )

    if situacao:
        visitas = visitas.filter(
            situacao=situacao
        )

    if data_inicial:
        visitas = visitas.filter(
            data_visita__gte=data_inicial
        )

    if data_final:
        visitas = visitas.filter(
            data_visita__lte=data_final
        )


    # =========================================================
    # TOTAL DE VISITAS
    # =========================================================

    total_visitas = visitas.count()


    # =========================================================
    # PAGINAÇÃO
    # =========================================================
    #
    # Exibe 10 visitas por página.
    # =========================================================

    paginator = Paginator(
        visitas,
        10
    )

    numero_pagina = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        numero_pagina
    )


    # =========================================================
    # ESCOLAS DISPONÍVEIS NO FILTRO
    # =========================================================

    escolas = Escola.objects.filter(
        ativa=True
    )

    if polo:
        escolas = escolas.filter(
            polo=polo
        )

    escolas = escolas.order_by(
        "nome"
    )


    # =========================================================
    # CONTEXTO
    # =========================================================

    contexto = {

        # Paginação
        "page_obj": page_obj,


        # Total encontrado
        "total_visitas": total_visitas,


        # Opções dos filtros
        "polos": Escola.POLO_CHOICES,

        "escolas": escolas,

        "equipes": RondaVisita.EQUIPE_CHOICES,

        "situacoes": RondaVisita.SITUACAO_CHOICES,


        # Valores selecionados
        "polo_selecionado": polo,

        "escola_selecionada": escola_id,

        "equipe_selecionada": equipe,

        "situacao_selecionada": situacao,

        "data_inicial": data_inicial,

        "data_final": data_final,
    }


    return render(
        request,
        "relatorio/visitas.html",
        contexto
    )