
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_POST

from cartao_programa.models import (
    EfetivoViatura,
    MissaoCartao,
    ViaturaPlantao,
)
from usuarios.models import Usuario

from .forms import (
    RondaVisitaForm,
    dados_da_missao,
    obter_codigo_equipe_viatura,
)
from .models import RondaVisita
from .permissoes import (
    pode_editar_visita,
    pode_excluir_visita,
    cartoes_disponiveis,
)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def obter_usuario_recom(request):
    """Identifica o usuário autenticado no RECOM."""

    if (
        not request.user.is_authenticated
        or not request.user.is_active
    ):
        raise PermissionDenied(
            "É necessário estar autenticado e ativo."
        )

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True,
    ).first()

    if usuario is None:
        if request.user.is_superuser:
            return None

        raise PermissionDenied(
            "Usuário RECOM não encontrado ou inativo."
        )

    return usuario


# =========================================================
# PERMISSÃO DE GESTÃO
# =========================================================

def pode_gerenciar_visitas(request):
    """ADMIN e COORDENADOR gerenciam todas as visitas."""

    usuario = obter_usuario_recom(request)

    return (
        request.user.is_superuser
        or (
            usuario is not None
            and usuario.perfil in ("ADMIN", "COORDENADOR")
        )
    )


# =========================================================
# VALIDAR CADASTRO
# =========================================================

def validar_cadastro_visita(request):

    if pode_gerenciar_visitas(request):
        return

    usuario = obter_usuario_recom(request)

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para registrar visitas."
        )


# =========================================================
# VALIDAR ACESSO À MISSÃO
# =========================================================

def validar_acesso_missao(request, missao):
    """
    C, P1 e P2 podem registrar visitas programadas.
    M não pode registrar novas visitas programadas.
    ADMIN e COORDENADOR possuem acesso integral.
    """

    if missao.cartao.plantao_id != missao.viatura.plantao_id:
        raise PermissionDenied(
            "A missão não corresponde ao plantão da viatura."
        )

    if pode_gerenciar_visitas(request):
        return

    usuario = obter_usuario_recom(request)

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para registrar "
            "visitas nesta missão."
        )

    escala = EfetivoViatura.objects.filter(
        viatura_id=missao.viatura_id,
        gcm=usuario,
    ).first()

    if escala is None:
        raise PermissionDenied(
            "Esta missão não pertence à sua escala."
        )

    if escala.funcao not in ("C", "P1", "P2"):
        raise PermissionDenied(
            "Sua função na viatura não permite "
            "registrar visitas nesta missão."
        )


# =========================================================
# OBTER MISSÃO AUTORIZADA
# =========================================================

def obter_missao_autorizada(request, missao_id):

    missao = get_object_or_404(
        MissaoCartao.objects.select_related(
            "escola",
            "viatura",
            "viatura__plantao",
            "viatura__equipe",
            "cartao__plantao",
        ),
        pk=missao_id,
    )

    validar_acesso_missao(request, missao)

    if missao.escola_id is None:
        raise PermissionDenied(
            "Esta missão não possui escola vinculada."
        )

    return missao


# =========================================================
# VALIDAR EDIÇÃO
# =========================================================

def validar_edicao_visita(request, visita):

    if not pode_editar_visita(request, visita):
        raise PermissionDenied(
            "Você não possui permissão para editar esta visita."
        )


# =========================================================
# VALIDAR EXCLUSÃO
# =========================================================

def validar_exclusao_visita(request, visita):

    if not pode_excluir_visita(request, visita):
        raise PermissionDenied(
            "Você não possui permissão para excluir esta visita."
        )


# =========================================================
# IDENTIFICAR CARTÃO DA VISITA AVULSA
# =========================================================

