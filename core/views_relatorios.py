
from datetime import date, time
from io import BytesIO
from collections import OrderedDict

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
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
from cartao_programa.models import EfetivoViatura
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
    Consulta compartilhada pela tela, PDF e XLSX.

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

    # GCM acessa diretamente o Relatório de Visitas.
    # A consulta continua abrangendo todas as equipes e visitas avulsas.
    if _perfil_usuario(request) == "GCM":
        return relatorio_visitas(request)

    # ADMIN e COORDENADOR permanecem na página gerencial.
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




def _xlsx_seguro(valor):
    """Evita interpretação de texto externo como fórmula no Excel/Sheets."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        valor = valor.replace("\x00", "")
        if valor.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + valor
        return valor
    return valor


def _estilizar_aba(aba, larguras=None):
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = aba.dimensions
    for celula in aba[1]:
        celula.fill = PatternFill("solid", fgColor="092B49")
        celula.font = Font(bold=True, color="FFFFFF")
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    aba.row_dimensions[1].height = 30
    for indice, largura in enumerate(larguras or [], 1):
        aba.column_dimensions[get_column_letter(indice)].width = largura
    for linha in aba.iter_rows(min_row=2):
        for celula in linha:
            celula.alignment = Alignment(vertical="top", wrap_text=True)


def _resposta_xlsx(workbook, nome):
    memoria = BytesIO()
    workbook.save(memoria)
    resposta = HttpResponse(
        memoria.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta

# =============================================================
# AGRUPAMENTO POR CARTÃO PROGRAMA (SEM REPETIR CABEÇALHOS)
# =============================================================

ORDEM_FUNCOES = {"C": 0, "M": 1, "P1": 2, "P2": 3}


def _cartao_da_visita(visita):
    """Usa o cartão da missão ou o vínculo direto da visita avulsa."""
    if visita.missao_cartao_id:
        return visita.missao_cartao.cartao
    return visita.cartao_programa


def _viatura_da_visita(visita):
    """Nunca deduz viatura a partir do cartão ou do plantão."""
    if visita.viatura_id:
        return visita.viatura
    if visita.missao_cartao_id:
        return visita.missao_cartao.viatura
    return None


def _nome_equipe_visita(visita):
    viatura = _viatura_da_visita(visita)
    if viatura and viatura.equipe_id:
        return viatura.equipe.nome
    return visita.get_equipe_display() if visita.equipe else "Não informada"


def _texto_efetivo(efetivo):
    return " | ".join(
        f"{item.funcao}: {item.gcm.nome}"
        for item in efetivo if item.gcm_id
    ) or "Não identificado"


def _escalas_do_plantao(plantao_id):
    """Retorna efetivos por viatura; não atribui uma escala a visitas avulsas."""
    escalas = (
        EfetivoViatura.objects
        .filter(viatura__plantao_id=plantao_id)
        .select_related("gcm", "viatura", "viatura__equipe")
        .order_by("viatura_id", "gcm__nome")
    )
    por_viatura = OrderedDict()
    for escala in escalas:
        vid = escala.viatura_id
        if vid not in por_viatura:
            v = escala.viatura
            por_viatura[vid] = {
                "viatura": v,
                "equipe": v.equipe.nome if v.equipe_id else "Não informada",
                "efetivo": [],
            }
        por_viatura[vid]["efetivo"].append(escala)
    for dados in por_viatura.values():
        dados["efetivo"].sort(
            key=lambda item: (ORDEM_FUNCOES.get(item.funcao, 9), item.gcm.nome if item.gcm_id else "")
        )
    return list(por_viatura.values())


def _grupos_visitas(visitas):
    """Um grupo por CP; visitas sem CP em grupo independente."""
    grupos = OrderedDict()
    for visita in visitas:
        cartao = _cartao_da_visita(visita)
        chave = ("cp", cartao.pk) if cartao else ("sem_cp", None)
        if chave not in grupos:
            if cartao:
                titulo = f"CP {cartao.pk} — {cartao.plantao.data:%d/%m/%Y}"
                escalas = _escalas_do_plantao(cartao.plantao_id)
            else:
                titulo = "Visitas sem Cartão Programa"
                escalas = []
            grupos[chave] = {
                "cartao": cartao,
                "titulo": titulo,
                "escalas": escalas,
                "visitas": [],
            }
        grupos[chave]["visitas"].append(visita)

    resultado = list(grupos.values())
    for grupo in resultado:
        grupo["visitas"].sort(
            key=lambda v: (v.data_visita, v.horario or time.min, v.pk)
        )
    return resultado


def _efetivo_escalado_cp(escalas):
    """Lista as guarnições escaladas no CP, sem atribuí-las à visita."""
    if not escalas:
        return "Não identificado"
    return " | ".join(
        f"{escala['equipe']} / {escala['viatura'].identificacao}: "
        f"{_texto_efetivo(escala['efetivo'])}"
        for escala in escalas
    )


def _visitas_com_efetivo(visitas):
    """Carrega relações necessárias para relatório, evitando consultas por linha."""
    return visitas.select_related(
        "escola", "cartao_programa__plantao", "viatura__equipe",
        "missao_cartao__cartao__plantao",
        "missao_cartao__viatura__equipe",
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
# EXPORTAÇÃO XLSX - VISITAS / ESCALAS / RESUMO
# =============================================================

@login_required
def exportar_visitas_xlsx(request):
    """Relatório visual por CP e base tabular independente para estatísticas."""
    visitas, _ = _consultar_visitas(request)
    grupos = _grupos_visitas(_visitas_com_efetivo(visitas))
    workbook = Workbook()
    aba = workbook.active
    aba.title = "Visitas por cartão"
    azul = "092B49"
    claro = "EAF0F5"
    titulos = [
        "Data", "Horário", "Escola", "Polo", "Tipo de registro",
        "Atividade realizada", "Situação", "Viatura da visita",
        "Relato", "Providências",
    ]
    larguras = [16, 12, 34, 16, 23, 30, 22, 23, 58, 58]
    for i, largura in enumerate(larguras, 1):
        aba.column_dimensions[get_column_letter(i)].width = largura
    aba.sheet_view.showGridLines = False
    aba.merge_cells("A1:J1")
    aba["A1"] = "RECOM — Ronda Escolar Comunitária | Relatório de Visitas"
    aba["A1"].font = Font(bold=True, color="FFFFFF", size=15)
    aba["A1"].fill = PatternFill("solid", fgColor=azul)
    aba["A1"].alignment = Alignment(vertical="center")
    aba.row_dimensions[1].height = 34
    aba.freeze_panes = "A2"

    base = workbook.create_sheet("Base estatística")
    base.append([
        "Data", "Horário", "Cartão Programa", "Data do plantão",
        "Equipe", "Viatura da visita", "Efetivo escalado no CP",
        "Escola", "Polo", "Tipo de registro", "Atividade realizada",
        "Situação", "Relato", "Providências",
    ])
    total = 0
    avulsas = 0

    for grupo in grupos:
        cartao = grupo["cartao"]
        escalas = grupo["escalas"]
        escalas_por_viatura = {e["viatura"].pk: e for e in escalas}
        efetivo_cp = _efetivo_escalado_cp(escalas) if cartao else "Sem CP"
        equipes = list(dict.fromkeys(e["equipe"] for e in escalas))
        equipe_cabecalho = ", ".join(equipes) if equipes else "Não identificada"
        viaturas = ", ".join(e["viatura"].identificacao for e in escalas) or "Não identificadas"
        titulo_grupo = grupo["titulo"]
        inicio = aba.max_row + 2
        aba.merge_cells(start_row=inicio, start_column=1, end_row=inicio, end_column=10)
        c = aba.cell(inicio, 1, titulo_grupo)
        c.font = Font(bold=True, color="FFFFFF", size=12)
        c.fill = PatternFill("solid", fgColor=azul)
        aba.row_dimensions[inicio].height = 25
        detalhes = (
            [("Equipe(s)", equipe_cabecalho), ("Viatura(s) escalada(s)", viaturas),
             ("Efetivo escalado no CP", efetivo_cp)]
            if cartao else [("Vínculo", "Visitas sem Cartão Programa; sem efetivo atribuído")]
        )
        detalhes.append(("Total de visitas", len(grupo["visitas"])))
        for indice, (rotulo, valor) in enumerate(detalhes, inicio + 1):
            aba.merge_cells(start_row=indice, start_column=2, end_row=indice, end_column=10)
            aba.cell(indice, 1, rotulo).font = Font(bold=True, color=azul)
            c = aba.cell(indice, 2, _xlsx_seguro(valor))
            c.alignment = Alignment(
                horizontal="left",
                vertical="center",
                wrap_text=True,
            )
            aba.row_dimensions[indice].height = 32 if rotulo == "Efetivo escalado no CP" else 22
        cab = inicio + 1 + len(detalhes)
        for coluna, nome in enumerate(titulos, 1):
            c = aba.cell(cab, coluna, nome)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=azul)
            c.alignment = Alignment(wrap_text=True, vertical="center")
        aba.row_dimensions[cab].height = 30
        for visita in grupo["visitas"]:
            viatura = _viatura_da_visita(visita)
            escala_visita = escalas_por_viatura.get(viatura.pk) if viatura else None
            if escala_visita:
                nome_equipe = escala_visita["equipe"]
            elif cartao and len(equipes) == 1:
                nome_equipe = equipes[0]
            else:
                nome_equipe = _nome_equipe_visita(visita)
            programada = bool(visita.missao_cartao_id)
            tipo = "Visita programada" if programada else "Visita avulsa"
            total += 1
            avulsas += int(not programada)
            dados = (
                visita.data_visita, visita.horario, visita.escola.nome,
                visita.escola.get_polo_display(), tipo,
                visita.get_tipo_visita_display(), visita.get_situacao_display(),
                viatura.identificacao if viatura else "Não identificada",
                visita.relato or "", visita.orientacoes or "",
            )
            linha = aba.max_row + 1
            for coluna, valor in enumerate(dados, 1):
                c = aba.cell(linha, coluna, _xlsx_seguro(valor))
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if (linha - cab) % 2 == 0:
                    c.fill = PatternFill("solid", fgColor="F3F6F9")
            aba.cell(linha, 1).number_format = "DD/MM/YYYY"
            aba.cell(linha, 2).number_format = "HH:MM"
            aba.row_dimensions[linha].height = 32
            base.append([_xlsx_seguro(v) for v in (
                visita.data_visita, visita.horario,
                f"CP {cartao.pk}" if cartao else "Não vinculado",
                cartao.plantao.data if cartao else None,
                nome_equipe, viatura.identificacao if viatura else "Não identificada",
                efetivo_cp, visita.escola.nome, visita.escola.get_polo_display(),
                tipo, visita.get_tipo_visita_display(), visita.get_situacao_display(),
                visita.relato or "", visita.orientacoes or "",
            )])
            base.cell(base.max_row, 1).number_format = "DD/MM/YYYY"
            base.cell(base.max_row, 2).number_format = "HH:MM"
            base.cell(base.max_row, 4).number_format = "DD/MM/YYYY"

    _estilizar_aba(base, [15, 12, 20, 19, 30, 24, 75, 34, 16, 22, 29, 22, 65, 65])
    escalas_aba = workbook.create_sheet("Escalas do plantão")
    escalas_aba.append(["Cartão Programa", "Data do plantão", "Viatura", "Equipe", "Efetivo escalado"])
    for grupo in grupos:
        cartao = grupo["cartao"]
        if not cartao:
            continue
        for escala in grupo["escalas"]:
            escalas_aba.append([
                f"CP {cartao.pk}", cartao.plantao.data,
                _xlsx_seguro(escala["viatura"].identificacao),
                _xlsx_seguro(escala["equipe"]),
                _xlsx_seguro(_texto_efetivo(escala["efetivo"])),
            ])
            escalas_aba.cell(escalas_aba.max_row, 2).number_format = "DD/MM/YYYY"
    _estilizar_aba(escalas_aba, [22, 20, 24, 34, 65])
    resumo = workbook.create_sheet("Resumo")
    resumo.append(["Indicador", "Quantidade"])
    resumo.append(["Visitas programadas", total - avulsas])
    resumo.append(["Visitas avulsas", avulsas])
    resumo.append(["Total de visitas", total])
    resumo.append(["Cartões Programa com visitas", sum(bool(g["cartao"]) for g in grupos)])
    _estilizar_aba(resumo, [38, 18])
    return _resposta_xlsx(workbook, "relatorio_visitas_recom.xlsx")


# Compatibilidade temporária com URLs antigas.
exportar_visitas_csv = exportar_visitas_xlsx


# =============================================================
# EXPORTAÇÃO PDF - CABEÇALHO ÚNICO POR CARTÃO
# =============================================================

@login_required
def exportar_visitas_pdf(request):
    visitas, _ = _consultar_visitas(request)
    grupos = _grupos_visitas(_visitas_com_efetivo(visitas))
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
        fontName="Helvetica", fontSize=8, leading=10,
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
    detalhe_estilo = ParagraphStyle(
        "DetalheRECOM", parent=estilos["Normal"],
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
    proporcoes = [0.085, 0.055, 0.16, 0.055, 0.11, 0.08, 0.105, 0.175, 0.175]
    larguras = [largura_util * p for p in proporcoes]
    nomes = [
        "Data", "Hora", "Escola", "Polo", "Atividade", "Viatura",
        "Situação", "Relato", "Orientações / Providências",
    ]

    if not grupos:
        elementos.append(Paragraph("Nenhuma visita encontrada.", subtitulo))

    for grupo in grupos:
        elementos.append(Paragraph(escape(grupo["titulo"]), grupo_estilo))
        elementos.append(Paragraph(
            f"Total de visitas deste grupo: {len(grupo['visitas'])}", detalhe_estilo
        ))
        if grupo["cartao"]:
            if grupo["escalas"]:
                for escala in grupo["escalas"]:
                    linha = (
                        f"{escala['equipe']} — {escala['viatura'].identificacao} — "
                        f"Efetivo: {_texto_efetivo(escala['efetivo'])}"
                    )
                    elementos.append(paragrafo(linha, detalhe_estilo))
            else:
                elementos.append(Paragraph("Efetivo escalado não identificado.", detalhe_estilo))
        else:
            elementos.append(Paragraph(
                "Sem vínculo com Cartão Programa; efetivo não atribuído.", detalhe_estilo
            ))
        elementos.append(Spacer(1, 2 * mm))

        dados = [[paragrafo(nome, cabecalho) for nome in nomes]]
        for visita in grupo["visitas"]:
            viatura = _viatura_da_visita(visita)
            dados.append([
                paragrafo(visita.data_visita.strftime("%d/%m/%Y")),
                paragrafo(visita.horario.strftime("%H:%M") if visita.horario else ""),
                paragrafo(visita.escola.nome),
                paragrafo(visita.escola.get_polo_display()),
                paragrafo(visita.get_tipo_visita_display()),
                paragrafo(viatura.identificacao if viatura else "Não identificada"),
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
