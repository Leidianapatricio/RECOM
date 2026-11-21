import re

from datetime import date, datetime
from io import BytesIO
from collections import OrderedDict

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    KeepTogether,
    LongTable,
    TableStyle,
)

from cartao_programa.models import (
    EfetivoViatura,
    Equipe,
    MissaoCartao,
    ViaturaPlantao,
)

from ocorrencias.models import Ocorrencia
from ocorrencias.permissoes import (
    filtrar_ocorrencias,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
)
from usuarios.models import Usuario
from visitas.models import RondaVisita

from visitas.permissoes import (
    filtro_visitas_avulsas_gcm,
    pode_editar_visita,
    pode_excluir_visita,
)


# =========================================================
# PERMISSÕES
# =========================================================

def obter_acesso_historico(request):

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):

        raise PermissionDenied(
            "Usuário não autenticado ou inativo."
        )

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()

    if request.user.is_superuser:

        return usuario, True

    if usuario is None:

        raise PermissionDenied(
            "Usuário RECOM não encontrado ou inativo."
        )

    if usuario.perfil in (
        "ADMIN",
        "COORDENADOR",
    ):

        return usuario, True

    if usuario.perfil == "GCM":

        return usuario, False

    raise PermissionDenied(
        "Você não possui permissão para acessar o histórico."
    )


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def converter_data(valor):

    if not valor:

        return None

    try:

        return date.fromisoformat(valor)

    except ValueError:

        return None


def formatar_data(valor):

    return (
        valor.strftime("%d/%m/%Y")
        if valor
        else "-"
    )


def formatar_hora(valor):

    return (
        valor.strftime("%H:%M")
        if valor
        else "-"
    )


def nome_responsavel(usuario):

    if usuario is None:

        return "Não informado"

    nome = getattr(
        usuario,
        "nome",
        None,
    )

    if nome:

        return nome

    return str(usuario)


# =========================================================
# IDENTIFICAR EQUIPE DA VIATURA
# =========================================================

def obter_equipe(viatura):

    if viatura is None:

        return "Não identificada"

    if viatura.equipe_id:

        return viatura.equipe.nome

    return "Extraordinária"


# =========================================================
# IDENTIFICAR EFETIVO DA VIATURA
# VISITAS PROGRAMADAS E MISSÕES
# =========================================================

def obter_efetivo(viatura):

    if viatura is None:

        return []

    return [
        {
            "nome": escala.gcm.nome,

            "funcao": escala.get_funcao_display(),
        }

        for escala in viatura.efetivo.all()
    ]


# =========================================================
# IDENTIFICAR CÓDIGO DA EQUIPE
# =========================================================

def codigo_equipe(nome):

    valor = str(
        nome or ""
    ).strip().upper()

    correspondencia = re.fullmatch(
        r"(?:EQUIPE\s+)?([A-F])"
        r"|EQUIPE\s+.+\s+-\s+([A-F])",
        valor,
    )

    if correspondencia:

        return (
            correspondencia.group(1)
            or correspondencia.group(2)
        )

    nomes_equipes = {
        "ALFA": "A",
        "ALPHA": "A",
        "BRAVO": "B",
        "CHARLIE": "C",
        "DELTA": "D",
        "ECHO": "E",
        "FOXTROT": "F",
        "EXTRA": "EXTRA",
        "EXTRAORDINARIA": "EXTRA",
        "EXTRAORDINÁRIA": "EXTRA",
        "EXTRAORDINARIO": "EXTRA",
        "EXTRAORDINÁRIO": "EXTRA",
    }

    valor = valor.removeprefix(
        "EQUIPE "
    ).strip()

    return nomes_equipes.get(valor)


# =========================================================
# IDENTIFICAR EFETIVO DO CARTÃO PROGRAMA
# INDEPENDENTEMENTE DA VIATURA
# =========================================================

def obter_efetivo_cartao(
    cartao_programa,
    cache,
):

    if cartao_programa is None:

        return []

    chave = cartao_programa.pk

    if chave not in cache:

        escalas = (
            EfetivoViatura.objects.filter(
                viatura__plantao_id=(
                    cartao_programa.plantao_id
                )
            )

            .select_related(
                "gcm",
                "viatura",
            )

            .order_by(
                "gcm__nome",
                "pk",
            )
        )

        vistos = set()

        pessoas = []

        for escala in escalas:

            if escala.gcm_id in vistos:

                continue

            vistos.add(
                escala.gcm_id
            )

            pessoas.append({
                "nome": escala.gcm.nome,

                "funcao": (
                    escala.get_funcao_display()
                ),
            })

        cache[chave] = pessoas

    return cache[chave]


# =========================================================
# EFETIVO DAS VISITAS AVULSAS
# =========================================================