def definir_cartao_visita_avulsa(request, visita, usuario):
    """
    Vincula a visita ao Cartão Programa autorizado.

    Sem escala, permite visita avulsa sem cartão.
    A viatura não define o compartilhamento.
    """

    visita.viatura = None

    cartoes = cartoes_disponiveis(
        request.user
    ).filter(
        plantao__data=visita.data_visita
    )

    if visita.cartao_programa_id:

        if not cartoes.filter(
            pk=visita.cartao_programa_id
        ).exists():
            raise ValidationError(
                "O Cartão Programa informado não está "
                "disponível para sua escala nesta data."
            )

        return

    if pode_gerenciar_visitas(request):
        return

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para registrar visitas."
        )

    opcoes = list(
        cartoes.order_by("pk")[:2]
    )

    if len(opcoes) == 1:
        visita.cartao_programa = opcoes[0]
        return

    if len(opcoes) > 1:
        raise ValidationError(
            "Selecione o Cartão Programa "
            "correspondente à sua escala nesta data."
        )

    visita.cartao_programa = None


# =========================================================
# ADICIONAR ERROS DO MODELO
# =========================================================

def adicionar_erros_modelo(form, erro):

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():
            form.add_error(
                campo if campo in form.fields else None,
                erros,
            )

    else:
        form.add_error(None, erro)


# =========================================================
# REDIRECIONAR APÓS CADASTRO OU EDIÇÃO
# =========================================================

def redirecionar_apos_visita(request, visita):

    usuario = obter_usuario_recom(request)

    if (
        visita.missao_cartao_id
        and usuario is not None
        and usuario.perfil == "GCM"
    ):
        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    return redirect(
        "escolas:detalhe_escola",
        pk=visita.escola_id,
    )


# =========================================================
# CADASTRAR VISITA
# =========================================================

@login_required
def cadastrar_visita(request):

    usuario = obter_usuario_recom(request)

    validar_cadastro_visita(request)

    missao_id = (
        request.POST.get("missao_cartao_id", "").strip()
        if request.method == "POST"
        else request.GET.get("missao", "").strip()
    )

    missao = (
        obter_missao_autorizada(request, missao_id)
        if missao_id
        else None
    )

    if missao is not None and (
        missao.status_execucao != "PENDENTE"
        or RondaVisita.objects.filter(
            missao_cartao_id=missao.pk
        ).exists()
    ):

        messages.warning(
            request,
            "Esta missão já possui um resultado registrado."
        )

        if pode_gerenciar_visitas(request):
            return redirect(
                "escolas:detalhe_escola",
                pk=missao.escola_id,
            )

        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            missao=missao,
            usuario_logado=request.user,
        )

        if form.is_valid():

            try:
                with transaction.atomic():

                    if missao is not None:

                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(),
                            pk=missao.pk,
                        )

                        validar_acesso_missao(request, missao)

                        if missao.status_execucao != "PENDENTE":
                            raise ValidationError(
                                "Esta missão já possui "
                                "um resultado registrado."
                            )

                        if RondaVisita.objects.filter(
                            missao_cartao_id=missao.pk
                        ).exists():
                            raise ValidationError(
                                "Já existe uma visita "
                                "registrada para esta missão."
                            )

                    visita = form.save(commit=False)

                    visita.missao_cartao = missao
                    visita.registrado_por = usuario

                    if missao is not None:

                        visita.cartao_programa = missao.cartao

                        for campo, valor in dados_da_missao(
                            missao
                        ).items():
                            setattr(visita, campo, valor)

                    else:

                        definir_cartao_visita_avulsa(
                            request,
                            visita,
                            usuario,
                        )

                    visita.full_clean()
                    visita.save()

                    if missao is not None:

                        missao.status_execucao = "REALIZADA"
                        missao.motivo_nao_realizacao = ""
                        missao.registrado_por = usuario
                        missao.atualizado_execucao_em = timezone.now()

                        missao.save(
                            update_fields=[
                                "status_execucao",
                                "motivo_nao_realizacao",
                                "registrado_por",
                                "atualizado_execucao_em",
                            ]
                        )

            except ValidationError as erro:
                adicionar_erros_modelo(form, erro)

            except IntegrityError:
                form.add_error(
                    None,
                    "Não foi possível registrar a visita. "
                    "Verifique se existe um registro duplicado "
                    "ou um conflito de dados."
                )

            else:
                messages.success(
                    request,
                    "Visita registrada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    visita,
                )

    else:

        initial = {}

        if missao is not None:

            initial["escola"] = missao.escola_id
            initial["data_visita"] = missao.cartao.plantao.data
            initial["cartao_programa"] = missao.cartao_id

        else:

            initial["data_visita"] = timezone.localdate()

            if request.GET.get("escola"):
                initial["escola"] = request.GET["escola"]

            if (
                usuario is not None
                and usuario.perfil == "GCM"
                and not request.user.is_superuser
            ):

                cartoes = list(
                    cartoes_disponiveis(
                        request.user
                    ).filter(
                        plantao__data=timezone.localdate()
                    ).order_by("pk")[:2]
                )

                if len(cartoes) == 1:
                    initial["cartao_programa"] = cartoes[0].pk

        form = RondaVisitaForm(
            initial=initial,
            missao=missao,
            usuario_logado=request.user,
        )

    contexto = {
        "form": form,
        "modo_edicao": False,
        "missao_cartao": missao,
        "missao_cartao_id": (
            missao.pk if missao is not None else None
        ),
        "usuario": usuario,
    }

    return render(
        request,
        "visitas/form_visita.html",
        contexto,
    )


