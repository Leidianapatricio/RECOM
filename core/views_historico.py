
import csv
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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

from cartao_programa.models import (
    EfetivoViatura,
    Equipe,
    MissaoCartao,
    ViaturaPlantao,
)
from ocorrencias.models import Ocorrencia
from usuarios.models import Usuario
from visitas.models import RondaVisita


# =========================================================
# PERMISSÕES
# =========================================================

def obter_acesso_historico(request):

    if not request.user.is_active:
        raise PermissionDenied("Usuário inativo.")

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

    if usuario.perfil in ("ADMIN", "COORDENADOR"):
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

    return valor.strftime("%d/%m/%Y") if valor else "-"


def formatar_hora(valor):

    return valor.strftime("%H:%M") if valor else "-"


def nome_responsavel(usuario):

    if usuario is None:
        return "Não informado"

    nome = getattr(usuario, "nome", None)

    if nome:
        return nome

    return str(usuario)


def obter_equipe(viatura):

    if viatura is None:
        return "Não identificada"

    if viatura.equipe_id:
        return viatura.equipe.nome

    return "Extraordinária"


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


def texto_efetivo(efetivo):

    if not efetivo:
        return "Não informado"

    return "; ".join(
        f"{item['nome']} ({item['funcao']})"
        for item in efetivo
    )


# =========================================================
# CONSULTAR E FILTRAR ATIVIDADES
# =========================================================

