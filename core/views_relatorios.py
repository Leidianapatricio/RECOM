
import csv
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Value, When
from django.http import HttpResponse
from django.shortcuts import render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    LongTable,
)

from cartao_programa.models import EfetivoViatura
from escolas.models import Escola, EscolaProblematica, TipoProblematica
from usuarios.models import Usuario
from visitas.models import RondaVisita


# =============================================================
# FUNÇÕES AUXILIARES
# =============================================================


def _perfil_usuario(request):
    """
    Identifica o perfil do usuário no RECOM.
    """
    usuario = _usuario_recom(request)

    if usuario is None:
        return None

    return str(usuario.perfil).strip().upper()


def _usuario_recom(request):
    """
    Recupera o cadastro RECOM associado ao
    usuário autenticado no Django.
    """
    if not request.user.is_authenticated:
        return None

    return Usuario.objects.filter(
        user=request.user,
        ativo=True
    ).first()



def _data_valida(valor):
    """
    Converte uma data no formato YYYY-MM-DD.
    """

    if not valor:
        return None

    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _query_filtros(request):
    """
    Preserva os filtros na paginação.
    """

    parametros = request.GET.copy()
    parametros.pop("page", None)

    return parametros.urlencode()


def _visitas_permitidas(request):
    """
    Retorna somente as visitas que o perfil pode consultar.

    Coordenador e administrador:
        Todas as visitas.

    GCM:
        Visitas programadas vinculadas às viaturas
        nas quais consta como integrante do efetivo.

    Visitas avulsas:
        Não são incluídas no relatório individual do
        GCM porque o modelo atual não registra o autor.
    """

    usuario = _usuario_recom(request)
    perfil = _perfil_usuario(request)

    visitas = (
        RondaVisita.objects
        .select_related("escola", "missao_cartao")
        .order_by("-data_visita", "-horario", "-pk")
    )

    if request.user.is_superuser:
        return visitas

    if perfil in ("ADMIN", "COORDENADOR"):
        return visitas

    if perfil == "GCM":

        if usuario is None:
            raise PermissionDenied(
                "Não foi possível identificar o GCM autenticado."
            )

        viaturas = (
            EfetivoViatura.objects
            .filter(gcm=usuario)
            .values_list("viatura_id", flat=True)
        )

        return visitas.filter(
            missao_cartao__viatura_id__in=viaturas
        )

    raise PermissionDenied(
        "Você não possui permissão para consultar "
        "o relatório de visitas."
    )


def _consultar_visitas(request):
    """
    Consulta compartilhada pela tela, PDF e CSV.

    Todos os filtros são aplicados antes da paginação.
    """

    visitas = _visitas_permitidas(request)

    polo = request.GET.get("polo", "").strip()
    escola_id = request.GET.get("escola", "").strip()
    equipe = request.GET.get("equipe", "").strip()
    tipo_visita = request.GET.get("tipo_visita", "").strip()
    situacao = request.GET.get("situacao", "").strip()

    data_inicial = request.GET.get(
        "data_inicial", ""
    ).strip()

    data_final = request.GET.get(
        "data_final", ""
    ).strip()

    # POLO
    polos_validos = {
        str(codigo)
        for codigo, _ in Escola.POLO_CHOICES
    }

    if polo in polos_validos:
        visitas = visitas.filter(
            escola__polo=polo
        )

    # ESCOLA
    if escola_id.isdigit():
        visitas = visitas.filter(
            escola_id=int(escola_id)
        )

    # EQUIPE
    equipes_validas = dict(
        RondaVisita.EQUIPE_CHOICES
    )

    if equipe in equipes_validas:
        visitas = visitas.filter(
            equipe=equipe
        )

    # TIPO DE VISITA
    tipos_validos = dict(
        RondaVisita.TIPO_VISITA_CHOICES
    )

    if tipo_visita in tipos_validos:
        visitas = visitas.filter(
            tipo_visita=tipo_visita
        )

    # SITUAÇÃO
    situacoes_validas = dict(
        RondaVisita.SITUACAO_CHOICES
    )

    if situacao in situacoes_validas:
        visitas = visitas.filter(
            situacao=situacao
        )

    # PERÍODO
    inicio = _data_valida(data_inicial)
    fim = _data_valida(data_final)

    if inicio:
        visitas = visitas.filter(
            data_visita__gte=inicio
        )

    if fim:
        visitas = visitas.filter(
            data_visita__lte=fim
        )

    filtros = {
        "polo_selecionado": polo,
        "escola_selecionada": escola_id,
        "equipe_selecionada": equipe,
        "tipo_visita_selecionado": tipo_visita,
        "situacao_selecionada": situacao,
        "data_inicial": data_inicial,
        "data_final": data_final,
    }

    return visitas, filtros