# =========================================================
# EDITAR VISITA
# =========================================================

@login_required
def editar_visita(request, pk):

    usuario = obter_usuario_recom(request)

    visita = get_object_or_404(
        RondaVisita.objects.select_related(
            "escola",
            "registrado_por",
            "cartao_programa__plantao",
            "missao_cartao",
            "missao_cartao__viatura__plantao",
            "missao_cartao__cartao__plantao",
        ),
        pk=pk,
    )

    validar_edicao_visita(request, visita)

    missao = visita.missao_cartao

    missao_original_id = visita.missao_cartao_id
    cartao_original_id = visita.cartao_programa_id
    autor_original_id = visita.registrado_por_id

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            instance=visita,
            missao=missao,
            usuario_logado=request.user,
        )

        campos_ausentes = [
            campo
            for campo in ("relato", "orientacoes")
            if campo not in request.POST
        ]

        formulario_valido = form.is_valid()

        if campos_ausentes:

            form.add_error(
                None,
                "Não foi possível salvar: o formulário "
                "não enviou os campos Relato e/ou Providências. "
                "Atualize a página e tente novamente.",
            )

            formulario_valido = False

        if formulario_valido:

            try:
                with transaction.atomic():

                    missao = None

                    if missao_original_id is not None:

                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(),
                            pk=missao_original_id,
                        )

                    visita = get_object_or_404(
                        RondaVisita.objects.select_for_update(),
                        pk=pk,
                    )

                    validar_edicao_visita(request, visita)

                    if (
                        visita.missao_cartao_id != missao_original_id
                        or visita.cartao_programa_id != cartao_original_id
                        or visita.registrado_por_id != autor_original_id
                    ):
                        raise ValidationError(
                            "Os vínculos da visita foram alterados. "
                            "Atualize a página e tente novamente."
                        )

                    if (
                        missao is not None
                        and missao.status_execucao == "NAO_REALIZADA"
                    ):
                        raise ValidationError(
                            "Esta missão está marcada "
                            "como não realizada."
                        )

                    for campo in form._meta.fields:

                        if campo in (
                            "cartao_programa",
                            "viatura",
                        ):
                            continue

                        if (
                            cartao_original_id is not None
                            and campo in ("data_visita", "equipe")
                        ):
                            continue

                        if campo in form.cleaned_data:
                            setattr(
                                visita,
                                campo,
                                form.cleaned_data[campo],
                            )

                    form.instance = visita
                    atualizada = form.save(commit=False)

                    atualizada.missao_cartao = missao
                    atualizada.cartao_programa_id = cartao_original_id
                    atualizada.registrado_por_id = autor_original_id

                    if missao is not None:

                        atualizada.cartao_programa = missao.cartao

                        for campo, valor in dados_da_missao(
                            missao
                        ).items():
                            setattr(atualizada, campo, valor)

                    else:
                        atualizada.viatura = None

                    atualizada.full_clean()
                    atualizada.save()

                    if (
                        missao is not None
                        and missao.status_execucao != "REALIZADA"
                    ):

                        missao.status_execucao = "REALIZADA"
                        missao.motivo_nao_realizacao = ""

                        missao.save(
                            update_fields=[
                                "status_execucao",
                                "motivo_nao_realizacao",
                            ]
                        )

            except ValidationError as erro:
                adicionar_erros_modelo(form, erro)

            except IntegrityError:
                form.add_error(
                    None,
                    "Não foi possível salvar a visita "
                    "devido a um conflito de dados."
                )

            else:

                messages.success(
                    request,
                    "Visita atualizada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    atualizada,
                )

    else:

        form = RondaVisitaForm(
            instance=visita,
            missao=missao,
            usuario_logado=request.user,
        )

    contexto = {
        "form": form,
        "visita": visita,
        "modo_edicao": True,
        "missao_cartao": missao,
        "missao_cartao_id": (
            missao.pk if missao is not None else None
        ),
        "usuario": usuario,
    }

    return render(
        request,
        "visitas/form_visita.html",
        contexto,
    )


