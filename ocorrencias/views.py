
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from cartao_programa.models import EfetivoViatura
from usuarios.models import Usuario

from .forms import (
    OcorrenciaForm,
    PessoaEnvolvidaFormSet,
    VeiculoEnvolvidoFormSet,
)
from .models import Ocorrencia


# ==========================================================
# PERMISSÕES
# ==========================================================

FUNCOES_AUTORIZADAS = ("C", "P1")


def obter_usuario_recom(request):
    """
    Retorna o cadastro RECOM do usuário autenticado.
    """

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        return None

    return Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()


def pode_gerenciar_ocorrencias(request, usuario=None):
    """
    ADMIN e COORDENADOR podem gerenciar
    todas as ocorrências.
    """

    if not request.user.is_active:
        return False

    if request.user.is_superuser:
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return bool(
        usuario
        and usuario.perfil in ("ADMIN", "COORDENADOR")
    )


def pode_consultar_ocorrencias(request, usuario=None):
    """
    Perfis autorizados a consultar ocorrências.
    """

    if pode_gerenciar_ocorrencias(request, usuario):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return bool(
        usuario
        and usuario.perfil in ("GCM", "MEDIADOR")
    )


def viaturas_autorizadas_gcm(usuario):
    """
    Retorna os IDs das viaturas em que o GCM
    está escalado como C ou P1.
    """

    if (
        usuario is None
        or not usuario.ativo
        or usuario.perfil != "GCM"
    ):
        return EfetivoViatura.objects.none()

    return EfetivoViatura.objects.filter(
        gcm=usuario,
        funcao__in=FUNCOES_AUTORIZADAS,
    )


def pode_cadastrar_ocorrencias(request, usuario=None):
    """
    Gestores podem cadastrar.

    GCM somente pode cadastrar se possuir
    escala como C ou P1.
    """

    if pode_gerenciar_ocorrencias(request, usuario):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return viaturas_autorizadas_gcm(usuario).exists()


def gcm_autorizado_na_viatura(usuario, viatura_id):
    """
    Verifica a função efetivamente atribuída
    ao GCM na viatura do plantão.
    """

    if not viatura_id:
        return False

    return viaturas_autorizadas_gcm(usuario).filter(
        viatura_id=viatura_id
    ).exists()


def pode_editar_ocorrencia(request, ocorrencia, usuario=None):
    """
    Gestores editam todas.

    C e P1 podem editar ocorrências da
    própria viatura, mesmo quando cadastradas
    por outro integrante autorizado.
    """

    if pode_gerenciar_ocorrencias(request, usuario):
        return True

    if usuario is None:
        usuario = obter_usuario_recom(request)

    return gcm_autorizado_na_viatura(
        usuario,
        ocorrencia.viatura_id,
    )


def pode_excluir_ocorrencia(request, ocorrencia, usuario=None):
    """
    Utiliza a mesma autorização da edição.
    """

    return pode_editar_ocorrencia(
        request,
        ocorrencia,
        usuario,
    )


def verificar_permissao(permitido):
    """
    Não revela registros a usuários sem acesso.
    """

    if not permitido:
        raise Http404(
            "Ocorrência não encontrada ou acesso não autorizado."
        )


# ==========================================================
# FORMULÁRIOS
# ==========================================================