def efetivo_avulsa(visita, cache):

    # -----------------------------------------------------
    # VISITA VINCULADA AO CARTÃO PROGRAMA
    # -----------------------------------------------------

    if visita.cartao_programa_id:

        return obter_efetivo_cartao(
            visita.cartao_programa,
            cache,
        )

    # -----------------------------------------------------
    # VISITA LEGADA COM VIATURA ORIGINAL
    # -----------------------------------------------------

    if visita.viatura_id:

        return obter_efetivo(
            visita.viatura
        )

    # -----------------------------------------------------
    # SEM VÍNCULO COM CARTÃO PROGRAMA
    # -----------------------------------------------------

    # Não utiliza equipe + data para presumir
    # o efetivo responsável pela visita.

    return []


# =========================================================
# FORMATAR EFETIVO PARA EXPORTAÇÕES
# =========================================================

def texto_efetivo(efetivo):

    if not efetivo:

        return "Não informado"

    return "; ".join(
        f"{item['nome']} ({item['funcao']})"

        for item in efetivo
    )


# =========================================================
# FORMATAR CARTÃO PROGRAMA
# =========================================================

def texto_cartao_programa(cartao):

    if cartao is None:

        return "Não vinculado"

    return (
        f"CP {cartao.pk} - "
        f"{formatar_data(cartao.plantao.data)}"
    )


# =========================================================
# CONSULTAR E FILTRAR ATIVIDADES
# =========================================================

