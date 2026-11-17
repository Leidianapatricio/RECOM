import csv
import re

from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    KeepTogether,
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
# EXPORTAR HISTÓRICO CSV
# =========================================================

@login_required
def exportar_historico_csv(request):

    dados = consultar_atividades(
        request
    )

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        'attachment; filename="historico_recom.csv"'
    )

    # BOM UTF-8 para preservar os acentos.

    response.write("\ufeff")

    writer = csv.writer(
        response,
        delimiter=";",
    )

    # -----------------------------------------------------
    # CABEÇALHO
    # -----------------------------------------------------

    writer.writerow([

        "Data",
        "Horário",
        "Atividade",
        "Descrição",
        "Local",
        "Situação",
        "Cartão Programa",
        "Viatura",
        "Equipe",
        "Registrado por",
        "Efetivo escalado",
        "Relato",
        "Providências",

    ])

    # -----------------------------------------------------
    # REGISTROS
    # -----------------------------------------------------

    def texto_seguro_csv(valor):

        if isinstance(valor, str):

            if valor.lstrip().startswith(
                ("=", "+", "-", "@")
            ):

                return "'" + valor

        return valor

    for item in dados["atividades"]:

        linha = [

            formatar_data(
                item["data"]
            ),

            formatar_hora(
                item["horario"]
            ),

            item["tipo_label"],

            item["descricao"],

            item["local"],

            item["situacao"],

            item["cartao_programa"],

            item["viatura"],

            item["equipe"],

            item["responsavel"],

            texto_efetivo(
                item["efetivo"]
            ),

            item["relato"],

            item["providencias"],

        ]

        writer.writerow([

            texto_seguro_csv(valor)

            for valor in linha

        ])

    return response


# =========================================================
# EXPORTAR HISTÓRICO PDF
# =========================================================

@login_required
def exportar_historico_pdf(request):

    dados = consultar_atividades(
        request
    )

    buffer = BytesIO()

    # -----------------------------------------------------
    # CONFIGURAÇÃO DO DOCUMENTO
    # -----------------------------------------------------

    documento = SimpleDocTemplate(

        buffer,

        pagesize=(
            21 * cm,
            29.7 * cm,
        ),

        rightMargin=1.5 * cm,

        leftMargin=1.5 * cm,

        topMargin=1.5 * cm,

        bottomMargin=1.5 * cm,

        title="Histórico de Atividades - RECOM",

    )

    estilos = getSampleStyleSheet()

    # -----------------------------------------------------
    # ESTILO DO TÍTULO
    # -----------------------------------------------------

    estilos.add(

        ParagraphStyle(

            name="TituloRECOM",

            parent=estilos["Heading1"],

            alignment=TA_CENTER,

            textColor=colors.HexColor(
                "#092B49"
            ),

            spaceAfter=12,

        )

    )

    # -----------------------------------------------------
    # ESTILO DO TEXTO
    # -----------------------------------------------------

    estilos.add(

        ParagraphStyle(

            name="TextoRECOM",

            parent=estilos["BodyText"],

            fontSize=9,

            leading=13,

            spaceAfter=5,

        )

    )

    # -----------------------------------------------------
    # CABEÇALHO
    # -----------------------------------------------------

    elementos = [

        Paragraph(

            "RECOM - Histórico de Atividades",

            estilos["TituloRECOM"],

        ),

        Paragraph(

            f"Total de atividades: "
            f"{len(dados['atividades'])}",

            estilos["TextoRECOM"],

        ),

        Spacer(
            1,
            0.4 * cm,
        ),

    ]

    # -----------------------------------------------------
    # FUNÇÃO AUXILIAR
    # -----------------------------------------------------

    def paragrafo(rotulo, valor):

        valor = escape(
            str(valor or "-")
        )

        valor = valor.replace(
            "\n",
            "<br/>",
        )

        return Paragraph(

            f"<b>{rotulo}:</b> {valor}",

            estilos["TextoRECOM"],

        )

    # -----------------------------------------------------
    # MONTAR ATIVIDADES
    # -----------------------------------------------------

    for item in dados["atividades"]:

        detalhes = [

            paragrafo(

                "Data e horário",

                (
                    f"{formatar_data(item['data'])} "
                    f"às {formatar_hora(item['horario'])}"
                ),

            ),

            paragrafo(

                "Atividade",

                item["tipo_label"],

            ),

            paragrafo(

                "Descrição",

                item["descricao"],

            ),

            paragrafo(

                "Local",

                item["local"],

            ),

            paragrafo(

                "Situação",

                item["situacao"],

            ),

            paragrafo(

                "Cartão Programa",

                item["cartao_programa"],

            ),

            paragrafo(

                "Viatura",

                item["viatura"],

            ),

            paragrafo(

                "Equipe",

                item["equipe"],

            ),

            paragrafo(

                "Registrado por",

                item["responsavel"],

            ),

            paragrafo(

                "Efetivo escalado",

                texto_efetivo(
                    item["efetivo"]
                ),

            ),

            paragrafo(

                "Relato",

                item["relato"],

            ),

            paragrafo(

                "Providências",

                item["providencias"],

            ),

        ]

        elementos.append(

            KeepTogether([

                *detalhes,

                Spacer(
                    1,
                    0.25 * cm,
                ),

            ])

        )

    # -----------------------------------------------------
    # NENHUM REGISTRO
    # -----------------------------------------------------

    if not dados["atividades"]:

        elementos.append(

            Paragraph(

                "Nenhuma atividade encontrada "
                "para os filtros.",

                estilos["TextoRECOM"],

            )

        )

    # -----------------------------------------------------
    # GERAR PDF
    # -----------------------------------------------------

    documento.build(
        elementos
    )

    response = HttpResponse(

        buffer.getvalue(),

        content_type="application/pdf",

    )

    response["Content-Disposition"] = (
        'attachment; filename="historico_recom.pdf"'
    )

    buffer.close()

    return response