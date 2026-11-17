from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_GET

from .forms import (
    OcorrenciaForm,
    PessoaEnvolvidaFormSet,
    VeiculoEnvolvidoFormSet,
)

from .models import Ocorrencia

from .permissoes import (
    obter_usuario_recom,
    pode_gerenciar_ocorrencias,
    pode_consultar_ocorrencias,
    pode_cadastrar_ocorrencias,
    pode_visualizar_ocorrencia,
    pode_editar_ocorrencia,
    pode_excluir_ocorrencia,
    cartoes_disponiveis,
    filtrar_ocorrencias,
    verificar_permissao,
)


# ==========================================================
# FORMULÁRIOS
# ==========================================================

def preparar_formularios(request, ocorrencia=None):
    """
    Inicializa o formulário principal e os formsets.
    """

    if ocorrencia is None:
        ocorrencia = Ocorrencia()

    dados = (
        request.POST
        if request.method == "POST"
        else None
    )

    form = OcorrenciaForm(
        dados,
        instance=ocorrencia,
        usuario_logado=request.user,
    )

    pessoas_formset = PessoaEnvolvidaFormSet(
        dados,
        instance=ocorrencia,
        prefix="pessoas",
    )

    veiculos_formset = VeiculoEnvolvidoFormSet(
        dados,
        instance=ocorrencia,
        prefix="veiculos",
        form_kwargs={
            "ocorrencia": ocorrencia
        },
    )

    return (
        form,
        pessoas_formset,
        veiculos_formset,
    )


# ==========================================================
# VALIDAR FORMULÁRIOS
# ==========================================================

def validar_formularios(
    form,
    pessoas_formset,
    veiculos_formset,
):

    form_valido = form.is_valid()

    pessoas_validas = pessoas_formset.is_valid()

    veiculos_validos = veiculos_formset.is_valid()

    return (
        form_valido
        and pessoas_validas
        and veiculos_validos
    )


# ==========================================================
# APRESENTAR ERROS DE VALIDAÇÃO
# ==========================================================

def adicionar_erros_validacao(form, erro):

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():

            if campo == "__all__":

                form.add_error(None, erros)

            elif campo in form.fields:

                form.add_error(campo, erros)

            else:

                form.add_error(None, erros)

    else:

        form.add_error(None, erro)


# ==========================================================
# VALIDAR VÍNCULO COM O CARTÃO PROGRAMA
# ==========================================================

def validar_cartao_ocorrencia(
    request,
    ocorrencia,
    usuario,
):

    verificar_permissao(
        pode_cadastrar_ocorrencias(
            request,
            usuario,
        )
    )

    cartoes = cartoes_disponiveis(
        request,
        usuario,
        data=ocorrencia.data,
    )

    # ------------------------------------------------------
    # CARTÃO INFORMADO
    # ------------------------------------------------------

    if ocorrencia.cartao_programa_id:

        if not cartoes.filter(
            pk=ocorrencia.cartao_programa_id
        ).exists():

            raise ValidationError({
                "cartao_programa": (
                    "O Cartão Programa informado não está "
                    "disponível para o usuário nesta data."
                )
            })

    # ------------------------------------------------------
    # CARTÃO NÃO INFORMADO
    # ------------------------------------------------------

    elif not pode_gerenciar_ocorrencias(
        request,
        usuario,
    ):

        quantidade = cartoes.count()

        if quantidade == 1:

            ocorrencia.cartao_programa = (
                cartoes.first()
            )

        elif quantidade > 1:

            raise ValidationError({
                "cartao_programa": (
                    "Selecione o Cartão Programa "
                    "correspondente à sua escala."
                )
            })

    # Novos registros não terão vínculo com viatura.

    ocorrencia.viatura = None

    return ocorrencia


# ==========================================================
# SALVAR OCORRÊNCIA E REGISTROS RELACIONADOS
# ==========================================================

