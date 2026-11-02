from functools import wraps

from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField, Prefetch
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from visitas.models import RondaVisita
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST

from usuarios.models import Usuario
from .models import (
    Equipe, IntegranteEquipe, Plantao, ViaturaPlantao,
    EfetivoViatura, CartaoPrograma, MissaoCartao,
)
from .forms import (
    EquipeForm, IntegranteEquipeForm, PlantaoForm,
    ViaturaPlantaoForm, EfetivoViaturaForm,
    CartaoProgramaForm, MissaoCartaoForm, MissoesEmLoteForm,
)

# =====================================================

# CONTROLE DE ACESSO - GESTÃO DO CARTÃO PROGRAMA

# =====================================================

def acesso_gestao_equipes(view_func):

    @wraps(view_func)

    @login_required

    def wrapper(request, *args, **kwargs):

        # Superusuários ativos do Django possuem acesso.

        if (

            request.user.is_active

            and request.user.is_superuser

        ):

            return view_func(request, *args, **kwargs)

        # Verifica o perfil do usuário no RECOM.

        usuario = getattr(

            request.user,

            "usuario",

            None

        )

        if (

            not request.user.is_active

            or not usuario

            or not usuario.ativo

            or usuario.perfil not in [

                "ADMIN",

                "COORDENADOR"

            ]

        ):

            raise PermissionDenied(

                "Você não possui permissão "

                "para gerenciar equipes e plantões."

            )

        return view_func(request, *args, **kwargs)

    return wrapper

# =====================================================

# LISTAR EQUIPES

# =====================================================

def fluxo_cartao_ativo(request):
    return request.GET.get("fluxo") == "cartao"


def redirecionar_fluxo(request, rota, **kwargs):
    resposta = redirect(rota, **kwargs)
    if fluxo_cartao_ativo(request):
        resposta["Location"] += ("&" if "?" in resposta["Location"] else "?") + "fluxo=cartao"
    return resposta


@acesso_gestao_equipes
def listar_equipes(request):

    equipes = (

        Equipe.objects.all()

        .order_by("nome")

    )

    return render(

        request,

        "cartao_programa/equipes/listar.html",

        {

            "equipes": equipes

        }

    )

# =====================================================

# CADASTRAR EQUIPE

# =====================================================

@acesso_gestao_equipes

def criar_equipe(request):

    if request.method == "POST":

        form = EquipeForm(

            request.POST

        )

        if form.is_valid():

            form.save()

            messages.success(

                request,

                "Equipe cadastrada com sucesso!"

            )

            return redirect(

                "cartao_programa:listar_equipes"

            )

    else:

        form = EquipeForm()

    return render(

        request,

        "cartao_programa/equipes/form.html",

        {

            "form": form,

            "titulo": "Cadastrar Equipe"

        }

    )

# =====================================================

# EDITAR EQUIPE

# =====================================================

@acesso_gestao_equipes

def editar_equipe(request, pk):

    equipe = get_object_or_404(

        Equipe,

        pk=pk

    )

    if request.method == "POST":

        form = EquipeForm(

            request.POST,

            instance=equipe

        )

        if form.is_valid():

            form.save()

            messages.success(

                request,

                "Equipe atualizada com sucesso!"

            )

            return redirect(

                "cartao_programa:listar_equipes"

            )

    else:

        form = EquipeForm(

            instance=equipe

        )

    return render(

        request,

        "cartao_programa/equipes/form.html",

        {

            "form": form,

            "titulo": "Editar Equipe"

        }

    )

# =====================================================

# LISTAR INTEGRANTES DE UMA EQUIPE

# =====================================================

@acesso_gestao_equipes

def listar_integrantes(request, equipe_id):

    equipe = get_object_or_404(

        Equipe,

        pk=equipe_id

    )

    integrantes = (

        IntegranteEquipe.objects

        .filter(equipe=equipe)

        .select_related("gcm")

        .order_by("gcm__nome")

    )

    return render(

        request,

        "cartao_programa/equipes/integrantes.html",

        {

            "equipe": equipe,

            "integrantes": integrantes

        }

    )

# =====================================================

# ADICIONAR GCM A UMA EQUIPE

# =====================================================

@acesso_gestao_equipes

def adicionar_integrante(request, equipe_id):

    equipe = get_object_or_404(

        Equipe,

        pk=equipe_id,

        ativa=True

    )

    if request.method == "POST":

        form = IntegranteEquipeForm(

            request.POST

        )

    else:

        form = IntegranteEquipeForm()

    # A equipe é determinada pela URL.

    form.fields["equipe"].initial = equipe.pk

    form.fields["equipe"].disabled = True

    if (

        request.method == "POST"

        and form.is_valid()

    ):

        integrante = form.save(

            commit=False

        )

        integrante.equipe = equipe

        integrante.save()

        messages.success(

            request,

            "GCM vinculado à equipe com sucesso!"

        )

        return redirect(

            "cartao_programa:listar_integrantes",

            equipe_id=equipe.pk

        )

    return render(

        request,

        "cartao_programa/equipes/form_integrante.html",

        {

            "form": form,

            "equipe": equipe,

            "titulo": "Adicionar GCM",

            "edicao": False

        }

    )

# =====================================================

# EDITAR FUNÇÃO HABITUAL DO INTEGRANTE

# =====================================================

@acesso_gestao_equipes

def editar_integrante(request, equipe_id, pk):

    equipe = get_object_or_404(

        Equipe,

        pk=equipe_id

    )

    integrante = get_object_or_404(

        IntegranteEquipe,

        pk=pk,

        equipe=equipe

    )

    if request.method == "POST":

        form = IntegranteEquipeForm(

            request.POST,

            instance=integrante

        )

    else:

        form = IntegranteEquipeForm(

            instance=integrante

        )

    # Somente a função habitual pode ser alterada.

    form.fields["equipe"].disabled = True

    form.fields["gcm"].disabled = True

    if (

        request.method == "POST"

        and form.is_valid()

    ):

        form.save()

        messages.success(

            request,

            "Função habitual do GCM "

            "atualizada com sucesso!"

        )

        return redirect(

            "cartao_programa:listar_integrantes",

            equipe_id=equipe.pk

        )

    return render(

        request,

        "cartao_programa/equipes/form_integrante.html",

        {

            "form": form,

            "equipe": equipe,

            "integrante": integrante,

            "titulo": "Editar Integrante",

            "edicao": True

        }

    )