def consultar_atividades(request):

    usuario, gestor = obter_acesso_historico(request)

    data_inicio = request.GET.get(
        "data_inicio", ""
    ).strip()

    data_fim = request.GET.get(
        "data_fim", ""
    ).strip()

    equipe_id = request.GET.get(
        "equipe", ""
    ).strip()

    viatura_id = request.GET.get(
        "viatura", ""
    ).strip()

    tipo = request.GET.get(
        "tipo", ""
    ).strip()

    inicio = converter_data(data_inicio)
    fim = converter_data(data_fim)

    if data_inicio and inicio is None:
        raise PermissionDenied("Data inicial inválida.")

    if data_fim and fim is None:
        raise PermissionDenied("Data final inválida.")

    if inicio and fim and inicio > fim:
        raise PermissionDenied(
            "A data inicial não pode ser posterior à final."
        )

    # -----------------------------------------------------
    # VIATURAS PERMITIDAS
    # -----------------------------------------------------

    viaturas = ViaturaPlantao.objects.select_related(
        "plantao",
        "equipe",
    )

    if not gestor:

        escalas = EfetivoViatura.objects.filter(
            gcm=usuario
        )

        viaturas = viaturas.filter(
            pk__in=escalas.values("viatura_id")
        )

    # -----------------------------------------------------
    # FILTROS DE VIATURA E EQUIPE
    # -----------------------------------------------------

    if equipe_id:

        if not equipe_id.isdigit():
            raise PermissionDenied("Equipe inválida.")

        viaturas = viaturas.filter(
            equipe_id=int(equipe_id)
        )

    if viatura_id:

        if not viatura_id.isdigit():
            raise PermissionDenied("Viatura inválida.")

        viaturas = viaturas.filter(
            pk=int(viatura_id)
        )

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
        "pk", flat=True
    )

    # -----------------------------------------------------
    # VISITAS
    # -----------------------------------------------------

    visitas = RondaVisita.objects.select_related(
        "escola",
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "missao_cartao",
        "registrado_por",
    ).prefetch_related(
        "viatura__efetivo__gcm"
    )

    if gestor:

        # Gestores também consultam registros antigos
        # sem viatura, desde que não estejam filtrando
        # por uma viatura ou equipe específica.
        if equipe_id or viatura_id:
            visitas = visitas.filter(
                viatura_id__in=ids_viaturas
            )

    else:

        visitas = visitas.filter(
            viatura_id__in=ids_viaturas
        )

    if inicio:
        visitas = visitas.filter(
            data_visita__gte=inicio
        )

    if fim:
        visitas = visitas.filter(
            data_visita__lte=fim
        )

    # -----------------------------------------------------
    # OCORRÊNCIAS
    # -----------------------------------------------------

    ocorrencias = Ocorrencia.objects.select_related(
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "registrado_por",
    ).prefetch_related(
        "viatura__efetivo__gcm"
    )

    if gestor:

        if equipe_id or viatura_id:
            ocorrencias = ocorrencias.filter(
                viatura_id__in=ids_viaturas
            )

    else:

        ocorrencias = ocorrencias.filter(
            viatura_id__in=ids_viaturas
        )

    if inicio:
        ocorrencias = ocorrencias.filter(
            data__gte=inicio
        )

    if fim:
        ocorrencias = ocorrencias.filter(
            data__lte=fim
        )

    # -----------------------------------------------------
    # MISSÕES NÃO REALIZADAS
    # -----------------------------------------------------

    missoes = MissaoCartao.objects.filter(
        status_execucao="NAO_REALIZADA",
        viatura_id__in=ids_viaturas,
    ).select_related(
        "escola",
        "viatura",
        "viatura__plantao",
        "viatura__equipe",
        "registrado_por",
    ).prefetch_related(
        "viatura__efetivo__gcm"
    )

    atividades = []

    # -----------------------------------------------------
    # MONTAR VISITAS
    # -----------------------------------------------------

    if tipo in ("", "VISITA_PROGRAMADA", "VISITA_AVULSA"):

        for visita in visitas:

            tipo_visita = (
                "VISITA_PROGRAMADA"
                if visita.missao_cartao_id
                else "VISITA_AVULSA"
            )

            if tipo and tipo != tipo_visita:
                continue

            viatura = visita.viatura

            atividades.append({
                "id": visita.pk,
                "tipo": tipo_visita,
                "tipo_label": (
                    "Visita programada"
                    if visita.missao_cartao_id
                    else "Visita avulsa"
                ),
                "data": visita.data_visita,
                "horario": visita.horario,
                "local": visita.escola.nome,
                "descricao": visita.get_tipo_visita_display(),
                "situacao": visita.get_situacao_display(),
                "relato": visita.relato or "",
                "providencias": visita.orientacoes or "",
                "viatura": (
                    viatura.identificacao
                    if viatura
                    else "Não vinculada"
                ),
                "equipe": (
                    obter_equipe(viatura)
                    if viatura
                    else visita.get_equipe_display()
                ),
                "responsavel": nome_responsavel(
                    visita.registrado_por
                ),
                "efetivo": obter_efetivo(viatura),
                "viatura_id": visita.viatura_id,
            })

    # -----------------------------------------------------
    # MONTAR OCORRÊNCIAS
    # -----------------------------------------------------

    if tipo in ("", "OCORRENCIA"):

        for ocorrencia in ocorrencias:

            viatura = ocorrencia.viatura

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
                "relato": ocorrencia.relato,
                "providencias": ocorrencia.providencias,
                "viatura": (
                    viatura.identificacao
                    if viatura
                    else "Não vinculada"
                ),
                "equipe": obter_equipe(viatura),
                "responsavel": nome_responsavel(
                    ocorrencia.registrado_por
                ),
                "efetivo": obter_efetivo(viatura),
                "viatura_id": ocorrencia.viatura_id,
            })

    # -----------------------------------------------------
    # MONTAR MISSÕES NÃO REALIZADAS
    # -----------------------------------------------------

    if tipo in ("", "MISSAO_NAO_REALIZADA"):

        for missao in missoes:

            viatura = missao.viatura

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
                "descricao": missao.get_tipo_missao_display(),
                "situacao": "Não realizada",
                "relato": missao.motivo_nao_realizacao,
                "providencias": "",
                "viatura": viatura.identificacao,
                "equipe": obter_equipe(viatura),
                "responsavel": nome_responsavel(
                    missao.registrado_por
                ),
                "efetivo": obter_efetivo(viatura),
                "viatura_id": missao.viatura_id,
            })

    # -----------------------------------------------------
    # ORDENAÇÃO
    # -----------------------------------------------------

    atividades.sort(
        key=lambda item: (
            item["data"],
            item["horario"] or datetime.min.time(),
            item["id"],
        ),
        reverse=True,
    )

    # -----------------------------------------------------
    # OPÇÕES DOS FILTROS
    # -----------------------------------------------------

    if gestor:

        equipes_disponiveis = Equipe.objects.filter(
            pk__in=ViaturaPlantao.objects.values(
                "equipe_id"
            )
        ).distinct().order_by("nome")

        viaturas_disponiveis = (
            ViaturaPlantao.objects
            .select_related("plantao", "equipe")
            .order_by("-plantao__data", "identificacao")
        )

    else:

        equipes_disponiveis = Equipe.objects.filter(
            pk__in=ViaturaPlantao.objects.filter(
                pk__in=EfetivoViatura.objects.filter(
                    gcm=usuario
                ).values("viatura_id")
            ).values("equipe_id")
        ).distinct().order_by("nome")

        viaturas_disponiveis = (
            ViaturaPlantao.objects
            .filter(
                pk__in=EfetivoViatura.objects.filter(
                    gcm=usuario
                ).values("viatura_id")
            )
            .select_related("plantao", "equipe")
            .distinct()
            .order_by("-plantao__data", "identificacao")
        )

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
# PÁGINA DO HISTÓRICO
# =========================================================