def salvar_formularios(
    form,
    pessoas_formset,
    veiculos_formset,
    request,
    usuario,
):
    """
    Salva a ocorrência, pessoas e veículos
    em uma única transação.

    Preserva o autor e o vínculo original
    durante a edição.
    """

    with transaction.atomic():

        ocorrencia = form.save(commit=False)

        # ==================================================
        # CADASTRO
        # ==================================================

        if not ocorrencia.pk:

            ocorrencia.registrado_por = request.user

            ocorrencia = validar_cartao_ocorrencia(
                request,
                ocorrencia,
                usuario,
            )

        # ==================================================
        # EDIÇÃO
        # ==================================================

        else:

            ocorrencia_original = get_object_or_404(

                Ocorrencia.objects.select_for_update(),

                pk=ocorrencia.pk,
            )

            # Revalida a autorização antes de salvar.

            verificar_permissao(
                pode_editar_ocorrencia(
                    request,
                    ocorrencia_original,
                    usuario,
                )
            )

            # Preserva o autor original.

            ocorrencia.registrado_por_id = (
                ocorrencia_original.registrado_por_id
            )

            # Preserva o Cartão Programa original.

            ocorrencia.cartao_programa_id = (
                ocorrencia_original.cartao_programa_id
            )

            # Preserva a viatura das ocorrências antigas.

            ocorrencia.viatura_id = (
                ocorrencia_original.viatura_id
            )

            # Impede a alteração da data de registros
            # vinculados a um cartão ou viatura.

            if (
                ocorrencia_original.cartao_programa_id
                or ocorrencia_original.viatura_id
            ):

                ocorrencia.data = (
                    ocorrencia_original.data
                )

        # ==================================================
        # VALIDAR E SALVAR OCORRÊNCIA
        # ==================================================

        ocorrencia.full_clean()

        ocorrencia.save()

        # ==================================================
        # VINCULAR FORMSETS
        # ==================================================

        pessoas_formset.instance = ocorrencia

        veiculos_formset.instance = ocorrencia

        # ==================================================
        # SALVAR PESSOAS ENVOLVIDAS
        # ==================================================

        pessoas_formset.save()

        # ==================================================
        # SALVAR VEÍCULOS ENVOLVIDOS
        # ==================================================

        veiculos = veiculos_formset.save(
            commit=False
        )

        for veiculo in veiculos:

            veiculo.ocorrencia = ocorrencia

            veiculo.full_clean()

            veiculo.save()

        # ==================================================
        # EXCLUIR VEÍCULOS REMOVIDOS
        # ==================================================

        for veiculo in veiculos_formset.deleted_objects:

            veiculo.delete()

        veiculos_formset.save_m2m()

    return ocorrencia


# ==========================================================
# LISTAR OCORRÊNCIAS
# ==========================================================