def consultar_atividades(request):

    usuario, gestor = obter_acesso_historico(
        request
    )

    # -----------------------------------------------------
    # RECEBER FILTROS
    # -----------------------------------------------------

    data_inicio = request.GET.get(
        "data_inicio",
        "",
    ).strip()

    data_fim = request.GET.get(
        "data_fim",
        "",
    ).strip()

    equipe_id = request.GET.get(
        "equipe",
        "",
    ).strip()

    viatura_id = request.GET.get(
        "viatura",
        "",
    ).strip()

    tipo = request.GET.get(
        "tipo",
        "",
    ).strip()

    inicio = converter_data(
        data_inicio
    )

    fim = converter_data(
        data_fim
    )

    # -----------------------------------------------------
    # VALIDAR FILTROS
    # -----------------------------------------------------

    if data_inicio and inicio is None:

        raise PermissionDenied(
            "Data inicial inválida."
        )

    if data_fim and fim is None:

        raise PermissionDenied(
            "Data final inválida."
        )

    if inicio and fim and inicio > fim:

        raise PermissionDenied(
            "A data inicial não pode ser posterior à final."
        )

    if equipe_id and not equipe_id.isdigit():

        raise PermissionDenied(
            "Equipe inválida."
        )

    if viatura_id and not viatura_id.isdigit():

        raise PermissionDenied(
            "Viatura inválida."
        )

    # -----------------------------------------------------
    # ESCALAS DO GCM
    # -----------------------------------------------------

    if gestor:

        escalas = EfetivoViatura.objects.all()

    else:

        escalas = EfetivoViatura.objects.filter(
            gcm=usuario
        )

    ids_plantoes = escalas.values(
        "viatura__plantao_id"
    )

    # -----------------------------------------------------
    # VIATURAS PERMITIDAS
    # -----------------------------------------------------

    viaturas = ViaturaPlantao.objects.select_related(
        "plantao",
        "equipe",
    )

    if not gestor:

        viaturas = viaturas.filter(
            pk__in=escalas.values(
                "viatura_id"
            )
        )

    ids_viaturas_autorizadas = viaturas.values(
        "pk"
    )

    # -----------------------------------------------------
    # FILTRO DE EQUIPE
    # -----------------------------------------------------

    equipe_selecionada = None

    codigo_selecionado = None

    if equipe_id:

        equipe_selecionada = Equipe.objects.filter(
            pk=int(equipe_id)
        ).first()

        if equipe_selecionada is None:

            raise PermissionDenied(
                "Equipe não encontrada."
            )

        codigo_selecionado = codigo_equipe(
            equipe_selecionada.nome
        )

        viaturas = viaturas.filter(
            equipe_id=int(equipe_id)
        )

    # -----------------------------------------------------
    # FILTRO DE VIATURA
    # -----------------------------------------------------

    if viatura_id:

        viaturas = viaturas.filter(
            pk=int(viatura_id)
        )

    # -----------------------------------------------------
    # FILTRO DE PERÍODO
    # -----------------------------------------------------

    if inicio:

        viaturas = viaturas.filter(
            plantao__data__gte=inicio
        )

    if fim:

        viaturas = viaturas.filter(
            plantao__data__lte=fim
        )

    viaturas = viaturas.distinct()

    ids_viaturas = viaturas.values_list(
        "pk",
        flat=True,
    )

    # =====================================================
    # VISITAS
    # =====================================================

    visitas = RondaVisita.objects.select_related(
        "escola",
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "missao_cartao",
        "missao_cartao__cartao__plantao",
        "missao_cartao__viatura__plantao",
        "missao_cartao__viatura__equipe",
        "cartao_programa",
        "cartao_programa__plantao",
        "registrado_por",
    ).prefetch_related(
        "viatura__efetivo__gcm",
        "missao_cartao__viatura__efetivo__gcm",
    )

    # -----------------------------------------------------
    # PERMISSÕES DO GCM
    # -----------------------------------------------------

    if not gestor:

        # VISITAS PROGRAMADAS:
        # Permanecem vinculadas à viatura da missão.

        filtro_programadas = Q(
            missao_cartao__isnull=False,

            missao_cartao__viatura_id__in=(
                ids_viaturas_autorizadas
            ),
        )

        # VISITAS AVULSAS:
        #
        # 1. Todas as criadas até 15/11/2026;
        # 2. Todas as registradas pelo próprio GCM;
        # 3. Todas as vinculadas ao mesmo Cartão Programa.

        filtro_avulsas = filtro_visitas_avulsas_gcm(
            usuario
        )

        visitas = visitas.filter(

            filtro_programadas

            | filtro_avulsas

        )

    # -----------------------------------------------------
    # APLICAR FILTRO DE VIATURA
    # -----------------------------------------------------

    if viatura_id:

        # Visitas avulsas não são atribuídas
        # a uma viatura específica.

        visitas = visitas.filter(
            missao_cartao__isnull=False,

            missao_cartao__viatura_id__in=(
                ids_viaturas
            ),
        )

    # -----------------------------------------------------
    # APLICAR FILTRO DE EQUIPE
    # -----------------------------------------------------

    elif equipe_id:

        filtro_equipe = Q(
            missao_cartao__isnull=False,

            missao_cartao__viatura__equipe_id=(
                equipe_selecionada.pk
            ),
        )

        if codigo_selecionado:

            filtro_equipe |= Q(
                missao_cartao__isnull=True,

                equipe__iexact=codigo_selecionado,
            )

            filtro_equipe |= Q(
                missao_cartao__isnull=True,

                equipe__iexact=(
                    f"Equipe {codigo_selecionado}"
                ),
            )

        visitas = visitas.filter(
            filtro_equipe
        )

    # -----------------------------------------------------
    # FILTRAR PERÍODO DAS VISITAS
    # -----------------------------------------------------

    if inicio:

        visitas = visitas.filter(
            data_visita__gte=inicio
        )

    if fim:

        visitas = visitas.filter(
            data_visita__lte=fim
        )

    visitas = visitas.distinct()

    # =====================================================
    # OCORRÊNCIAS
    # =====================================================

    ocorrencias = Ocorrencia.objects.select_related(
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "cartao_programa",
        "cartao_programa__plantao",
        "registrado_por",
    ).prefetch_related(
        "viatura__efetivo__gcm",
    )

    # -----------------------------------------------------
    # PERMISSÕES DAS OCORRÊNCIAS
    # -----------------------------------------------------

    ocorrencias = filtrar_ocorrencias(
        request, ocorrencias, usuario
    )

    # -----------------------------------------------------
    # FILTRO DE VIATURA DAS OCORRÊNCIAS
    # -----------------------------------------------------

    if viatura_id:

        ocorrencias = ocorrencias.filter(
            cartao_programa__isnull=True,

            viatura_id__in=ids_viaturas,
        )

    # -----------------------------------------------------
    # FILTRO DE EQUIPE DAS OCORRÊNCIAS
    # -----------------------------------------------------

    elif equipe_id:

        plantoes_equipe = (
            ViaturaPlantao.objects.filter(
                equipe_id=int(equipe_id)
            ).values(
                "plantao_id"
            )
        )

        ocorrencias = ocorrencias.filter(

            Q(
                cartao_programa__isnull=True,

                viatura__equipe_id=int(equipe_id),
            )

            | Q(
                cartao_programa__plantao_id__in=(
                    plantoes_equipe
                )
            )

        )

    # -----------------------------------------------------
    # FILTRAR PERÍODO DAS OCORRÊNCIAS
    # -----------------------------------------------------

    if inicio:

        ocorrencias = ocorrencias.filter(
            data__gte=inicio
        )

    if fim:

        ocorrencias = ocorrencias.filter(
            data__lte=fim
        )

    ocorrencias = ocorrencias.distinct()

    # =====================================================
    # MISSÕES NÃO REALIZADAS
    # =====================================================

    missoes = MissaoCartao.objects.filter(
        status_execucao="NAO_REALIZADA",

        viatura_id__in=ids_viaturas,

    ).select_related(
        "escola",
        "cartao__plantao",
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "registrado_por",

    ).prefetch_related(
        "viatura__efetivo__gcm",
    )

    # =====================================================
    # MONTAR LISTA DE ATIVIDADES
    # =====================================================

    atividades = []

    cache_efetivo_cartao = {}

    # =====================================================
    # MONTAR VISITAS
    # =====================================================

    if tipo in (
        "",
        "VISITA_PROGRAMADA",
        "VISITA_AVULSA",
    ):

        for visita in visitas:

            programada = bool(
                visita.missao_cartao_id
            )

            tipo_visita = (
                "VISITA_PROGRAMADA"

                if programada

                else "VISITA_AVULSA"
            )

            if tipo and tipo != tipo_visita:

                continue

            # ---------------------------------------------
            # VISITA PROGRAMADA
            # ---------------------------------------------

            if programada:

                viatura = (
                    visita.missao_cartao.viatura
                )

                cartao = (
                    visita.missao_cartao.cartao
                )

                equipe = obter_equipe(
                    viatura
                )

                efetivo = obter_efetivo(
                    viatura
                )

            # ---------------------------------------------
            # VISITA AVULSA
            # ---------------------------------------------

            else:

                viatura = None

                cartao = visita.cartao_programa

                equipe = visita.get_equipe_display()

                efetivo = efetivo_avulsa(
                    visita,
                    cache_efetivo_cartao,
                )

            # ---------------------------------------------
            # ADICIONAR REGISTRO
            # ---------------------------------------------

            atividades.append({

                "id": visita.pk,

                "tipo": tipo_visita,

                "tipo_label": (
                    "Visita programada"

                    if programada

                    else "Visita avulsa"
                ),

                "data": visita.data_visita,

                "horario": visita.horario,

                "local": visita.escola.nome,

                "escola_id": visita.escola_id,

                "descricao": (
                    visita.get_tipo_visita_display()
                ),

                "situacao": (
                    visita.get_situacao_display()
                ),

                "relato": visita.relato or "",

                "providencias": (
                    visita.orientacoes or ""
                ),

                "viatura": (
                    viatura.identificacao

                    if viatura

                    else "Não vinculada"
                ),

                "viatura_id": (
                    viatura.pk

                    if viatura

                    else None
                ),

                "equipe": equipe,

                "cartao_programa": (
                    texto_cartao_programa(cartao)
                ),

                "cartao_programa_id": (
                    cartao.pk

                    if cartao

                    else None
                ),

                "responsavel": nome_responsavel(
                    visita.registrado_por
                ),

                "efetivo": efetivo,

                "pode_editar": pode_editar_visita(
                    request,
                    visita,
                    usuario,
                ),

                "pode_excluir": pode_excluir_visita(
                    request,
                    visita,
                    usuario,
                ),

            })

    # =====================================================
    # MONTAR OCORRÊNCIAS
    # =====================================================

    if tipo in (
        "",
        "OCORRENCIA",
    ):

        for ocorrencia in ocorrencias:

            cartao = ocorrencia.cartao_programa

            if cartao:

                viatura = None

                efetivo = obter_efetivo_cartao(
                    cartao,
                    cache_efetivo_cartao,
                )

                equipe = "Efetivo do Cartão Programa"

            else:

                viatura = ocorrencia.viatura

                efetivo = obter_efetivo(
                    viatura
                )

                equipe = obter_equipe(
                    viatura
                )

            atividades.append({

                "id": ocorrencia.pk,

                "tipo": "OCORRENCIA",

                "tipo_label": "Ocorrência",

                "data": ocorrencia.data,

                "horario": ocorrencia.horario,

                "local": ocorrencia.local,

                "descricao": (
                    ocorrencia.get_tipo_ocorrencia_display()
                ),

                "situacao": (
                    ocorrencia.get_natureza_atuacao_display()
                ),

                "relato": ocorrencia.relato or "",

                "providencias": (
                    ocorrencia.providencias or ""
                ),

                "viatura": (
                    viatura.identificacao

                    if viatura

                    else "Não vinculada"
                ),

                "viatura_id": (
                    viatura.pk

                    if viatura

                    else None
                ),

                "equipe": equipe,

                "cartao_programa": (
                    texto_cartao_programa(cartao)
                ),

                "cartao_programa_id": (
                    cartao.pk

                    if cartao

                    else None
                ),

                "responsavel": nome_responsavel(
                    ocorrencia.registrado_por
                ),

                "efetivo": efetivo,

                "pode_editar": pode_editar_ocorrencia(
                    request, ocorrencia, usuario,
                ),
                "pode_excluir": pode_excluir_ocorrencia(
                    request, ocorrencia, usuario,
                ),

            })

    # =====================================================
    # MONTAR MISSÕES NÃO REALIZADAS
    # =====================================================

    if tipo in (
        "",
        "MISSAO_NAO_REALIZADA",
    ):

        for missao in missoes:

            viatura = missao.viatura

            cartao = missao.cartao

            atividades.append({

                "id": missao.pk,

                "tipo": "MISSAO_NAO_REALIZADA",

                "tipo_label": "Missão não realizada",

                "data": viatura.plantao.data,

                "horario": missao.horario_inicio,

                "local": (
                    missao.escola.nome

                    if missao.escola_id

                    else missao.local
                ),

                "descricao": (
                    missao.get_tipo_missao_display()
                ),

                "situacao": "Não realizada",

                "relato": (
                    missao.motivo_nao_realizacao
                    or ""
                ),

                "providencias": "",

                "viatura": (
                    viatura.identificacao
                ),

                "viatura_id": missao.viatura_id,

                "equipe": obter_equipe(
                    viatura
                ),

                "cartao_programa": (
                    texto_cartao_programa(cartao)
                ),

                "cartao_programa_id": cartao.pk,

                "responsavel": nome_responsavel(
                    missao.registrado_por
                ),

                "efetivo": obter_efetivo(
                    viatura
                ),

            })

    # =====================================================
    # ORDENAÇÃO
    # =====================================================

    atividades.sort(

        key=lambda item: (
            item["data"],

            item["horario"]
            or datetime.min.time(),

            item["id"],
        ),

        reverse=True,

    )

    # =====================================================
    # OPÇÕES DOS FILTROS
    # =====================================================

    # Todas as equipes ficam disponíveis porque
    # todos os GCMs podem consultar visitas avulsas legadas,
    # independentemente da equipe.

    equipes_disponiveis = (
        Equipe.objects.all()
        .order_by("nome")
    )

    if gestor:

        viaturas_disponiveis = (
            ViaturaPlantao.objects

            .select_related(
                "plantao",
                "equipe",
            )

            .order_by(
                "-plantao__data",
                "identificacao",
            )
        )

    else:

        viaturas_disponiveis = (
            ViaturaPlantao.objects

            .filter(
                pk__in=ids_viaturas_autorizadas
            )

            .select_related(
                "plantao",
                "equipe",
            )

            .distinct()

            .order_by(
                "-plantao__data",
                "identificacao",
            )
        )

    # =====================================================
    # FILTROS SELECIONADOS
    # =====================================================

    filtros = {

        "data_inicio": data_inicio,

        "data_fim": data_fim,

        "equipe": equipe_id,

        "viatura": viatura_id,

        "tipo": tipo,

    }

    return {

        "atividades": atividades,

        "filtros": filtros,

        "equipes": equipes_disponiveis,

        "viaturas": viaturas_disponiveis,

        "gestor": gestor,

        "usuario_recom": usuario,

    }


