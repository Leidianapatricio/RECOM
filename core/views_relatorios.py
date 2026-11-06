
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


def _autorizar_relatorios(request):
    """Autoriza consultas de relatórios para ADMIN, COORDENADOR e GCM."""
    if request.user.is_superuser:
        return

    if _perfil_usuario(request) not in ("ADMIN", "COORDENADOR", "GCM"):
        raise PermissionDenied(
            "Você não possui permissão para consultar os relatórios."
        )


def _visitas_permitidas(request):
    """
    Permite consultar todas as visitas aos perfis
    ADMIN, COORDENADOR e GCM.

    Inclui visitas programadas e avulsas.
    """

    perfil = _perfil_usuario(request)

    if not request.user.is_authenticated:
        raise PermissionDenied(
            "É necessário estar autenticado."
        )

    if not request.user.is_superuser and perfil not in (
        "ADMIN",
        "COORDENADOR",
        "GCM",
    ):
        raise PermissionDenied(
            "Você não possui permissão para consultar "
            "o relatório de visitas."
        )

    return (
        RondaVisita.objects
        .select_related("escola", "missao_cartao")
        .order_by("-data_visita", "-horario", "-pk")
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
    """Lista escolas ativas para os filtros dos perfis autorizados."""
    _autorizar_relatorios(request)
    escolas = Escola.objects.filter(ativa=True)
    if polo:
        escolas = escolas.filter(polo=polo)
    return escolas.order_by("nome")


# =============================================================
# PÁGINA PRINCIPAL DE RELATÓRIOS
# =============================================================

@login_required
def relatorios(request):

    _autorizar_relatorios(request)

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

    _autorizar_relatorios(request)

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
# AGRUPAMENTO POR CARTÃO PROGRAMA / VIATURA
# =============================================================

def _grupos_visitas(visitas):
    """Agrupa registros por missão vinculada à viatura do plantão.

    Os registros avulsos permanecem em grupo próprio. A ordem dos
    grupos segue a primeira ocorrência no conjunto recebido.
    """
    grupos = {}
    for visita in visitas:
        missao = visita.missao_cartao
        viatura = missao.viatura if missao else None
        chave = (missao.cartao_id, viatura.pk) if missao else (None, None)

        if chave not in grupos:
            if viatura:
                efetivo = sorted(
                    viatura.efetivo.all(),
                    key=lambda item: {"C": 0, "M": 1, "P1": 2, "P2": 3}.get(item.funcao, 9)
                )
                titulo = (
                    f"Cartão Programa {missao.cartao.plantao.data:%d/%m/%Y}"
                    f" — VTR {viatura.identificacao}"
                )
                equipe = viatura.equipe.nome if viatura.equipe_id else "Equipe não informada"
            else:
                efetivo = []
                titulo = "Visitas sem missão vinculada"
                equipe = "Não se aplica"

            grupos[chave] = {
                "titulo": titulo,
                "equipe": equipe,
                "efetivo": efetivo,
                "visitas": [],
            }
        grupos[chave]["visitas"].append(visita)
    return list(grupos.values())


def _visitas_com_efetivo(visitas):
    """Evita consultas repetidas ao buscar os integrantes das viaturas."""
    return visitas.select_related(
        "escola", "missao_cartao__cartao__plantao",
        "missao_cartao__viatura__equipe"
    ).prefetch_related(
        "missao_cartao__viatura__efetivo__gcm"
    )


# =============================================================
# RELATÓRIO DETALHADO DE VISITAS
# =============================================================

@login_required
def relatorio_visitas(request):

    visitas, filtros = _consultar_visitas(request)

    # Exibe o efetivo somente após o envio do formulário de filtros.
    # A navegação por páginas não conta como uma nova consulta.
    campos_filtro = (
        "polo", "escola", "equipe", "tipo_visita",
        "situacao", "data_inicial", "data_final",
    )
    consulta_realizada = any(campo in request.GET for campo in campos_filtro)

    # Total de resultados filtrados
    total_visitas = visitas.count()

    # Paginação apenas na tela
    paginator = Paginator(
        _visitas_com_efetivo(visitas),
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
        "grupos_visitas": _grupos_visitas(page_obj.object_list),
        "consulta_realizada": consulta_realizada,
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
# EXPORTAÇÃO CSV - VISITAS COM EFETIVO DESIGNADO
# =============================================================

@login_required
def exportar_visitas_csv(request):

    # Mantém os filtros e as permissões já existentes.
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

    # ==========================================
    # CABEÇALHO DAS VISITAS
    # ==========================================

    cabecalho = [
        "Data",
        "Horário",
        "Escola",
        "Polo",
        "Equipe",
        "Tipo de visita",
        "Situação",
        "Relato",
        "Orientações / Providências",
    ]

    # ==========================================
    # AGRUPAR VISITAS POR CARTÃO PROGRAMA / VTR
    # ==========================================

    # Reutiliza as funções que já identificam
    # o efetivo e organizam os grupos do PDF.
    visitas_com_efetivo = _visitas_com_efetivo(
        visitas
    )

    grupos = _grupos_visitas(
        visitas_com_efetivo
    )

    # ==========================================
    # ESCREVER CADA GRUPO NO CSV
    # ==========================================

    for grupo in grupos:

        # Linha em branco entre grupos.
        escritor.writerow([])

        # Identificação do Cartão Programa e viatura.
        escritor.writerow([
            "Cartão Programa / Viatura",
            grupo["titulo"],
        ])

        # Identificação da equipe.
        escritor.writerow([
            "Equipe designada",
            grupo["equipe"],
        ])

        # Efetivo designado.
        efetivo = []

        for integrante in grupo["efetivo"]:

            funcao = integrante.funcao

            nome = (
                integrante.gcm.nome
                if integrante.gcm
                else "Não identificado"
            )

            efetivo.append(
                f"{funcao}: {nome}"
            )

        escritor.writerow([
            "Efetivo designado",
            " | ".join(efetivo)
            if efetivo
            else "Não identificado",
        ])

        # Linha em branco antes da tabela.
        escritor.writerow([])

        # Cabeçalho da tabela de visitas.
        escritor.writerow(cabecalho)

        # ======================================
        # REGISTROS DE VISITAS DO GRUPO
        # ======================================

        for visita in grupo["visitas"]:

            escritor.writerow([
                visita.data_visita.strftime("%d/%m/%Y"),
                (
                    visita.horario.strftime("%H:%M")
                    if visita.horario
                    else ""
                ),
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
    visitas, _ = _consultar_visitas(request)
    visitas = _visitas_com_efetivo(visitas)
    grupos = _grupos_visitas(visitas)
    total_visitas = sum(len(grupo["visitas"]) for grupo in grupos)

    buffer = BytesIO()
    pagina = landscape(A4)
    documento = SimpleDocTemplate(
        buffer, pagesize=pagina,
        rightMargin=8 * mm, leftMargin=8 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Relatório de Visitas - RECOM", author="RECOM",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloRECOM", parent=estilos["Heading1"],
        fontName="Helvetica-Bold", fontSize=15, leading=19,
        alignment=TA_CENTER, textColor=colors.HexColor("#092B49"),
        spaceAfter=3 * mm,
    )
    subtitulo = ParagraphStyle(
        "SubtituloRECOM", parent=estilos["Normal"],
        fontSize=10, leading=13, alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    celula = ParagraphStyle(
        "CelulaRECOM", parent=estilos["Normal"],
        fontName="Helvetica", fontSize=9, leading=12,
        alignment=TA_LEFT, wordWrap="CJK",
    )
    cabecalho = ParagraphStyle(
        "CabecalhoRECOM", parent=celula,
        fontName="Helvetica-Bold", textColor=colors.white,
    )
    grupo_estilo = ParagraphStyle(
        "GrupoRECOM", parent=estilos["Normal"],
        fontName="Helvetica-Bold", fontSize=10, leading=13,
        textColor=colors.HexColor("#092B49"),
    )
    efetivo_estilo = ParagraphStyle(
        "EfetivoRECOM", parent=estilos["Normal"],
        fontSize=9, leading=12,
    )

    def paragrafo(valor, estilo=celula):
        texto = escape(str(valor if valor is not None and valor != "" else "-"))
        return Paragraph(texto.replace("\r\n", "\n").replace("\n", "<br/>"), estilo)

    elementos = [
        Paragraph("RECOM - Ronda Escolar Comunitária", titulo),
        Paragraph("Relatório de Visitas", subtitulo),
        Paragraph(f"Total de visitas encontradas: {total_visitas}", subtitulo),
        Spacer(1, 2 * mm),
    ]
    largura_util = pagina[0] - 16 * mm
    proporcoes = [0.085, 0.055, 0.15, 0.05, 0.07, 0.09, 0.10, 0.20, 0.20]
    larguras = [largura_util * p for p in proporcoes]
    nomes = ["Data", "Hora", "Escola", "Polo", "Equipe", "Tipo",
             "Situação", "Relato", "Orientações / Providências"]

    if not grupos:
        elementos.append(Paragraph("Nenhuma visita encontrada.", subtitulo))

    for grupo in grupos:
        elementos.append(Paragraph(escape(grupo["titulo"]), grupo_estilo))
        elementos.append(Paragraph("Equipe: " + escape(grupo["equipe"]), efetivo_estilo))
        if grupo["efetivo"]:
            texto_efetivo = " | ".join(
                f"{escape(item.funcao)}: {escape(item.gcm.nome)}"
                for item in grupo["efetivo"]
            )
        else:
            texto_efetivo = "Efetivo não vinculado" if grupo["titulo"].startswith("Cartão") else "Efetivo não identificado (visita avulsa)"
        elementos.append(Paragraph("Efetivo: " + texto_efetivo, efetivo_estilo))
        elementos.append(Spacer(1, 2 * mm))

        dados = [[paragrafo(nome, cabecalho) for nome in nomes]]
        for visita in grupo["visitas"]:
            dados.append([
                paragrafo(visita.data_visita.strftime("%d/%m/%Y")),
                paragrafo(visita.horario.strftime("%H:%M") if visita.horario else ""),
                paragrafo(visita.escola.nome),
                paragrafo(visita.escola.get_polo_display()),
                paragrafo(visita.get_equipe_display()),
                paragrafo(visita.get_tipo_visita_display()),
                paragrafo(visita.get_situacao_display()),
                paragrafo(visita.relato),
                paragrafo(visita.orientacoes),
            ])
        tabela = LongTable(dados, colWidths=larguras, repeatRows=1, hAlign="CENTER")
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#092B49")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5DF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F3F6F9")]),
        ]))
        elementos.append(tabela)
        elementos.append(Spacer(1, 6 * mm))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(8 * mm, 7 * mm, "RECOM - Relatório de Visitas")
        canvas.drawRightString(pagina[0] - 8 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    resposta = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    buffer.close()
    resposta["Content-Disposition"] = 'attachment; filename="relatorio_visitas_recom.pdf"'
    return resposta