@login_required
def historico_atividades(request):

    dados = consultar_atividades(request)

    atividades = dados["atividades"]

    paginator = Paginator(
        atividades,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    dados["page_obj"] = page_obj
    dados["total_atividades"] = len(atividades)

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

    dados = consultar_atividades(request)

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        'attachment; filename="historico_recom.csv"'
    )

    response.write("\ufeff")

    writer = csv.writer(
        response,
        delimiter=";",
    )

    writer.writerow([
        "Data",
        "Horário",
        "Atividade",
        "Descrição",
        "Local",
        "Situação",
        "Viatura",
        "Equipe",
        "Registrado por",
        "Efetivo escalado",
        "Relato",
        "Providências",
    ])

    for item in dados["atividades"]:

        writer.writerow([
            formatar_data(item["data"]),
            formatar_hora(item["horario"]),
            item["tipo_label"],
            item["descricao"],
            item["local"],
            item["situacao"],
            item["viatura"],
            item["equipe"],
            item["responsavel"],
            texto_efetivo(item["efetivo"]),
            item["relato"],
            item["providencias"],
        ])

    return response


# =========================================================
# EXPORTAR HISTÓRICO PDF
# =========================================================

@login_required
def exportar_historico_pdf(request):

    dados = consultar_atividades(request)

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Histórico de Atividades - RECOM",
    )

    estilos = getSampleStyleSheet()

    estilos.add(
        ParagraphStyle(
            name="TituloRECOM",
            parent=estilos["Heading1"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#092B49"),
            spaceAfter=12,
        )
    )

    estilos.add(
        ParagraphStyle(
            name="TextoRECOM",
            parent=estilos["BodyText"],
            fontSize=9,
            leading=13,
            spaceAfter=5,
        )
    )

    elementos = [
        Paragraph(
            "RECOM - Histórico de Atividades",
            estilos["TituloRECOM"],
        ),
        Paragraph(
            f"Total de atividades: {len(dados['atividades'])}",
            estilos["TextoRECOM"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    def paragrafo(rotulo, valor):

        valor = escape(str(valor or "-"))

        return Paragraph(
            f"<b>{rotulo}:</b> {valor}",
            estilos["TextoRECOM"],
        )

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
                "Efetivo",
                texto_efetivo(item["efetivo"]),
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
                Spacer(1, 0.25 * cm),
            ])
        )

    if not dados["atividades"]:

        elementos.append(
            Paragraph(
                "Nenhuma atividade encontrada para os filtros.",
                estilos["TextoRECOM"],
            )
        )

    documento.build(elementos)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        'attachment; filename="historico_recom.pdf"'
    )

    buffer.close()

    return response