# =========================================================
# PÁGINA DO HISTÓRICO DE ATIVIDADES
# =========================================================

@login_required
def historico_atividades(request):

    dados = consultar_atividades(
        request
    )

    atividades = dados["atividades"]

    # -----------------------------------------------------
    # PAGINAÇÃO
    # -----------------------------------------------------

    paginator = Paginator(
        atividades,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    dados["page_obj"] = page_obj

    # -----------------------------------------------------
    # INDICADORES
    # -----------------------------------------------------

    dados["total_atividades"] = len(
        atividades
    )

    dados["total_visitas"] = sum(

        1

        for item in atividades

        if item["tipo"] in (
            "VISITA_PROGRAMADA",
            "VISITA_AVULSA",
        )

    )

    dados["total_ocorrencias"] = sum(

        1

        for item in atividades

        if item["tipo"] == "OCORRENCIA"

    )

    dados["total_nao_realizadas"] = sum(

        1

        for item in atividades

        if item["tipo"] == "MISSAO_NAO_REALIZADA"

    )

    # -----------------------------------------------------
    # RENDERIZAR
    # -----------------------------------------------------

    return render(
        request,

        "core/historico_atividades.html",

        dados,
    )




# =========================================================
# EXPORTAÇÕES PADRONIZADAS - HISTÓRICO RECOM
# =========================================================

ORDEM_FUNCOES = {"C": 0, "M": 1, "P1": 2, "P2": 3}
AZUL_RECOM = "092B49"


def _xlsx_seguro(valor):
    if valor is None:
        return ""
    if isinstance(valor, str):
        valor = valor.replace("\x00", "")
        if valor.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + valor
    return valor


def _estilizar_aba(aba, larguras):
    aba.sheet_view.showGridLines = False
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = aba.dimensions
    for celula in aba[1]:
        celula.fill = PatternFill("solid", fgColor=AZUL_RECOM)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.alignment = Alignment(vertical="center", wrap_text=True)
    aba.row_dimensions[1].height = 32
    for indice, largura in enumerate(larguras, 1):
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


def _grupos_historico(atividades):
    """Um grupo por CP, independentemente da viatura da atividade."""
    grupos = OrderedDict()
    for item in atividades:
        cp_id = item.get("cartao_programa_id")
        chave = ("cp", cp_id) if cp_id is not None else ("sem_cp", None)
        if chave not in grupos:
            grupos[chave] = {
                "cartao_id": cp_id,
                "titulo": item["cartao_programa"] if cp_id else "Atividades sem Cartão Programa",
                "atividades": [],
            }
        grupos[chave]["atividades"].append(item)
    for grupo in grupos.values():
        grupo["atividades"].sort(
            key=lambda item: (
                item["data"] or date.min,
                item["horario"] or datetime.min.time(),
                item["id"],
            )
        )
    return list(grupos.values())


def _escalas_historico(grupo, cache):
    """Escala do plantão do CP: referência, não atribuição à atividade."""
    cp_id = grupo["cartao_id"]
    if cp_id is None:
        return []
    if cp_id not in cache:
        from cartao_programa.models import CartaoPrograma
        cartao = CartaoPrograma.objects.select_related("plantao").get(pk=cp_id)
        escalas = (
            EfetivoViatura.objects
            .filter(viatura__plantao_id=cartao.plantao_id)
            .select_related("gcm", "viatura", "viatura__equipe")
            .order_by("viatura_id", "pk")
        )
        por_viatura = OrderedDict()
        for escala in escalas:
            if escala.viatura_id not in por_viatura:
                v = escala.viatura
                por_viatura[escala.viatura_id] = {
                    "viatura": v.identificacao,
                    "equipe": v.equipe.nome if v.equipe_id else "Não informada",
                    "pessoas": [],
                }
            por_viatura[escala.viatura_id]["pessoas"].append(escala)
        resultado = list(por_viatura.values())
        for dados in resultado:
            dados["pessoas"].sort(
                key=lambda escala: (
                    ORDEM_FUNCOES.get(escala.funcao, 9),
                    escala.gcm.nome if escala.gcm_id else "",
                )
            )
        cache[cp_id] = resultado
    return cache[cp_id]


def _texto_escala(escala):
    pessoas = " | ".join(
        f"{pessoa.funcao}: {pessoa.gcm.nome}"
        for pessoa in escala["pessoas"] if pessoa.gcm_id
    ) or "Não identificado"
    return f'{escala["equipe"]} / {escala["viatura"]}: {pessoas}'


def _detalhes_grupo(grupo, cache):
    escalas = _escalas_historico(grupo, cache)
    if grupo["cartao_id"] is None:
        return {
            "escalas": [],
            "equipes": "Não vinculadas a um CP",
            "viaturas": "Não vinculadas a um CP",
            "efetivo": "Sem escala de CP atribuída",
        }
    return {
        "escalas": escalas,
        "equipes": ", ".join(dict.fromkeys(e["equipe"] for e in escalas)) or "Não identificadas",
        "viaturas": ", ".join(e["viatura"] for e in escalas) or "Não identificadas",
        "efetivo": " | ".join(_texto_escala(e) for e in escalas) or "Não identificado",
    }


@login_required
def exportar_historico_xlsx(request):
    atividades = consultar_atividades(request)["atividades"]
    grupos = _grupos_historico(atividades)
    cache = {}
    wb = Workbook()
    visual = wb.active
    visual.title = "Atividades por cartão"
    visual.sheet_view.showGridLines = False
    titulos = [
        "Data", "Horário", "Tipo de registro", "Atividade realizada",
        "Local", "Situação", "Viatura da atividade",
        "Registrado por", "Relato", "Providências",
    ]
    larguras = [16, 12, 23, 31, 37, 23, 24, 27, 60, 60]
    for indice, largura in enumerate(larguras, 1):
        visual.column_dimensions[get_column_letter(indice)].width = largura
    visual.merge_cells("A1:J1")
    c = visual["A1"]
    c.value = "RECOM — Ronda Escolar Comunitária | Histórico de Atividades"
    c.fill = PatternFill("solid", fgColor=AZUL_RECOM)
    c.font = Font(bold=True, color="FFFFFF", size=15)
    c.alignment = Alignment(vertical="center", horizontal="left")
    visual.row_dimensions[1].height = 36
    visual.freeze_panes = "A2"

    base = wb.create_sheet("Base estatística")
    base.append([
        "Data", "Horário", "Cartão Programa", "Equipe da atividade",
        "Viatura da atividade", "Efetivo escalado no CP (referência)",
        "Tipo de registro", "Atividade realizada", "Local", "Situação",
        "Registrado por", "Relato", "Providências",
    ])
    escalas_aba = wb.create_sheet("Escalas do plantão")
    escalas_aba.append(["Cartão Programa", "Equipe", "Viatura", "Efetivo escalado"])

    for grupo in grupos:
        detalhes = _detalhes_grupo(grupo, cache)
        inicio = visual.max_row + 2
        visual.merge_cells(start_row=inicio, start_column=1, end_row=inicio, end_column=10)
        titulo = visual.cell(inicio, 1, _xlsx_seguro(grupo["titulo"]))
        titulo.fill = PatternFill("solid", fgColor=AZUL_RECOM)
        titulo.font = Font(bold=True, color="FFFFFF", size=12)
        titulo.alignment = Alignment(vertical="center")
        visual.row_dimensions[inicio].height = 26
        campos = [
            ("Equipe(s)", detalhes["equipes"]),
            ("Viatura(s) escalada(s)", detalhes["viaturas"]),
            ("Efetivo escalado no CP", detalhes["efetivo"]),
            ("Total de atividades", len(grupo["atividades"])),
        ]
        for indice, (rotulo, valor) in enumerate(campos, inicio + 1):
            visual.merge_cells(start_row=indice, start_column=2, end_row=indice, end_column=10)
            visual.cell(indice, 1, rotulo).font = Font(bold=True, color=AZUL_RECOM)
            celula = visual.cell(indice, 2, _xlsx_seguro(valor))
            celula.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            visual.row_dimensions[indice].height = 34 if rotulo == "Efetivo escalado no CP" else 23
        linha_cabecalho = inicio + 1 + len(campos)
        for coluna, nome in enumerate(titulos, 1):
            c = visual.cell(linha_cabecalho, coluna, nome)
            c.fill = PatternFill("solid", fgColor=AZUL_RECOM)
            c.font = Font(bold=True, color="FFFFFF")
            c.alignment = Alignment(vertical="center", wrap_text=True)
        visual.row_dimensions[linha_cabecalho].height = 32

        for posicao, item in enumerate(grupo["atividades"], 1):
            linha = visual.max_row + 1
            valores = [
                item["data"], item["horario"], item["tipo_label"],
                item["descricao"], item["local"], item["situacao"],
                item["viatura"], item["responsavel"],
                item["relato"], item["providencias"],
            ]
            for coluna, valor in enumerate(valores, 1):
                c = visual.cell(linha, coluna, _xlsx_seguro(valor))
                c.alignment = Alignment(vertical="top", wrap_text=True)
                if posicao % 2 == 0:
                    c.fill = PatternFill("solid", fgColor="F3F6F9")
            visual.cell(linha, 1).number_format = "DD/MM/YYYY"
            visual.cell(linha, 2).number_format = "HH:MM"
            visual.row_dimensions[linha].height = 35
            base.append([_xlsx_seguro(v) for v in [
                item["data"], item["horario"],
                f'CP {grupo["cartao_id"]}' if grupo["cartao_id"] else "Não vinculado",
                item["equipe"], item["viatura"], detalhes["efetivo"],
                item["tipo_label"], item["descricao"], item["local"],
                item["situacao"], item["responsavel"], item["relato"], item["providencias"],
            ]])
            base.cell(base.max_row, 1).number_format = "DD/MM/YYYY"
            base.cell(base.max_row, 2).number_format = "HH:MM"

        for escala in detalhes["escalas"]:
            escalas_aba.append([
                f'CP {grupo["cartao_id"]}',
                _xlsx_seguro(escala["equipe"]),
                _xlsx_seguro(escala["viatura"]),
                _xlsx_seguro(_texto_escala(escala)),
            ])

    _estilizar_aba(base, [16, 12, 22, 28, 25, 78, 24, 32, 38, 24, 28, 65, 65])
    _estilizar_aba(escalas_aba, [22, 32, 24, 78])
    resumo = wb.create_sheet("Resumo")
    resumo.append(["Indicador", "Quantidade"])
    for chave, rotulo in [
        ("VISITA_PROGRAMADA", "Visitas programadas"),
        ("VISITA_AVULSA", "Visitas avulsas"),
        ("OCORRENCIA", "Ocorrências"),
        ("MISSAO_NAO_REALIZADA", "Missões não realizadas"),
    ]:
        resumo.append([rotulo, sum(item["tipo"] == chave for item in atividades)])
    resumo.append(["Total de atividades", len(atividades)])
    resumo.append(["Cartões Programa com atividades", sum(g["cartao_id"] is not None for g in grupos)])
    _estilizar_aba(resumo, [43, 19])
    return _resposta_xlsx(wb, "historico_atividades_recom.xlsx")


@login_required
def exportar_historico_pdf(request):
    atividades = consultar_atividades(request)["atividades"]
    grupos = _grupos_historico(atividades)
    cache = {}
    buffer = BytesIO()
    pagina = landscape(A4)
    documento = SimpleDocTemplate(
        buffer, pagesize=pagina,
        leftMargin=8 * mm, rightMargin=8 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Histórico de Atividades - RECOM", author="RECOM",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloHistoricoRECOM", parent=estilos["Heading1"],
        fontName="Helvetica-Bold", fontSize=15, leading=19,
        alignment=TA_CENTER, textColor=colors.HexColor("#092B49"),
        spaceAfter=3 * mm,
    )
    subtitulo = ParagraphStyle(
        "SubtituloHistoricoRECOM", parent=estilos["Normal"],
        fontSize=10, leading=13, alignment=TA_CENTER, spaceAfter=3 * mm,
    )
    celula = ParagraphStyle(
        "CelulaHistoricoRECOM", parent=estilos["Normal"],
        fontName="Helvetica", fontSize=7.5, leading=10,
        alignment=TA_LEFT, wordWrap="CJK",
    )
    cabecalho = ParagraphStyle(
        "CabecalhoHistoricoRECOM", parent=celula,
        fontName="Helvetica-Bold", textColor=colors.white,
    )
    grupo_estilo = ParagraphStyle(
        "GrupoHistoricoRECOM", parent=estilos["Normal"],
        fontName="Helvetica-Bold", fontSize=10, leading=13,
        textColor=colors.HexColor("#092B49"),
    )
    detalhe_estilo = ParagraphStyle(
        "DetalheHistoricoRECOM", parent=estilos["Normal"],
        fontSize=9, leading=12,
    )

    def p(valor, estilo=celula):
        valor = "-" if valor is None or valor == "" else str(valor)
        return Paragraph(
            escape(valor).replace("\r\n", "\n").replace("\n", "<br/>"),
            estilo,
        )

    elementos = [
        Paragraph("RECOM - Ronda Escolar Comunitária", titulo),
        Paragraph("Histórico de Atividades", subtitulo),
        Paragraph(f"Total de atividades encontradas: {len(atividades)}", subtitulo),
        Spacer(1, 2 * mm),
    ]
    largura_util = pagina[0] - 16 * mm
    proporcoes = [0.075, 0.05, 0.105, 0.125, 0.135, 0.095, 0.085, 0.105, 0.11, 0.115]
    larguras = [largura_util * fracao for fracao in proporcoes]
    nomes = [
        "Data", "Hora", "Tipo de registro", "Atividade", "Local",
        "Situação", "Viatura", "Registrado por", "Relato", "Providências",
    ]
    if not grupos:
        elementos.append(Paragraph("Nenhuma atividade encontrada.", subtitulo))
    for grupo in grupos:
        detalhes = _detalhes_grupo(grupo, cache)
        elementos.append(p(grupo["titulo"], grupo_estilo))
        elementos.append(p(f'Total de atividades deste grupo: {len(grupo["atividades"])}', detalhe_estilo))
        if grupo["cartao_id"] is not None:
            if detalhes["escalas"]:
                for escala in detalhes["escalas"]:
                    elementos.append(p(_texto_escala(escala), detalhe_estilo))
            else:
                elementos.append(p("Efetivo escalado não identificado.", detalhe_estilo))
        else:
            elementos.append(p("Sem vínculo com Cartão Programa; efetivo não atribuído.", detalhe_estilo))
        elementos.append(Spacer(1, 2 * mm))
        linhas = [[p(nome, cabecalho) for nome in nomes]]
        for item in grupo["atividades"]:
            linhas.append([
                p(formatar_data(item["data"])),
                p(formatar_hora(item["horario"])),
                p(item["tipo_label"]), p(item["descricao"]), p(item["local"]),
                p(item["situacao"]), p(item["viatura"]), p(item["responsavel"]),
                p(item["relato"]), p(item["providencias"]),
            ])
        tabela = LongTable(linhas, colWidths=larguras, repeatRows=1, hAlign="CENTER")
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
        canvas.drawString(8 * mm, 7 * mm, "RECOM - Histórico de Atividades")
        canvas.drawRightString(pagina[0] - 8 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    resposta = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    resposta["Content-Disposition"] = 'attachment; filename="historico_atividades_recom.pdf"'
    buffer.close()
    return resposta