# =====================================================

# REMOVER INTEGRANTE DA EQUIPE FIXA

# =====================================================

@acesso_gestao_equipes

def remover_integrante(request, equipe_id, pk):

    equipe = get_object_or_404(

        Equipe,

        pk=equipe_id

    )

    integrante = get_object_or_404(

        IntegranteEquipe.objects.select_related("gcm"),

        pk=pk,

        equipe=equipe

    )

    # A remoção somente acontece após confirmação.

    if request.method == "POST":

        nome_gcm = integrante.gcm.nome

        # Remove apenas o vínculo com a equipe.

        integrante.delete()

        messages.success(

            request,

            f"O GCM {nome_gcm} foi removido "

            "da equipe com sucesso!"

        )

        return redirect(

            "cartao_programa:listar_integrantes",

            equipe_id=equipe.pk

        )

    return render(

        request,

        "cartao_programa/equipes/confirmar_remocao_integrante.html",

        {

            "equipe": equipe,

            "integrante": integrante

        }

    )

# =====================================================

# LISTAR PLANTÕES

# =====================================================

@acesso_gestao_equipes

def listar_plantoes(request):

    plantoes = (

        Plantao.objects.all()

        .order_by("-data", "-pk")

    )

    return render(

        request,

        "cartao_programa/plantoes/listar.html",

        {

            "plantoes": plantoes,
            "fluxo_cartao": fluxo_cartao_ativo(request)

        }

    )

# =====================================================

# CADASTRAR PLANTÃO

# =====================================================

@acesso_gestao_equipes

def criar_plantao(request):

    if request.method == "POST":

        form = PlantaoForm(

            request.POST

        )

        if form.is_valid():

            plantao = form.save()
            messages.success(request, "Plantão cadastrado com sucesso!")
            if fluxo_cartao_ativo(request):
                return redirecionar_fluxo(request, "cartao_programa:listar_viaturas", plantao_id=plantao.pk)
            return redirect("cartao_programa:listar_plantoes")

    else:

        form = PlantaoForm()

    return render(

        request,

        "cartao_programa/plantoes/form.html",

        {

            "form": form,

            "titulo": "Cadastrar Plantão",
            "fluxo_cartao": fluxo_cartao_ativo(request)

        }

    )

# =====================================================

# LISTAR VIATURAS DE UM PLANTÃO

# =====================================================

@acesso_gestao_equipes

def listar_viaturas(request, plantao_id):

    plantao = get_object_or_404(

        Plantao,

        pk=plantao_id

    )

    viaturas = (

        ViaturaPlantao.objects

        .filter(plantao=plantao)

        .select_related("equipe")

        .order_by("identificacao")

    )

    return render(

        request,

        "cartao_programa/viaturas/listar.html",

        {

            "plantao": plantao,

            "viaturas": viaturas,
            "fluxo_cartao": fluxo_cartao_ativo(request),
        }

    )

# =====================================================

# FUNÇÃO AUXILIAR - EXIBIR ERROS DO MODELO

# =====================================================

def adicionar_erros_validacao(form, erro):

    # Converte erros do full_clean() em erros

    # exibidos no próprio formulário.

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():

            # Erros gerais do modelo.

            if campo == "__all__":

                form.add_error(None, erros)

            # Erros de campos presentes no formulário.

            elif campo in form.fields:

                form.add_error(campo, erros)

            # Erros de campos não exibidos no formulário.

            else:

                form.add_error(None, erros)

    else:

        form.add_error(None, erro)

# =====================================================
# PREENCHIMENTO AUTOMÁTICO DO EFETIVO
# =====================================================


def preencher_efetivo_automaticamente(viatura):
    """Adiciona integrantes da equipe selecionada, sem duplicar escalas.

    Funciona para ordinário e extraordinário. Não modifica integrantes
    existentes e devolve avisos para quem não pôde ser incluído.
    """
    if not viatura.equipe_id:
        return 0, []

    integrantes = list(
        IntegranteEquipe.objects.filter(
            equipe_id=viatura.equipe_id,
            gcm__perfil="GCM",
            gcm__ativo=True,
        ).select_related("gcm").order_by("gcm__nome")
    )
    if not integrantes:
        return 0, ["A equipe selecionada não possui GCMs ativos cadastrados."]

    quantidade = 0
    pendentes = []
    for integrante in integrantes:
        # Não incluir o mesmo GCM duas vezes no mesmo dia, inclusive
        # quando há mais de um plantão nessa data.
        ja_escalado = EfetivoViatura.objects.filter(
            gcm_id=integrante.gcm_id,
            viatura__plantao__data=viatura.plantao.data,
        ).exists()
        if ja_escalado:
            # Integrante já incluído nesta própria viatura não é pendência.
            if not EfetivoViatura.objects.filter(
                viatura=viatura, gcm_id=integrante.gcm_id
            ).exists():
                pendentes.append(f"{integrante.gcm.nome}: já escalado nesta data.")
            continue

        funcao_ocupada = EfetivoViatura.objects.filter(
            viatura=viatura,
            funcao=integrante.funcao_habitual,
        ).exists()
        if funcao_ocupada:
            pendentes.append(
                f"{integrante.gcm.nome}: função "
                f"{integrante.funcao_habitual} já ocupada nesta viatura."
            )
            continue

        efetivo = EfetivoViatura(
            viatura=viatura,
            gcm=integrante.gcm,
            funcao=integrante.funcao_habitual,
        )
        efetivo.full_clean()
        efetivo.save()
        quantidade += 1

    return quantidade, pendentes

def validar_equipe_extraordinaria(viatura):
    """Impede usar no extraordinário a equipe do ordinário da mesma data."""
    if viatura.tipo_servico != "EXTRAORDINARIO" or not viatura.equipe_id:
        return
    if ViaturaPlantao.objects.filter(
        plantao__data=viatura.plantao.data,
        tipo_servico="ORDINARIO",
        equipe_id=viatura.equipe_id,
    ).exclude(pk=viatura.pk).exists():
        raise ValidationError({
            "equipe": "Esta equipe já está responsável pelo serviço ordinário "
                      "nesta data. Selecione outra equipe para o extraordinário."
        })


# =====================================================
# CADASTRAR VIATURA EM UM PLANTÃO
# =====================================================