# =========================================================
# EXCLUIR VISITA
# REDIRECIONAMENTO CONFORME A ORIGEM
# =========================================================

@login_required
@require_POST
def excluir_visita(request, pk):
    """
    Exclui a visita respeitando as permissões.

    Se a exclusão for iniciada no Histórico de Atividades,
    retorna ao histórico com os filtros anteriores.

    Nos demais casos, retorna à página da escola.

    Ao excluir visita programada, a missão volta
    para o status PENDENTE.
    """

    obter_usuario_recom(request)

    referencia = get_object_or_404(
        RondaVisita,
        pk=pk,
    )

    validar_exclusao_visita(request, referencia)

    missao_id = referencia.missao_cartao_id

    # Identificar a origem antes da exclusão.
    origem = request.POST.get("origem", "").strip()

    with transaction.atomic():

        missao = None

        if missao_id is not None:
            missao = get_object_or_404(
                MissaoCartao.objects.select_for_update(),
                pk=missao_id,
            )

        visita = get_object_or_404(
            RondaVisita.objects.select_for_update(),
            pk=pk,
        )

        if visita.missao_cartao_id != missao_id:
            raise PermissionDenied(
                "O vínculo da visita foi alterado. "
                "Atualize a página."
            )

        validar_exclusao_visita(request, visita)

        escola_id = visita.escola_id

        visita.delete()

        if missao is not None:

            existe_outra_visita = (
                RondaVisita.objects.filter(
                    missao_cartao_id=missao.pk
                ).exists()
            )

            if not existe_outra_visita:

                missao.status_execucao = "PENDENTE"
                missao.motivo_nao_realizacao = ""
                missao.registrado_por = None
                missao.atualizado_execucao_em = None

                missao.save(
                    update_fields=[
                        "status_execucao",
                        "motivo_nao_realizacao",
                        "registrado_por",
                        "atualizado_execucao_em",
                    ]
                )

    messages.success(
        request,
        "Visita excluída com sucesso."
    )

    # Retornar ao Histórico de Atividades.
    if origem == "historico":

        url = reverse("core:historico_atividades")

        campos_permitidos = (
            "data_inicio",
            "data_fim",
            "equipe",
            "viatura",
            "tipo",
            "page",
        )

        parametros = {
            campo: request.POST.get(campo, "")
            for campo in campos_permitidos
            if request.POST.get(campo)
        }

        if parametros:
            url = f"{url}?{urlencode(parametros)}"

        return redirect(url)

    # Comportamento original para outras páginas.
    return redirect(
        "escolas:detalhe_escola",
        pk=escola_id,
    )


# =========================================================
# LISTAR VISITAS - ADMIN E COORDENADOR
# =========================================================