def preparar_formularios(request, ocorrencia=None):
    """
    Inicializa o formulário principal e os formsets.

    O usuário autenticado é enviado ao formulário
    para restringir as viaturas disponíveis.
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


def validar_formularios(
    form,
    pessoas_formset,
    veiculos_formset,
):
    """
    Valida todos os formulários.
    """

    form_valido = form.is_valid()
    pessoas_validas = pessoas_formset.is_valid()
    veiculos_validos = veiculos_formset.is_valid()

    return (
        form_valido
        and pessoas_validas
        and veiculos_validos
    )


def adicionar_erros_validacao(form, erro):
    """
    Converte erros do modelo em erros
    apresentados no formulário.
    """

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
# SALVAR OCORRÊNCIA E REGISTROS RELACIONADOS
# ==========================================================

def salvar_formularios(
    form,
    pessoas_formset,
    veiculos_formset,
    request,
    usuario,
    viatura_original_id=None,
):
    """
    Salva todos os registros em uma transação.

    Revalida as permissões antes de persistir
    os dados e preserva o autor original.
    """

    with transaction.atomic():

        ocorrencia = form.save(commit=False)

        if not ocorrencia.pk:
            ocorrencia.registrado_por = request.user

        if not pode_gerenciar_ocorrencias(request, usuario):

            # GCM não pode transferir a ocorrência
            # para outra viatura durante a edição.

            if (
                viatura_original_id is not None
                and ocorrencia.viatura_id != viatura_original_id
            ):
                raise ValidationError(
                    "Não é permitido alterar a viatura "
                    "responsável por esta ocorrência."
                )

            if not gcm_autorizado_na_viatura(
                usuario,
                ocorrencia.viatura_id,
            ):
                raise ValidationError(
                    "Você não está escalado como Comandante "
                    "ou Patrulheiro 1 nesta viatura."
                )

        if not ocorrencia.viatura_id:
            raise ValidationError(
                "Informe a viatura responsável."
            )

        ocorrencia.full_clean()
        ocorrencia.save()

        pessoas_formset.instance = ocorrencia
        veiculos_formset.instance = ocorrencia

        # Salva pessoas antes dos veículos.
        pessoas_formset.save()

        veiculos = veiculos_formset.save(
            commit=False
        )

        for veiculo in veiculos:

            veiculo.ocorrencia = ocorrencia
            veiculo.full_clean()
            veiculo.save()

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
        pode_consultar_ocorrencias(request, usuario)
    )

    ocorrencias = (
        Ocorrencia.objects
        .select_related(
            "registrado_por",
            "viatura",
            "viatura__equipe",
            "viatura__plantao",
        )
        .all()
    )

    busca = request.GET.get("busca", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    natureza = request.GET.get("natureza", "").strip()
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()

    if busca:
        ocorrencias = ocorrencias.filter(
            Q(local__icontains=busca)
            | Q(bairro__icontains=busca)
            | Q(relato__icontains=busca)
            | Q(equipe_apoiada__icontains=busca)
            | Q(viatura__identificacao__icontains=busca)
        )

    if categoria:
        ocorrencias = ocorrencias.filter(
            categoria=categoria
        )

    if natureza:
        ocorrencias = ocorrencias.filter(
            natureza_atuacao=natureza
        )

    # Datas inválidas não devem provocar
    # erro na página de listagem.

    if data_inicio:
        try:
            date.fromisoformat(data_inicio)
            ocorrencias = ocorrencias.filter(
                data__gte=data_inicio
            )
        except ValueError:
            data_inicio = ""

    if data_fim:
        try:
            date.fromisoformat(data_fim)
            ocorrencias = ocorrencias.filter(
                data__lte=data_fim
            )
        except ValueError:
            data_fim = ""

    ocorrencias = ocorrencias.order_by(
        "-data",
        "-horario",
        "-id",
    )

    paginator = Paginator(
        ocorrencias,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # Identifica os registros que o GCM
    # pode editar ou excluir na página.

    viaturas_permitidas = set()

    if (
        usuario is not None
        and usuario.perfil == "GCM"
    ):
        viaturas_permitidas = set(
            viaturas_autorizadas_gcm(usuario)
            .values_list("viatura_id", flat=True)
        )

    gestor = pode_gerenciar_ocorrencias(
        request,
        usuario,
    )

    for ocorrencia in page_obj:
        ocorrencia.pode_editar_usuario = (
            gestor
            or ocorrencia.viatura_id in viaturas_permitidas
        )
        ocorrencia.pode_excluir_usuario = (
            ocorrencia.pode_editar_usuario
        )

    context = {
        "ocorrencias": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "categoria_selecionada": categoria,
        "natureza_selecionada": natureza,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "categorias": Ocorrencia.Categoria.choices,
        "naturezas": Ocorrencia.NaturezaAtuacao.choices,
        "pode_cadastrar": pode_cadastrar_ocorrencias(
            request,
            usuario,
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
        pode_cadastrar_ocorrencias(request, usuario)
    )

    form, pessoas_formset, veiculos_formset = (
        preparar_formularios(request)
    )

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
                adicionar_erros_validacao(form, erro)

            except IntegrityError:
                form.add_error(
                    None,
                    "Já existe uma ocorrência registrada "
                    "para esta viatura, data e horário."
                )

            else:
                messages.success(
                    request,
                    "Ocorrência cadastrada com sucesso!"
                )

                return redirect(
                    "ocorrencias:detalhe_ocorrencia",
                    pk=ocorrencia.pk,
                )

        messages.error(
            request,
            "Verifique os campos informados."
        )

    context = {
        "form": form,
        "pessoas_formset": pessoas_formset,
        "veiculos_formset": veiculos_formset,
        "titulo": "Nova Ocorrência",
        "modo_edicao": False,
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
        pode_consultar_ocorrencias(request, usuario)
    )

    ocorrencia = get_object_or_404(
        Ocorrencia.objects.select_related(
            "registrado_por",
            "viatura",
            "viatura__equipe",
            "viatura__plantao",
        ).prefetch_related(
            "pessoas_envolvidas",
            "veiculos_envolvidos",
        ),
        pk=pk,
    )

    context = {
        "ocorrencia": ocorrencia,
        "pessoas": ocorrencia.pessoas_envolvidas.all(),
        "veiculos": ocorrencia.veiculos_envolvidos.all(),
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

    ocorrencia = get_object_or_404(
        Ocorrencia.objects.select_related(
            "viatura",
            "viatura__plantao",
        ),
        pk=pk,
    )

    verificar_permissao(
        pode_editar_ocorrencia(
            request,
            ocorrencia,
            usuario,
        )
    )

    viatura_original_id = ocorrencia.viatura_id

    form, pessoas_formset, veiculos_formset = (
        preparar_formularios(
            request,
            ocorrencia=ocorrencia,
        )
    )

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
                    viatura_original_id=viatura_original_id,
                )

            except ValidationError as erro:
                adicionar_erros_validacao(form, erro)

            except IntegrityError:
                form.add_error(
                    None,
                    "Já existe outra ocorrência registrada "
                    "para esta viatura, data e horário."
                )

            else:
                messages.success(
                    request,
                    "Ocorrência atualizada com sucesso!"
                )

                return redirect(
                    "ocorrencias:detalhe_ocorrencia",
                    pk=ocorrencia.pk,
                )

        messages.error(
            request,
            "Verifique os campos informados."
        )

    context = {
        "form": form,
        "pessoas_formset": pessoas_formset,
        "veiculos_formset": veiculos_formset,
        "ocorrencia": ocorrencia,
        "titulo": "Editar Ocorrência",
        "modo_edicao": True,
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

    ocorrencia = get_object_or_404(
        Ocorrencia.objects.select_related(
            "viatura",
            "viatura__plantao",
        ),
        pk=pk,
    )

    verificar_permissao(
        pode_excluir_ocorrencia(
            request,
            ocorrencia,
            usuario,
        )
    )

    if request.method == "POST":

        with transaction.atomic():
            ocorrencia.delete()

        messages.success(
            request,
            "Ocorrência excluída com sucesso!"
        )

        return redirect(
            "ocorrencias:listar_ocorrencias"
        )

    return render(
        request,
        "ocorrencias/confirmar_exclusao.html",
        {
            "ocorrencia": ocorrencia,
        },
    )