@acesso_gestao_equipes
def criar_viatura(request, plantao_id):
    plantao = get_object_or_404(Plantao, pk=plantao_id)
    form = ViaturaPlantaoForm(
        request.POST if request.method == "POST" else None,
        plantao=plantao,
    )

    if request.method == "POST" and form.is_valid():
        viatura = form.save(commit=False)
        viatura.plantao = plantao
        try:
            with transaction.atomic():
                # A validação de equipe única por data fica no modelo.
                viatura.full_clean()
                validar_equipe_extraordinaria(viatura)
                viatura.save()
                quantidade, pendentes = preencher_efetivo_automaticamente(viatura)
        except ValidationError as erro:
            adicionar_erros_validacao(form, erro)
        else:
            messages.success(request, "Viatura cadastrada com sucesso!")
            if pendentes:
                messages.warning(
                    request,
                    "Confira os integrantes não incluídos automaticamente: "
                    + " ".join(pendentes),
                )
            if fluxo_cartao_ativo(request):
                return redirecionar_fluxo(
                    request, "cartao_programa:listar_efetivo",
                    plantao_id=plantao.pk, viatura_id=viatura.pk,
                )
            return redirecionar_fluxo(
                request, "cartao_programa:listar_viaturas", plantao_id=plantao.pk
            )

    return render(request, "cartao_programa/viaturas/form.html", {
        "form": form,
        "plantao": plantao,
        "titulo": "Cadastrar Viatura",
        "fluxo_cartao": fluxo_cartao_ativo(request),
        "edicao": False,
    })

# =====================================================
# EDITAR VIATURA DE UM PLANTÃO
# =====================================================

@acesso_gestao_equipes
def editar_viatura(request, plantao_id, pk):
    plantao = get_object_or_404(Plantao, pk=plantao_id)
    viatura = get_object_or_404(ViaturaPlantao, pk=pk, plantao=plantao)

    # Guardar os valores antes de form.is_valid(), que altera a instância.
    equipe_anterior_id = viatura.equipe_id
    tipo_anterior = viatura.tipo_servico

    form = ViaturaPlantaoForm(
        request.POST if request.method == "POST" else None,
        instance=viatura, plantao=plantao,
    )
    if request.method == "POST" and form.is_valid():
        atualizada = form.save(commit=False)
        atualizada.plantao = plantao

        # Não manter o efetivo de uma equipe antiga como se fosse da nova.
        mudou_equipe = equipe_anterior_id != atualizada.equipe_id
        mudou_tipo = tipo_anterior != atualizada.tipo_servico
        if (mudou_equipe or mudou_tipo) and EfetivoViatura.objects.filter(
            viatura_id=atualizada.pk
        ).exists():
            form.add_error(
                "equipe" if mudou_equipe else "tipo_servico",
                "Esta viatura já possui GCMs escalados. Ajuste ou remova "
                "o efetivo antes de alterar a equipe ou o tipo de serviço.",
            )
        else:
            try:
                with transaction.atomic():
                    atualizada.full_clean()
                    validar_equipe_extraordinaria(atualizada)
                    atualizada.save()
                    quantidade, pendentes = preencher_efetivo_automaticamente(
                        atualizada
                    )
            except ValidationError as erro:
                adicionar_erros_validacao(form, erro)
            else:
                messages.success(request, "Viatura atualizada com sucesso!")
                if pendentes:
                    messages.warning(
                        request,
                        "Confira os integrantes não incluídos automaticamente: "
                        + " ".join(pendentes),
                    )
                return redirecionar_fluxo(
                    request, "cartao_programa:listar_viaturas",
                    plantao_id=plantao.pk,
                )

    return render(request, "cartao_programa/viaturas/form.html", {
        "form": form,
        "plantao": plantao,
        "viatura": viatura,
        "titulo": "Editar Viatura",
        "fluxo_cartao": fluxo_cartao_ativo(request),
        "edicao": True,
    })

# =====================================================

# EFETIVO DE CADA VIATURA

# =====================================================

@acesso_gestao_equipes