@login_required
def listar_ocorrencias(request):

    usuario = obter_usuario_recom(request)

    verificar_permissao(
        pode_consultar_ocorrencias(
            request,
            usuario,
        )
    )

    # ------------------------------------------------------
    # CONSULTA PRINCIPAL
    # ------------------------------------------------------

    ocorrencias = (
        Ocorrencia.objects.select_related(
            "registrado_por",
            "viatura",
            "viatura__equipe",
            "viatura__plantao",
            "cartao_programa",
            "cartao_programa__plantao",
        ).all()
    )

    # ------------------------------------------------------
    # APLICAR PERMISSÕES
    # ------------------------------------------------------

    ocorrencias = filtrar_ocorrencias(
        request,
        ocorrencias,
        usuario,
    )

    # ------------------------------------------------------
    # RECEBER FILTROS
    # ------------------------------------------------------

    busca = request.GET.get(
        "busca",
        "",
    ).strip()

    categoria = request.GET.get(
        "categoria",
        "",
    ).strip()

    natureza = request.GET.get(
        "natureza",
        "",
    ).strip()

    data_inicio = request.GET.get(
        "data_inicio",
        "",
    ).strip()

    data_fim = request.GET.get(
        "data_fim",
        "",
    ).strip()

    # ------------------------------------------------------
    # FILTRO DE BUSCA
    # ------------------------------------------------------

    if busca:

        filtro_busca = (

            Q(local__icontains=busca)

            | Q(bairro__icontains=busca)

            | Q(relato__icontains=busca)

            | Q(equipe_apoiada__icontains=busca)

            | Q(
                viatura__identificacao__icontains=busca
            )

        )

        if busca.isascii() and busca.isdecimal():

            filtro_busca |= Q(
                cartao_programa_id=int(busca)
            )

        ocorrencias = ocorrencias.filter(
            filtro_busca
        )

    # ------------------------------------------------------
    # FILTRO DE CATEGORIA
    # ------------------------------------------------------

    if categoria:

        ocorrencias = ocorrencias.filter(
            categoria=categoria
        )

    # ------------------------------------------------------
    # FILTRO DE NATUREZA
    # ------------------------------------------------------

    if natureza:

        ocorrencias = ocorrencias.filter(
            natureza_atuacao=natureza
        )

    # ------------------------------------------------------
    # FILTRO DE DATA INICIAL
    # ------------------------------------------------------

    if data_inicio:

        try:

            inicio = date.fromisoformat(
                data_inicio
            )

            ocorrencias = ocorrencias.filter(
                data__gte=inicio
            )

        except ValueError:

            data_inicio = ""

    # ------------------------------------------------------
    # FILTRO DE DATA FINAL
    # ------------------------------------------------------

    if data_fim:

        try:

            fim = date.fromisoformat(
                data_fim
            )

            ocorrencias = ocorrencias.filter(
                data__lte=fim
            )

        except ValueError:

            data_fim = ""

    # ------------------------------------------------------
    # ORDENAÇÃO
    # ------------------------------------------------------

    ocorrencias = ocorrencias.order_by(
        "-data",
        "-horario",
        "-id",
    )

    # ------------------------------------------------------
    # PAGINAÇÃO
    # ------------------------------------------------------

    paginator = Paginator(
        ocorrencias,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # ------------------------------------------------------
    # IDENTIFICAR PERMISSÕES INDIVIDUAIS
    # ------------------------------------------------------

    gestor = pode_gerenciar_ocorrencias(
        request,
        usuario,
    )

    for ocorrencia in page_obj:

        ocorrencia.pode_editar_usuario = (
            pode_editar_ocorrencia(
                request,
                ocorrencia,
                usuario,
            )
        )

        ocorrencia.pode_excluir_usuario = (
            pode_excluir_ocorrencia(
                request,
                ocorrencia,
                usuario,
            )
        )

    # ------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------

    context = {

        "ocorrencias": page_obj,

        "page_obj": page_obj,

        "busca": busca,

        "categoria_selecionada": categoria,

        "natureza_selecionada": natureza,

        "data_inicio": data_inicio,

        "data_fim": data_fim,

        "categorias": Ocorrencia.Categoria.choices,

        "naturezas": (
            Ocorrencia.NaturezaAtuacao.choices
        ),

        "pode_cadastrar": (
            pode_cadastrar_ocorrencias(
                request,
                usuario,
            )
        ),

        "pode_gerenciar": gestor,

        "usuario_recom": usuario,

    }

    return render(
        request,
        "ocorrencias/listar_ocorrencias.html",
        context,
    )


# ==========================================================
# CADASTRAR OCORRÊNCIA
# ==========================================================

@login_required
def cadastrar_ocorrencia(request):

    usuario = obter_usuario_recom(request)

    verificar_permissao(
        pode_cadastrar_ocorrencias(
            request,
            usuario,
        )
    )

    # ------------------------------------------------------
    # PREPARAR FORMULÁRIOS
    # ------------------------------------------------------

    form, pessoas_formset, veiculos_formset = (
        preparar_formularios(request)
    )

    # ------------------------------------------------------
    # PROCESSAR FORMULÁRIO
    # ------------------------------------------------------

    if request.method == "POST":

        if validar_formularios(
            form,
            pessoas_formset,
            veiculos_formset,
        ):

            try:

                ocorrencia = salvar_formularios(
                    form,
                    pessoas_formset,
                    veiculos_formset,
                    request,
                    usuario,
                )

            except ValidationError as erro:

                adicionar_erros_validacao(
                    form,
                    erro,
                )

            except IntegrityError:

                form.add_error(
                    None,
                    "Não foi possível salvar a ocorrência. "
                    "Verifique os dados informados.",
                )

            else:

                messages.success(
                    request,
                    "Ocorrência cadastrada com sucesso!",
                )

                return redirect(
                    "ocorrencias:detalhe_ocorrencia",
                    pk=ocorrencia.pk,
                )

        messages.error(
            request,
            "Verifique os campos informados.",
        )

    # ------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------

    context = {

        "form": form,

        "pessoas_formset": pessoas_formset,

        "veiculos_formset": veiculos_formset,

        "titulo": "Nova Ocorrência",

        "modo_edicao": False,

        "usuario_recom": usuario,

        "pode_gerenciar": (
            pode_gerenciar_ocorrencias(
                request,
                usuario,
            )
        ),

    }

    return render(
        request,
        "ocorrencias/form_ocorrencia.html",
        context,
    )


# ==========================================================
# DETALHE DA OCORRÊNCIA
# ==========================================================

@login_required
def detalhe_ocorrencia(request, pk):

    usuario = obter_usuario_recom(request)

    verificar_permissao(
        pode_consultar_ocorrencias(
            request,
            usuario,
        )
    )

    # ------------------------------------------------------
    # CONSULTAR OCORRÊNCIA
    # ------------------------------------------------------

    ocorrencias = (
        Ocorrencia.objects.select_related(

            "registrado_por",

            "viatura",

            "viatura__equipe",

            "viatura__plantao",

            "cartao_programa",

            "cartao_programa__plantao",

        ).prefetch_related(

            "pessoas_envolvidas",

            "veiculos_envolvidos",

        )
    )

    ocorrencias = filtrar_ocorrencias(
        request,
        ocorrencias,
        usuario,
    )

    ocorrencia = get_object_or_404(
        ocorrencias,
        pk=pk,
    )

    # ------------------------------------------------------
    # VALIDAR PERMISSÃO INDIVIDUAL
    # ------------------------------------------------------

    verificar_permissao(
        pode_visualizar_ocorrencia(
            request,
            ocorrencia,
            usuario,
        )
    )

    # ------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------

    context = {

        "ocorrencia": ocorrencia,

        "pessoas": (
            ocorrencia.pessoas_envolvidas.all()
        ),

        "veiculos": (
            ocorrencia.veiculos_envolvidos.all()
        ),

        "pode_editar": pode_editar_ocorrencia(
            request,
            ocorrencia,
            usuario,
        ),

        "pode_excluir": pode_excluir_ocorrencia(
            request,
            ocorrencia,
            usuario,
        ),

        "usuario_recom": usuario,

    }

    return render(
        request,
        "ocorrencias/detalhe_ocorrencia.html",
        context,
    )


# ==========================================================
# EDITAR OCORRÊNCIA
# ==========================================================

@login_required
def editar_ocorrencia(request, pk):

    usuario = obter_usuario_recom(request)

    # ------------------------------------------------------
    # CONSULTAR OCORRÊNCIA
    # ------------------------------------------------------

    ocorrencia = get_object_or_404(

        Ocorrencia.objects.select_related(

            "registrado_por",

            "viatura",

            "viatura__plantao",

            "cartao_programa",

            "cartao_programa__plantao",

        ),

        pk=pk,

    )

    # ------------------------------------------------------
    # VALIDAR PERMISSÃO
    # ------------------------------------------------------

    verificar_permissao(
        pode_editar_ocorrencia(
            request,
            ocorrencia,
            usuario,
        )
    )

    # ------------------------------------------------------
    # PREPARAR FORMULÁRIOS
    # ------------------------------------------------------

    form, pessoas_formset, veiculos_formset = (
        preparar_formularios(
            request,
            ocorrencia=ocorrencia,
        )
    )

    # ------------------------------------------------------
    # PROCESSAR EDIÇÃO
    # ------------------------------------------------------

    if request.method == "POST":

        if validar_formularios(
            form,
            pessoas_formset,
            veiculos_formset,
        ):

            try:

                ocorrencia = salvar_formularios(
                    form,
                    pessoas_formset,
                    veiculos_formset,
                    request,
                    usuario,
                )

            except ValidationError as erro:

                adicionar_erros_validacao(
                    form,
                    erro,
                )

            except IntegrityError:

                form.add_error(
                    None,
                    "Não foi possível atualizar "
                    "a ocorrência. Verifique os dados.",
                )

            else:

                messages.success(
                    request,
                    "Ocorrência atualizada com sucesso!",
                )

                return redirect(
                    "ocorrencias:detalhe_ocorrencia",
                    pk=ocorrencia.pk,
                )

        messages.error(
            request,
            "Verifique os campos informados.",
        )

    # ------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------

    context = {

        "form": form,

        "pessoas_formset": pessoas_formset,

        "veiculos_formset": veiculos_formset,

        "ocorrencia": ocorrencia,

        "titulo": "Editar Ocorrência",

        "modo_edicao": True,

        "usuario_recom": usuario,

        "pode_gerenciar": (
            pode_gerenciar_ocorrencias(
                request,
                usuario,
            )
        ),

    }

    return render(
        request,
        "ocorrencias/form_ocorrencia.html",
        context,
    )


# ==========================================================
# EXCLUIR OCORRÊNCIA
# ==========================================================

@login_required
def excluir_ocorrencia(request, pk):

    usuario = obter_usuario_recom(request)

    # ------------------------------------------------------
    # CONSULTAR OCORRÊNCIA
    # ------------------------------------------------------

    ocorrencia = get_object_or_404(

        Ocorrencia.objects.select_related(

            "registrado_por",

            "viatura",

            "viatura__plantao",

            "cartao_programa",

            "cartao_programa__plantao",

        ),

        pk=pk,

    )

    # ------------------------------------------------------
    # VALIDAR PERMISSÃO
    # ------------------------------------------------------

    verificar_permissao(
        pode_excluir_ocorrencia(
            request,
            ocorrencia,
            usuario,
        )
    )

    # ------------------------------------------------------
    # CONFIRMAR EXCLUSÃO
    # ------------------------------------------------------

    if request.method == "POST":

        with transaction.atomic():

            ocorrencia = get_object_or_404(

                Ocorrencia.objects.select_for_update(),

                pk=pk,

            )

            # Revalida a permissão antes de excluir.

            verificar_permissao(
                pode_excluir_ocorrencia(
                    request,
                    ocorrencia,
                    usuario,
                )
            )

            ocorrencia.delete()

        messages.success(
            request,
            "Ocorrência excluída com sucesso!",
        )

        return redirect(
            "ocorrencias:listar_ocorrencias"
        )

    # ------------------------------------------------------
    # PÁGINA DE CONFIRMAÇÃO
    # ------------------------------------------------------

    return render(

        request,

        "ocorrencias/confirmar_exclusao.html",

        {
            "ocorrencia": ocorrencia,
        },

    )


# ==========================================================
# API - CONSULTAR CARTÕES PROGRAMA DISPONÍVEIS
# ==========================================================

@login_required
@require_GET
def consultar_cartoes_ocorrencia(request):

    usuario = obter_usuario_recom(request)

    verificar_permissao(
        pode_cadastrar_ocorrencias(
            request,
            usuario,
        )
    )

    # ------------------------------------------------------
    # RECEBER DATA DA OCORRÊNCIA
    # ------------------------------------------------------

    data_informada = request.GET.get(
        "data",
        "",
    ).strip()

    if not data_informada:

        return JsonResponse({
            "cartoes": [],
        })

    # ------------------------------------------------------
    # VALIDAR DATA
    # ------------------------------------------------------

    try:

        data_ocorrencia = date.fromisoformat(
            data_informada
        )

    except ValueError:

        return JsonResponse(
            {
                "erro": "Data inválida.",
                "cartoes": [],
            },
            status=400,
        )

    # ------------------------------------------------------
    # CONSULTAR CARTÕES AUTORIZADOS
    # ------------------------------------------------------

    cartoes = cartoes_disponiveis(
        request,
        usuario,
        data=data_ocorrencia,
    )

    resultado = []

    for cartao in cartoes:

        data_formatada = (
            cartao.plantao.data.strftime(
                "%d/%m/%Y"
            )
        )

        tipo_servico = (
            cartao.plantao.get_tipo_servico_display()
        )

        resultado.append({

            "id": cartao.pk,

            "data": (
                cartao.plantao.data.isoformat()
            ),

            "tipo_servico": tipo_servico,

            "descricao": (
                f"CP {cartao.pk} - "
                f"{data_formatada} - "
                f"{tipo_servico}"
            ),

        })

    return JsonResponse({

        "cartoes": resultado,

    })