@login_required
def listar_visitas(request):

    usuario = obter_usuario_recom(request)

    if not pode_gerenciar_visitas(request):
        raise PermissionDenied(
            "Você não possui permissão para acessar "
            "a gestão de visitas."
        )

    visitas = RondaVisita.objects.select_related(
        "escola",
        "registrado_por",
        "cartao_programa__plantao",
        "missao_cartao",
    ).order_by(
        "-data_visita",
        "-horario",
        "-pk",
    )

    busca = request.GET.get("busca", "").strip()
    equipe = request.GET.get("equipe", "").strip()
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()

    if busca:
        visitas = visitas.filter(
            Q(escola__nome__icontains=busca)
            | Q(relato__icontains=busca)
        )

    if equipe:
        visitas = visitas.filter(equipe=equipe)

    try:
        inicio = (
            date.fromisoformat(data_inicio)
            if data_inicio else None
        )
    except ValueError:
        inicio = None
        messages.warning(request, "Data inicial inválida.")

    try:
        fim = (
            date.fromisoformat(data_fim)
            if data_fim else None
        )
    except ValueError:
        fim = None
        messages.warning(request, "Data final inválida.")

    if inicio:
        visitas = visitas.filter(data_visita__gte=inicio)

    if fim:
        visitas = visitas.filter(data_visita__lte=fim)

    paginator = Paginator(visitas, 15)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    contexto = {
        "page_obj": page_obj,
        "usuario": usuario,
        "busca": busca,
        "equipe_selecionada": equipe,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    return render(
        request,
        "visitas/listar_visitas.html",
        contexto,
    )


# =========================================================
# CONSULTAR CARTÕES PROGRAMA DISPONÍVEIS
# =========================================================

@login_required
@require_GET
def consultar_cartoes_visita(request):

    obter_usuario_recom(request)
    validar_cadastro_visita(request)

    data_informada = request.GET.get(
        "data", ""
    ).strip()

    if not data_informada:
        return JsonResponse({
            "cartoes": [],
            "mensagem": "Informe a data da visita.",
        })

    try:
        data_visita = date.fromisoformat(
            data_informada
        )
    except ValueError:
        return JsonResponse(
            {
                "cartoes": [],
                "mensagem": "Data inválida.",
            },
            status=400,
        )

    cartoes = cartoes_disponiveis(
        request.user
    ).filter(
        plantao__data=data_visita
    ).order_by("pk")

    resultado = []

    for cartao in cartoes:
        resultado.append({
            "id": cartao.pk,
            "data": cartao.plantao.data.isoformat(),
            "tipo_servico": cartao.plantao.tipo_servico,
            "descricao": (
                f"CP {cartao.pk} - "
                f"{cartao.plantao.data:%d/%m/%Y} - "
                f"{cartao.plantao.get_tipo_servico_display()}"
            ),
        })

    return JsonResponse({
        "cartoes": resultado,
        "mensagem": (
            ""
            if resultado
            else "Nenhum Cartão Programa disponível nesta data. "
                 "Você poderá registrar a visita avulsa "
                 "sem vínculo com um cartão."
        ),
    })


# =========================================================
# CONSULTAR VIATURAS
# COMPATIBILIDADE COM ROTAS EXISTENTES
# =========================================================

@login_required
@require_GET
def consultar_viaturas_visita(request):

    usuario = obter_usuario_recom(request)
    validar_cadastro_visita(request)

    data_informada = request.GET.get(
        "data", ""
    ).strip()

    if not data_informada:
        return JsonResponse({
            "viaturas": [],
            "mensagem": "Informe a data da visita.",
        })

    try:
        data_visita = date.fromisoformat(
            data_informada
        )
    except ValueError:
        return JsonResponse(
            {
                "viaturas": [],
                "mensagem": "Data inválida.",
            },
            status=400,
        )

    viaturas = ViaturaPlantao.objects.select_related(
        "plantao",
        "equipe",
    ).filter(
        plantao__data=data_visita
    )

    if not pode_gerenciar_visitas(request):

        if usuario is None or usuario.perfil != "GCM":
            raise PermissionDenied(
                "Você não possui permissão "
                "para consultar essas viaturas."
            )

        viaturas = viaturas.filter(
            efetivo__gcm=usuario,
        )

    viaturas = viaturas.distinct().order_by(
        "identificacao",
        "pk",
    )

    resultado = []

    for viatura in viaturas:

        try:
            codigo_equipe = obter_codigo_equipe_viatura(
                viatura
            )
        except ValidationError:
            continue

        nome_equipe = (
            viatura.equipe.nome
            if viatura.equipe_id
            else "Equipe extraordinária"
        )

        resultado.append({
            "id": viatura.pk,
            "identificacao": viatura.identificacao,
            "equipe": codigo_equipe,
            "nome_equipe": nome_equipe,
        })

    return JsonResponse({
        "viaturas": resultado,
        "mensagem": (
            ""
            if resultado
            else "Nenhuma viatura disponível "
                 "para sua escala nesta data."
        ),
    })