def listar_efetivo(request, plantao_id, viatura_id):

    viatura = get_object_or_404(

        ViaturaPlantao.objects.select_related("plantao", "equipe"),

        pk=viatura_id,

        plantao_id=plantao_id,

    )

    integrantes = (

        EfetivoViatura.objects.filter(viatura=viatura)

        .select_related("gcm")
        .annotate(
            ordem_funcao=Case(
                When(funcao="C", then=Value(1)),
                When(funcao="M", then=Value(2)),
                When(funcao="P1", then=Value(3)),
                When(funcao="P2", then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .order_by("ordem_funcao", "gcm__nome")

        

    )

    funcoes = set(integrantes.values_list("funcao", flat=True))

    return render(

        request,

        "cartao_programa/efetivo/listar.html",

        {

            "plantao": viatura.plantao,

            "viatura": viatura,

            "integrantes": integrantes,

            "pode_adicionar": integrantes.count() < 4,

            "possui_comandante": "C" in funcoes,

            "possui_motorista": "M" in funcoes,
            "fluxo_cartao": fluxo_cartao_ativo(request),

        },

    )

def _validar_e_salvar_efetivo(form, viatura):
    """Valida a escala manual, inclusive entre plantões da mesma data."""
    integrante = form.save(commit=False)
    integrante.viatura = viatura
    outros = EfetivoViatura.objects.filter(viatura=viatura).exclude(
        pk=integrante.pk
    )
    if outros.count() >= 4:
        form.add_error(None, "Esta viatura já possui quatro integrantes.")
        return False

    # A checagem anterior do formulário só considerava o mesmo plantão.
    # Esta impede escala repetida em plantões distintos da mesma data.
    if integrante.gcm_id and EfetivoViatura.objects.filter(
        gcm_id=integrante.gcm_id,
        viatura__plantao__data=viatura.plantao.data,
    ).exclude(pk=integrante.pk).exists():
        form.add_error("gcm", "Este GCM já está escalado em outra viatura nesta data.")
        return False

    try:
        integrante.full_clean()
    except ValidationError as erro:
        adicionar_erros_validacao(form, erro)
        return False
    integrante.save()
    return True

@acesso_gestao_equipes

def adicionar_efetivo(request, plantao_id, viatura_id):

    viatura = get_object_or_404(

        ViaturaPlantao.objects.select_related("plantao"),

        pk=viatura_id,

        plantao_id=plantao_id,

    )

    if request.method == "POST":

        form = EfetivoViaturaForm(request.POST, viatura=viatura)

        if form.is_valid() and _validar_e_salvar_efetivo(form, viatura):

            messages.success(request, "GCM incluído no efetivo da viatura!")

            return redirecionar_fluxo(

                request,

                "cartao_programa:listar_efetivo",

                plantao_id=plantao_id,

                viatura_id=viatura_id,

            )

    else:

        form = EfetivoViaturaForm(viatura=viatura)

    return render(

        request,

        "cartao_programa/efetivo/form.html",

        {

            "plantao": viatura.plantao,

            "viatura": viatura,

            "form": form,

            "titulo": "Adicionar GCM à Viatura",
            "fluxo_cartao": fluxo_cartao_ativo(request),

            "edicao": False,

        },

    )

@acesso_gestao_equipes

def editar_efetivo(request, plantao_id, viatura_id, pk):

    viatura = get_object_or_404(

        ViaturaPlantao.objects.select_related("plantao"),

        pk=viatura_id,

        plantao_id=plantao_id,

    )

    integrante = get_object_or_404(

        EfetivoViatura,

        pk=pk,

        viatura=viatura,

    )

    if request.method == "POST":

        form = EfetivoViaturaForm(

            request.POST, instance=integrante, viatura=viatura

        )

        if form.is_valid() and _validar_e_salvar_efetivo(form, viatura):

            messages.success(request, "Efetivo da viatura atualizado com sucesso!")

            return redirecionar_fluxo(

                request,

                "cartao_programa:listar_efetivo",

                plantao_id=plantao_id,

                viatura_id=viatura_id,

            )

    else:

        form = EfetivoViaturaForm(instance=integrante, viatura=viatura)

    return render(

        request,

        "cartao_programa/efetivo/form.html",

        {

            "plantao": viatura.plantao,

            "viatura": viatura,

            "integrante": integrante,

            "form": form,

            "titulo": "Editar GCM da Viatura",
            "fluxo_cartao": fluxo_cartao_ativo(request),

            "edicao": True,

        },

    )

@acesso_gestao_equipes

def remover_efetivo(request, plantao_id, viatura_id, pk):

    viatura = get_object_or_404(

        ViaturaPlantao.objects.select_related("plantao"),

        pk=viatura_id,

        plantao_id=plantao_id,

    )

    integrante = get_object_or_404(

        EfetivoViatura.objects.select_related("gcm"),

        pk=pk,

        viatura=viatura,

    )

    if request.method == "POST":

        nome = integrante.gcm.nome

        integrante.delete()  # Não exclui o cadastro nem a equipe fixa do GCM.

        messages.success(request, f"{nome} foi removido do efetivo da viatura.")

        return redirecionar_fluxo(

            request,

            "cartao_programa:listar_efetivo",

            plantao_id=plantao_id,

            viatura_id=viatura_id,

        )

    return render(

        request,

        "cartao_programa/efetivo/confirmar_remocao.html",

        {

            "plantao": viatura.plantao,

            "viatura": viatura,

            "integrante": integrante,

        "fluxo_cartao": fluxo_cartao_ativo(request),
        },

    )

# =====================================================

# CARTÃO PROGRAMA - VISUALIZAR

# =====================================================

def _coordenador_automatico(request):
    """Define responsável sem escolher arbitrariamente entre vários coordenadores."""
    usuario = getattr(request.user, "usuario", None)
    if usuario is not None and usuario.ativo and usuario.perfil == "COORDENADOR":
        return usuario

    coordenadores = Usuario.objects.filter(perfil="COORDENADOR", ativo=True)
    # Se houver somente um, a escolha é inequívoca.
    if coordenadores.count() == 1:
        return coordenadores.first()
    return None


def _garantir_cartao(request, plantao):
    """Retorna o cartão existente ou cria um único cartão automaticamente.

    Se o administrador tiver vários coordenadores disponíveis, a seleção
    explícita permanece necessária para não atribuir responsabilidade errada.
    """
    cartao = CartaoPrograma.objects.filter(plantao=plantao).first()
    if cartao is not None:
        return cartao

    coordenador = _coordenador_automatico(request)
    if coordenador is None:
        return None

    with transaction.atomic():
        cartao, criado = CartaoPrograma.objects.get_or_create(
            plantao=plantao,
            defaults={"coordenador": coordenador},
        )
    if criado:
        messages.success(request, "Cartão Programa criado automaticamente. Cadastre as missões.")
    return cartao



@acesso_gestao_equipes
def visualizar_cartao(request, plantao_id):

    plantao = get_object_or_404(
        Plantao,
        pk=plantao_id
    )

    cartao = (
        CartaoPrograma.objects
        .filter(plantao=plantao)
        .select_related("coordenador", "plantao")
        .first()
    )

    if fluxo_cartao_ativo(request):
        return redirecionar_fluxo(
            request,
            "cartao_programa:listar_missoes",
            plantao_id=plantao.pk
        )

    # ==========================================
    # ORDENAR EFETIVO: C, M, P1, P2
    # ==========================================

    efetivo_ordenado = (
        EfetivoViatura.objects
        .select_related("gcm")
        .annotate(
            ordem_funcao=Case(
                When(funcao="C", then=Value(1)),
                When(funcao="M", then=Value(2)),
                When(funcao="P1", then=Value(3)),
                When(funcao="P2", then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .order_by("ordem_funcao", "pk")
    )

    # ==========================================
    # VIATURAS DO PLANTÃO
    # ==========================================

    viaturas = (
        ViaturaPlantao.objects
        .filter(plantao=plantao)
        .select_related("equipe")
        .prefetch_related(
            Prefetch(
                "efetivo",
                queryset=efetivo_ordenado
            )
        )
        .order_by("identificacao")
    )

    # ==========================================
    # MISSÕES DO CARTÃO PROGRAMA
    # ==========================================

    missoes = (
        MissaoCartao.objects
        .filter(cartao=cartao)
        .select_related("viatura", "escola")
        .order_by("numero")
        if cartao is not None
        else MissaoCartao.objects.none()
    )

    # ==========================================
    # RENDERIZAÇÃO
    # ==========================================

    return render(
        request,
        "cartao_programa/cartoes/detalhe.html",
        {
            "plantao": plantao,
            "cartao": cartao,
            "viaturas": viaturas,
            "missoes": missoes,
            "fluxo_cartao": fluxo_cartao_ativo(request),
        }
    )


# =====================================================
# CARTÃO PROGRAMA - CRIAR
# =====================================================

@acesso_gestao_equipes
def criar_cartao(request, plantao_id):

    plantao = get_object_or_404(
        Plantao,
        pk=plantao_id
    )

    fluxo_cartao = fluxo_cartao_ativo(request)

    usuario = getattr(request.user, "usuario", None)

    if not request.user.is_active:
        raise PermissionDenied("Usuário inativo.")

    eh_admin = (
        request.user.is_superuser
        or request.user.is_staff
        or (
            usuario is not None
            and usuario.ativo
            and usuario.perfil == "ADMIN"
        )
    )

    eh_coordenador = (
        usuario is not None
        and usuario.ativo
        and usuario.perfil == "COORDENADOR"
    )

    if not (eh_admin or eh_coordenador):
        raise PermissionDenied(
            "Apenas administradores e coordenadores "
            "podem criar um Cartão Programa."
        )

    # Se o cartão já existe, não abrir
    # novamente o formulário de criação.
    cartao_existente = CartaoPrograma.objects.filter(
        plantao=plantao
    ).first()

    if cartao_existente:

        destino = (
            "cartao_programa:listar_missoes"
            if fluxo_cartao
            else "cartao_programa:visualizar_cartao"
        )

        return redirecionar_fluxo(
            request,
            destino,
            plantao_id=plantao.pk
        )

    coordenadores = Usuario.objects.filter(
        perfil="COORDENADOR",
        ativo=True
    ).order_by("nome")

    quantidade_coordenadores = coordenadores.count()

    # Coordenador logado tem prioridade.
    if eh_coordenador:
        coordenador_automatico = usuario

    # Um único coordenador ativo:
    # seleção automática.
    elif quantidade_coordenadores == 1:
        coordenador_automatico = coordenadores.first()

    else:
        coordenador_automatico = None

    selecionar_coordenador = (
        coordenador_automatico is None
        and quantidade_coordenadores > 1
    )

    form = CartaoProgramaForm(
        request.POST if request.method == "POST" else None,
        plantao=plantao
    )

    if selecionar_coordenador:
        form.fields["coordenador"] = django_forms.ModelChoiceField(
            queryset=coordenadores,
            label="Coordenador responsável",
            required=True,
            empty_label="Selecione um coordenador",
            widget=django_forms.Select(
                attrs={"class": "form-select"}
            )
        )

    # Criação automática quando existe
    # um coordenador definido.
    if (
        request.method == "GET"
        and fluxo_cartao
        and coordenador_automatico is not None
    ):
        cartao = CartaoPrograma(
            plantao=plantao,
            coordenador=coordenador_automatico
        )

        try:
            cartao.full_clean()
            cartao.save()

        except ValidationError as erro:
            adicionar_erros_validacao(form, erro)

        else:
            return redirecionar_fluxo(
                request,
                "cartao_programa:listar_missoes",
                plantao_id=plantao.pk
            )

    # Criação manual quando necessário.
    if request.method == "POST" and form.is_valid():

        cartao = form.save(commit=False)
        cartao.plantao = plantao

        if selecionar_coordenador:
            cartao.coordenador = form.cleaned_data["coordenador"]
        else:
            cartao.coordenador = coordenador_automatico

        if cartao.coordenador is None:
            form.add_error(
                None,
                "Não existe coordenador ativo disponível. "
                "Cadastre ou ative um coordenador."
            )

        else:
            try:
                cartao.full_clean()

            except ValidationError as erro:
                adicionar_erros_validacao(form, erro)

            else:
                cartao.save()

                messages.success(
                    request,
                    "Cartão Programa criado com sucesso!"
                )

                destino = (
                    "cartao_programa:listar_missoes"
                    if fluxo_cartao
                    else "cartao_programa:visualizar_cartao"
                )

                return redirecionar_fluxo(
                    request,
                    destino,
                    plantao_id=plantao.pk
                )

    return render(
        request,
        "cartao_programa/cartoes/form.html",
        {
            "plantao": plantao,
            "form": form,
            "coordenador": coordenador_automatico,
            "coordenadores_disponiveis": quantidade_coordenadores > 0,
            "selecionar_coordenador": selecionar_coordenador,
            "titulo": "Criar Cartão Programa",
            "fluxo_cartao": fluxo_cartao,
            "edicao": False,
        }
    )



# =====================================================
# CARTÃO PROGRAMA - EDITAR
# =====================================================

@acesso_gestao_equipes
def editar_cartao(request, plantao_id):

    plantao = get_object_or_404(Plantao, pk=plantao_id)

    cartao = get_object_or_404(
        CartaoPrograma.objects.select_related("coordenador"),
        plantao=plantao
    )

    form = CartaoProgramaForm(
        request.POST if request.method == "POST" else None,
        instance=cartao,
        plantao=plantao,
    )

    if request.method == "POST" and form.is_valid():

        atualizado = form.save(commit=False)

        atualizado.plantao = plantao

        # Preserva o coordenador originalmente responsável.
        # A edição não permite substituí-lo pelo formulário.
        atualizado.coordenador = cartao.coordenador

        try:
            atualizado.full_clean()

        except ValidationError as erro:
            adicionar_erros_validacao(form, erro)

        else:
            atualizado.save()

            messages.success(
                request,
                "Cartão Programa atualizado com sucesso!"
            )

            return redirecionar_fluxo(
                request,
                "cartao_programa:visualizar_cartao",
                plantao_id=plantao.pk
            )

    return render(
        request,
        "cartao_programa/cartoes/form.html",
        {
            "plantao": plantao,
            "cartao": cartao,
            "coordenador": cartao.coordenador,
            "form": form,
            "titulo": "Editar Cartão Programa",
            "fluxo_cartao": fluxo_cartao_ativo(request),
            "edicao": True,
        }
    )
# =========================================================
# EXCLUIR CARTÃO PROGRAMA
# PRESERVANDO AS VISITAS REGISTRADAS
# =========================================================


@login_required
@require_POST
def excluir_cartao(request, pk):

    # Somente administradores e coordenadores
    # podem excluir cartões.
    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True
    ).first()

    if not (
        request.user.is_superuser
        or (
            usuario is not None
            and usuario.perfil in ["ADMIN", "COORDENADOR"]
        )
    ):
        raise PermissionDenied(
            "Você não possui permissão para excluir "
            "Cartões Programa."
        )

    try:
        with transaction.atomic():

            cartao = get_object_or_404(
                CartaoPrograma.objects.select_for_update(),
                pk=pk
            )

            # As visitas vinculadas às missões serão
            # preservadas pelo SET_NULL do modelo
            # RondaVisita.
            cartao.delete()

    except ProtectedError:

        messages.error(
            request,
            "Não foi possível excluir o Cartão Programa "
            "porque existem registros protegidos vinculados."
        )

    else:

        messages.success(
            request,
            "Cartão Programa excluído com sucesso. "
            "As visitas já registradas foram preservadas."
        )

    return redirect(
        "cartao_programa:listar_cartoes"
    )


# =====================================================

# MISSÕES - LISTAR

# =====================================================

@acesso_gestao_equipes
def listar_missoes(request, plantao_id):
    plantao = get_object_or_404(Plantao, pk=plantao_id)
    cartao = _garantir_cartao(request, plantao) if fluxo_cartao_ativo(request) else (
        CartaoPrograma.objects.filter(plantao=plantao).first()
    )

    if cartao is None:
        # Quando há vários coordenadores, somente a escolha explícita
        # permite identificar o responsável correto.
        if fluxo_cartao_ativo(request):
            messages.warning(
                request,
                "Selecione o coordenador responsável para iniciar as missões. "
                "Isso é necessário somente quando há mais de um coordenador ativo "
                "ou nenhum coordenador identificado.",
            )
        else:
            messages.info(request, "Antes de cadastrar missões, crie o Cartão Programa deste plantão.")
        return redirecionar_fluxo(
            request, "cartao_programa:criar_cartao", plantao_id=plantao.pk
        )

    missoes = (
        MissaoCartao.objects.filter(cartao=cartao)
        .select_related("viatura", "escola")
        .order_by("numero")
    )
    return render(request, "cartao_programa/missoes/listar.html", {
        "plantao": plantao,
        "cartao": cartao,
        "missoes": missoes,
        "fluxo_cartao": fluxo_cartao_ativo(request),
    })

# =====================================================

# MISSÕES - CRIAR

# =====================================================

@acesso_gestao_equipes

def criar_missao(request, plantao_id):

    plantao = get_object_or_404(Plantao, pk=plantao_id)

    cartao = get_object_or_404(CartaoPrograma, plantao=plantao)

    form = MissaoCartaoForm(

        request.POST if request.method == "POST" else None,

        cartao=cartao,

    )

    if request.method == "POST" and form.is_valid():

        missao = form.save(commit=False)

        missao.cartao = cartao

        try:

            missao.full_clean()

        except ValidationError as erro:

            adicionar_erros_validacao(form, erro)

        else:

            missao.save()

            messages.success(request, "Missão cadastrada com sucesso!")

            return redirecionar_fluxo(request, "cartao_programa:listar_missoes", plantao_id=plantao.pk)

    return render(request, "cartao_programa/missoes/form.html", {

        "plantao": plantao,

        "cartao": cartao,

        "form": form,

        "titulo": "Cadastrar Missão",
            "fluxo_cartao": fluxo_cartao_ativo(request),

        "edicao": False,

    })

# =====================================================

# MISSÕES - EDITAR

# =====================================================

@acesso_gestao_equipes

def editar_missao(request, plantao_id, pk):

    plantao = get_object_or_404(Plantao, pk=plantao_id)

    cartao = get_object_or_404(CartaoPrograma, plantao=plantao)

    missao = get_object_or_404(MissaoCartao, pk=pk, cartao=cartao)

    form = MissaoCartaoForm(

        request.POST if request.method == "POST" else None,

        instance=missao,

        cartao=cartao,

    )

    if request.method == "POST" and form.is_valid():

        atualizada = form.save(commit=False)

        atualizada.cartao = cartao

        try:

            atualizada.full_clean()

        except ValidationError as erro:

            adicionar_erros_validacao(form, erro)

        else:

            atualizada.save()

            messages.success(request, "Missão atualizada com sucesso!")

            return redirecionar_fluxo(request, "cartao_programa:listar_missoes", plantao_id=plantao.pk)

    return render(request, "cartao_programa/missoes/form.html", {

        "plantao": plantao,

        "cartao": cartao,

        "missao": missao,

        "form": form,

        "titulo": "Editar Missão",
            "fluxo_cartao": fluxo_cartao_ativo(request),

        "edicao": True,

    })

# =====================================================

# MISSÕES - REMOVER (SOMENTE POR POST)

# =====================================================

@acesso_gestao_equipes

def remover_missao(request, plantao_id, pk):

    plantao = get_object_or_404(Plantao, pk=plantao_id)

    cartao = get_object_or_404(CartaoPrograma, plantao=plantao)

    missao = get_object_or_404(MissaoCartao, pk=pk, cartao=cartao)

    if request.method == "POST":

        numero = missao.numero

        missao.delete()

        messages.success(request, f"Missão {numero} removida com sucesso!")

        return redirecionar_fluxo(request, "cartao_programa:listar_missoes", plantao_id=plantao.pk)

    return render(request, "cartao_programa/missoes/remocao.html", {

        "plantao": plantao,

        "cartao": cartao,

        "missao": missao,

        "fluxo_cartao": fluxo_cartao_ativo(request),
    })


# =====================================================
# MISSÕES - CADASTRO EM LOTE POR POLO
# =====================================================


@acesso_gestao_equipes
def criar_missoes_em_lote(request, plantao_id):
    """Cadastra uma missão por escola, de maneira atômica e sequencial."""

    plantao = get_object_or_404(Plantao, pk=plantao_id)
    cartao = get_object_or_404(CartaoPrograma, plantao=plantao)

    # Recupera o polo selecionado na página.
    polo_selecionado = request.GET.get("polo")

    # Cria o formulário mantendo o polo selecionado.
    if request.method == "POST":
        form = MissoesEmLoteForm(
            request.POST,
            cartao=cartao,
        )
    else:
        form = MissoesEmLoteForm(
            cartao=cartao,
            initial=(
                {"polo": polo_selecionado}
                if polo_selecionado
                else None
            ),
        )

    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        escolas = list(dados["escolas"].order_by("nome"))

        try:
            # Serializa os cadastros em lote para evitar números
            # repetidos em requisições simultâneas.
            with transaction.atomic():
                CartaoPrograma.objects.select_for_update().get(
                    pk=cartao.pk
                )

                ultimo_numero = (
                    MissaoCartao.objects.filter(cartao=cartao)
                    .order_by("-numero")
                    .values_list("numero", flat=True)
                    .first()
                ) or 0

                for indice, escola in enumerate(escolas, start=1):
                    missao = MissaoCartao(
                        cartao=cartao,
                        numero=ultimo_numero + indice,
                        viatura=dados["viatura"],
                        escola=escola,
                        local="",
                        endereco=escola.endereco or "",
                        periodo=dados["periodo"],
                        horario_inicio=dados.get("horario_inicio"),
                        horario_fim=dados.get("horario_fim"),
                        tipo_missao=dados["tipo_missao"],
                        observacoes=dados.get("observacoes") or "",
                    )

                    # Valida a missão antes de salvar.
                    missao.full_clean()
                    missao.save()

        except ValidationError as erro:
            adicionar_erros_validacao(form, erro)

        else:
            messages.success(
                request,
                f"{len(escolas)} missão(ões) cadastrada(s) com sucesso!",
            )

            return redirecionar_fluxo(
                request,
                "cartao_programa:listar_missoes",
                plantao_id=plantao.pk,
            )

    return render(
        request,
        "cartao_programa/missoes/form_lote.html",
        {
            "plantao": plantao,
            "cartao": cartao,
            "form": form,
            "titulo": "Cadastrar Missões por Polo",
            "fluxo_cartao": fluxo_cartao_ativo(request),
        },
    )

# =====================================================
# LISTAR CARTÕES PROGRAMA
# =====================================================

@acesso_gestao_equipes
def listar_cartoes(request):

    cartoes = (
        CartaoPrograma.objects
        .select_related("plantao", "coordenador")
        .order_by("-plantao__data", "-pk")
    )

    return render(
        request,
        "cartao_programa/cartoes/listar.html",
        {
            "cartoes": cartoes
        }
    )



# =====================================================
# EXCLUIR PLANTÃO E REGISTROS VINCULADOS
# =====================================================

@acesso_gestao_equipes
def excluir_plantao(request, plantao_id):

    plantao = get_object_or_404(
        Plantao,
        pk=plantao_id
    )

    # Exclusão permitida somente via POST.
    if request.method != "POST":
        messages.warning(
            request,
            "Confirme a exclusão do plantão."
        )
        return redirect(
            "cartao_programa:listar_plantoes"
        )

    try:
        with transaction.atomic():

            # Excluir missões vinculadas ao cartão.
            MissaoCartao.objects.filter(
                cartao__plantao=plantao
            ).delete()

            # Excluir o Cartão Programa.
            CartaoPrograma.objects.filter(
                plantao=plantao
            ).delete()

            # Excluir os integrantes das viaturas.
            EfetivoViatura.objects.filter(
                viatura__plantao=plantao
            ).delete()

            # Excluir as viaturas do plantão.
            ViaturaPlantao.objects.filter(
                plantao=plantao
            ).delete()

            # Excluir o plantão.
            plantao.delete()

    except ProtectedError:
        messages.error(
            request,
            "Não foi possível excluir o plantão "
            "porque existem outros registros "
            "protegidos vinculados."
        )

    else:
        messages.success(
            request,
            "Plantão e todos os registros vinculados "
            "excluídos com sucesso!"
        )

    return redirect(
        "cartao_programa:listar_plantoes"
    )


# =========================================================
# ÁREA DO GCM - FUNÇÕES AUXILIARES
# =========================================================

def obter_gcm_logado(request):
    """
    Retorna o cadastro do GCM autenticado.

    Apenas usuários ativos com perfil GCM
    podem acessar a área operacional.
    """

    if not request.user.is_active:
        raise PermissionDenied(
            "Sua conta está inativa."
        )

    usuario = Usuario.objects.filter(
        user=request.user,
        ativo=True,
        perfil="GCM",
    ).first()

    if usuario is None:
        raise PermissionDenied(
            "Esta área é exclusiva para GCMs ativos."
        )

    return usuario


def obter_escala_gcm(request, viatura_id):
    """
    Obtém a escala real do GCM na viatura.

    Não utiliza a função habitual da equipe.
    """

    usuario = obter_gcm_logado(request)

    escala = get_object_or_404(
        EfetivoViatura.objects.select_related(
            "viatura",
            "viatura__plantao",
            "viatura__equipe",
        ),
        viatura_id=viatura_id,
        gcm=usuario,
    )

    return escala


# =========================================================
# MEU CARTÃO PROGRAMA - GCM
# =========================================================

@login_required
def meu_cartao_programa(request):
    """
    Exibe somente os cartões e as missões
    correspondentes às viaturas nas quais
    o GCM está escalado.
    """

    usuario = obter_gcm_logado(request)

    escalas = list(
        EfetivoViatura.objects.filter(
            gcm=usuario,
            viatura__plantao__cartao_programa__isnull=False,
        )
        .select_related(
            "viatura",
            "viatura__plantao",
            "viatura__equipe",
            "viatura__plantao__cartao_programa",
        )
        .order_by(
            "-viatura__plantao__data",
            "-viatura__plantao_id",
            "viatura__identificacao",
        )
    )

    # Consulta somente missões pertencentes
    # às viaturas efetivamente escaladas.
    viatura_ids = [
        escala.viatura_id
        for escala in escalas
    ]

    missoes = (
        MissaoCartao.objects.filter(
            viatura_id__in=viatura_ids,
            cartao__plantao_id__in=[
                escala.viatura.plantao_id
                for escala in escalas
            ],
        )
        .select_related(
            "escola",
            "viatura",
            "cartao",
        )
        .order_by(
            "numero"
        )
    )

    # Agrupa as missões por viatura e plantão,
    # evitando exibir missões de outros efetivos.
    missoes_por_viatura = {}

    for missao in missoes:

        if (
            missao.cartao.plantao_id
            != missao.viatura.plantao_id
        ):
            continue

        missoes_por_viatura.setdefault(
            missao.viatura_id,
            []
        ).append(missao)

    cartoes_gcm = []

    for escala in escalas:

        viatura = escala.viatura

        cartoes_gcm.append({
            "escala": escala,
            "viatura": viatura,
            "plantao": viatura.plantao,
            "cartao": (
                viatura.plantao.cartao_programa
            ),
            "missoes": missoes_por_viatura.get(
                viatura.pk,
                []
            ),
            "pode_registrar_visita": (
                escala.funcao in ["C", "P1", "P2"]
            ),
            "pode_registrar_km": (
                escala.funcao in ["C", "M"]
            ),
        })

    return render(
        request,
        "cartao_programa/gcm/meu_cartao.html",
        {
            "usuario": usuario,
            "cartoes_gcm": cartoes_gcm,
        }
    )


# =========================================================
# FORMULÁRIO DE QUILOMETRAGEM
# =========================================================

class QuilometragemGCMForm(django_forms.ModelForm):
    """
    Permite alterar exclusivamente os campos
    de quilometragem da viatura.
    """

    class Meta:

        model = ViaturaPlantao

        fields = [
            "km_inicial",
            "km_final",
        ]

        labels = {
            "km_inicial": "KM inicial",
            "km_final": "KM final",
        }

        widgets = {
            "km_inicial": django_forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                    "placeholder": "Informe o KM inicial",
                }
            ),
            "km_final": django_forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                    "placeholder": "Informe o KM final",
                }
            ),
        }

    def clean(self):

        dados = super().clean()

        km_inicial = dados.get("km_inicial")
        km_final = dados.get("km_final")

        if (
            km_inicial is not None
            and km_final is not None
            and km_final < km_inicial
        ):
            self.add_error(
                "km_final",
                "O KM final não pode ser menor "
                "que o KM inicial."
            )

        return dados


# =========================================================
# REGISTRAR QUILOMETRAGEM - GCM
# =========================================================

@login_required
def registrar_quilometragem_gcm(request, viatura_id):
    """
    Permite registrar ou atualizar a quilometragem
    somente quando o GCM estiver escalado como:

    C = Comandante
    M = Motorista

    P1 e P2 não podem alterar quilometragem.
    """

    escala = obter_escala_gcm(
        request,
        viatura_id
    )

    if escala.funcao not in ["C", "M"]:
        raise PermissionDenied(
            "Somente o Comandante e o Motorista "
            "podem registrar a quilometragem."
        )

    viatura = escala.viatura

    # A área operacional utiliza apenas
    # viaturas pertencentes a cartões existentes.
    if not CartaoPrograma.objects.filter(
        plantao_id=viatura.plantao_id
    ).exists():
        raise PermissionDenied(
            "Esta viatura ainda não possui "
            "um Cartão Programa cadastrado."
        )

    if request.method == "POST":

        # Bloqueia a linha durante a atualização
        # em bancos que oferecem suporte a
        # SELECT FOR UPDATE.
        with transaction.atomic():

            viatura = get_object_or_404(
                ViaturaPlantao.objects.select_for_update(),
                pk=viatura_id
            )

            # Revalida a escala dentro da transação.
            usuario = obter_gcm_logado(request)

            if not EfetivoViatura.objects.filter(
                viatura=viatura,
                gcm=usuario,
                funcao__in=["C", "M"],
            ).exists():
                raise PermissionDenied(
                    "Você não possui autorização "
                    "para alterar esta quilometragem."
                )

            form = QuilometragemGCMForm(
                request.POST,
                instance=viatura
            )

            if form.is_valid():

                atualizada = form.save(
                    commit=False
                )

                try:

                    atualizada.full_clean()

                except ValidationError as erro:

                    adicionar_erros_validacao(
                        form,
                        erro
                    )

                else:

                    atualizada.save(
                        update_fields=[
                            "km_inicial",
                            "km_final",
                        ]
                    )

                    messages.success(
                        request,
                        "Quilometragem registrada "
                        "com sucesso!"
                    )

                    return redirect(
                        "cartao_programa:meu_cartao_programa"
                    )

    else:

        form = QuilometragemGCMForm(
            instance=viatura
        )

    return render(
        request,
        "cartao_programa/gcm/quilometragem.html",
        {
            "form": form,
            "viatura": viatura,
            "plantao": viatura.plantao,
            "escala": escala,
        }
    )
# =========================================================
# GCM - REGISTRAR MISSÃO NÃO REALIZADA
# =========================================================

@login_required
@require_POST
def registrar_missao_nao_realizada(request, missao_id):

    usuario = obter_gcm_logado(request)

    motivo = request.POST.get(
        "motivo_nao_realizacao", ""
    ).strip()

    if not motivo:
        messages.error(
            request,
            "Informe o motivo da não realização da missão."
        )
        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    if len(motivo) > 3000:
        messages.error(
            request,
            "A justificativa deve ter no máximo 3000 caracteres."
        )
        return redirect(
            "cartao_programa:meu_cartao_programa"
        )

    with transaction.atomic():

        missao = get_object_or_404(
            MissaoCartao.objects.select_for_update()
            .select_related("cartao", "viatura"),
            pk=missao_id
        )

        if missao.cartao.plantao_id != missao.viatura.plantao_id:
            raise PermissionDenied(
                "A missão não corresponde ao plantão da viatura."
            )

        escala = EfetivoViatura.objects.filter(
            viatura_id=missao.viatura_id,
            gcm=usuario,
            funcao__in=["C", "P1", "P2"],
        ).first()

        if escala is None:
            raise PermissionDenied(
                "Você não possui autorização para justificar esta missão."
            )

        if missao.status_execucao != "PENDENTE":
            messages.warning(
                request,
                "Esta missão já possui um resultado registrado."
            )
            return redirect(
                "cartao_programa:meu_cartao_programa"
            )

        if RondaVisita.objects.filter(
            missao_cartao_id=missao.pk
        ).exists():
            messages.warning(
                request,
                "Esta missão já possui uma visita registrada."
            )
            return redirect(
                "cartao_programa:meu_cartao_programa"
            )

        missao.status_execucao = "NAO_REALIZADA"
        missao.motivo_nao_realizacao = motivo
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

    messages.success(
        request,
        "Missão registrada como não realizada. "
        "A justificativa está disponível para a equipe."
    )

    return redirect(
        "cartao_programa:meu_cartao_programa"
    )