def _escolas_disponiveis(request, polo=""):
    """
    Escolas apresentadas no filtro.
    """

    escolas = Escola.objects.filter(ativa=True)

    if polo:
        escolas = escolas.filter(polo=polo)

    if _perfil_usuario(request) == "GCM":

        usuario = _usuario_recom(request)

        if usuario is None:
            return escolas.none()

        viaturas = (
            EfetivoViatura.objects
            .filter(gcm=usuario)
            .values_list("viatura_id", flat=True)
        )

        escolas_ids = (
            RondaVisita.objects
            .filter(
                missao_cartao__viatura_id__in=viaturas
            )
            .values_list("escola_id", flat=True)
        )

        escolas = escolas.filter(
            pk__in=escolas_ids
        )

    return escolas.order_by("nome")


# =============================================================
# PÁGINA PRINCIPAL DE RELATÓRIOS
# =============================================================

@login_required
def relatorios(request):

    # O GCM acessa diretamente o relatório de visitas.
    if _perfil_usuario(request) == "GCM":
        return relatorio_visitas(request)

    # Indicadores gerais
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

    # Problemáticas
    total_problematicas = (
        EscolaProblematica.objects.count()
    )

    problematicas_ativas = (
        EscolaProblematica.objects.filter(
            situacao="ATIVA"
        ).count()
    )

    problematicas_em_acompanhamento = (
        EscolaProblematica.objects.filter(
            situacao="EM_ACOMPANHAMENTO"
        ).count()
    )

    problematicas_resolvidas = (
        EscolaProblematica.objects.filter(
            situacao="RESOLVIDA"
        ).count()
    )

    # Visitas
    total_visitas = RondaVisita.objects.count()

    visitas_sem_alteracao = (
        RondaVisita.objects.filter(
            situacao="SEM_ALTERACAO"
        ).count()
    )

    visitas_com_alteracao = (
        RondaVisita.objects.filter(
            situacao="COM_ALTERACAO"
        ).count()
    )

    contexto = {
        "total_usuarios": total_usuarios,
        "total_escolas": total_escolas,
        "total_gcms": total_gcms,
        "total_mediadores": total_mediadores,

        "total_problematicas": total_problematicas,
        "problematicas_ativas": problematicas_ativas,
        "problematicas_em_acompanhamento": (
            problematicas_em_acompanhamento
        ),
        "problematicas_resolvidas": problematicas_resolvidas,

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

@login_required
def relatorio_problematicas(request):

    problematicas = (
        EscolaProblematica.objects
        .select_related(
            "escola",
            "tipo_problematica"
        )
        .order_by(
            "escola__nome",
            "tipo_problematica__nome"
        )
    )

    # Filtros
    polo = request.GET.get("polo", "").strip()
    escola_id = request.GET.get("escola", "").strip()
    tipo_id = request.GET.get("tipo", "").strip()
    situacao = request.GET.get("situacao", "").strip()

    if polo:
        problematicas = problematicas.filter(
            escola__polo=polo
        )

    if escola_id.isdigit():
        problematicas = problematicas.filter(
            escola_id=int(escola_id)
        )

    if tipo_id.isdigit():
        problematicas = problematicas.filter(
            tipo_problematica_id=int(tipo_id)
        )

    if situacao:
        problematicas = problematicas.filter(
            situacao=situacao
        )

    total_problematicas = problematicas.count()

    # Paginação
    paginator = Paginator(
        problematicas,
        10
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # Escolas
    escolas = Escola.objects.filter(
        ativa=True
    )

    if polo:
        escolas = escolas.filter(
            polo=polo
        )

    escolas = escolas.order_by("nome")

    # Tipos de problemática
    tipos_problematicas = (
        TipoProblematica.objects
        .filter(ativa=True)
        .annotate(
            ordem_outras=Case(
                When(
                    nome__iexact="Outras",
                    then=Value(1)
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "ordem_outras",
            "nome"
        )
    )

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

@login_required
def relatorio_visitas(request):

    visitas, filtros = _consultar_visitas(request)

    # Total de resultados filtrados
    total_visitas = visitas.count()

    # Paginação apenas na tela
    paginator = Paginator(
        visitas,
        10
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    escolas = _escolas_disponiveis(
        request,
        filtros["polo_selecionado"]
    )

    contexto = {
        "page_obj": page_obj,
        "total_visitas": total_visitas,

        # Opções dos filtros
        "polos": Escola.POLO_CHOICES,
        "escolas": escolas,
        "equipes": RondaVisita.EQUIPE_CHOICES,
        "tipos_visita": RondaVisita.TIPO_VISITA_CHOICES,
        "situacoes": RondaVisita.SITUACAO_CHOICES,

        # Paginação
        "query_filtros": _query_filtros(request),

        # Perfil
        "eh_gcm": _perfil_usuario(request) == "GCM",
    }

    contexto.update(filtros)

    return render(
        request,
        "relatorio/visitas.html",
        contexto
    )


# =============================================================
# EXPORTAÇÃO CSV
# =============================================================

@login_required
def exportar_visitas_csv(request):

    visitas, filtros = _consultar_visitas(request)

    resposta = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    resposta["Content-Disposition"] = (
        'attachment; filename="relatorio_visitas_recom.csv"'
    )

    # BOM para reconhecimento de UTF-8 pelo Excel.
    resposta.write("\ufeff")

    escritor = csv.writer(
        resposta,
        delimiter=";"
    )

    escritor.writerow([
        "Data",
        "Horário",
        "Escola",
        "Polo",
        "Equipe",
        "Tipo de visita",
        "Situação",
        "Relato",
        "Orientações / Providências",
    ])

    for visita in visitas.iterator():

        escritor.writerow([
            visita.data_visita.strftime("%d/%m/%Y"),
            visita.horario.strftime("%H:%M") if visita.horario else "",
            visita.escola.nome,
            visita.escola.get_polo_display(),
            visita.get_equipe_display(),
            visita.get_tipo_visita_display(),
            visita.get_situacao_display(),
            visita.relato or "",
            visita.orientacoes or "",
        ])

    return resposta


# =============================================================
# EXPORTAÇÃO PDF
# =============================================================

@login_required
def exportar_visitas_pdf(request):

    visitas, filtros = _consultar_visitas(request)

    total_visitas = visitas.count()

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Relatório de Visitas - RECOM",
        author="RECOM",
    )

    estilos = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        "TituloRECOM",
        parent=estilos["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#092B49"),
        spaceAfter=5 * mm,
    )

    estilo_subtitulo = ParagraphStyle(
        "SubtituloRECOM",
        parent=estilos["Normal"],
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    estilo_celula = ParagraphStyle(
        "CelulaRECOM",
        parent=estilos["Normal"],
        fontSize=6,
        leading=8,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )

    estilo_cabecalho = ParagraphStyle(
        "CabecalhoTabelaRECOM",
        parent=estilo_celula,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    def paragrafo(valor, estilo=estilo_celula):
        texto = escape(str(valor or "-"))
        texto = texto.replace("\n", "<br/>")
        return Paragraph(texto, estilo)

    elementos = []

    elementos.append(
        Paragraph(
            "RECOM - Ronda Escolar Comunitária",
            estilo_titulo
        )
    )

    elementos.append(
        Paragraph(
            "Relatório de Visitas",
            estilo_subtitulo
        )
    )

    elementos.append(
        Paragraph(
            f"Total de visitas encontradas: {total_visitas}",
            estilo_subtitulo
        )
    )

    elementos.append(
        Spacer(1, 3 * mm)
    )

    cabecalhos = [
        "Data",
        "Hora",
        "Escola",
        "Polo",
        "Equipe",
        "Tipo",
        "Situação",
        "Relato",
        "Orientações / Providências",
    ]

    dados = [
        [
            paragrafo(campo, estilo_cabecalho)
            for campo in cabecalhos
        ]
    ]

    for visita in visitas.iterator():

        dados.append([
            paragrafo(
                visita.data_visita.strftime("%d/%m/%Y")
            ),
            paragrafo(
                visita.horario.strftime("%H:%M")
                if visita.horario else ""
            ),
            paragrafo(visita.escola.nome),
            paragrafo(
                visita.escola.get_polo_display()
            ),
            paragrafo(
                visita.get_equipe_display()
            ),
            paragrafo(
                visita.get_tipo_visita_display()
            ),
            paragrafo(
                visita.get_situacao_display()
            ),
            paragrafo(visita.relato),
            paragrafo(visita.orientacoes),
        ])

    largura_util = landscape(A4)[0] - 20 * mm

    proporcoes = [
        0.07,  # Data
        0.05,  # Hora
        0.14,  # Escola
        0.05,  # Polo
        0.07,  # Equipe
        0.10,  # Tipo
        0.09,  # Situação
        0.20,  # Relato
        0.23,  # Orientações
    ]

    larguras = [
        largura_util * proporcao
        for proporcao in proporcoes
    ]

    tabela = LongTable(
        dados,
        colWidths=larguras,
        repeatRows=1,
        hAlign="CENTER",
    )

    tabela.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#092B49")
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.HexColor("#CBD5DF")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F3F6F9")
                ]
            ),
        ])
    )

    elementos.append(tabela)

    def rodape(canvas, doc):
        canvas.saveState()

        canvas.setFont(
            "Helvetica",
            8
        )

        canvas.setFillColor(
            colors.HexColor("#555555")
        )

        canvas.drawString(
            10 * mm,
            7 * mm,
            "RECOM - Relatório de Visitas"
        )

        canvas.drawRightString(
            landscape(A4)[0] - 10 * mm,
            7 * mm,
            f"Página {doc.page}"
        )

        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=rodape,
        onLaterPages=rodape,
    )

    pdf = buffer.getvalue()
    buffer.close()

    resposta = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    resposta["Content-Disposition"] = (
        'attachment; filename="relatorio_visitas_recom.pdf"'
    )

    return resposta
