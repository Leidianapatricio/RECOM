
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cartao_programa.models import EfetivoViatura, MissaoCartao
from usuarios.models import Usuario

from .forms import RondaVisitaForm, dados_da_missao
from .models import RondaVisita


# =========================================================
# FUNÇÕES AUXILIARES - CONTROLE DE ACESSO
# =========================================================

def obter_usuario_recom(request):
    """
    Retorna o usuário RECOM vinculado ao usuário Django.

    Superusuários Django podem não possuir cadastro
    no modelo Usuario.
    """

    if not request.user.is_authenticated:
        raise PermissionDenied(
            "É necessário estar autenticado."
        )

    if not request.user.is_active:
        raise PermissionDenied(
            "Usuário inativo."
        )

    usuario = Usuario.objects.filter(
        user=request.user
    ).first()

    if usuario is None or not usuario.ativo:

        if request.user.is_superuser:
            return None

        raise PermissionDenied(
            "Usuário RECOM não encontrado ou inativo."
        )

    return usuario


def pode_gerenciar_visitas(request):
    """
    Administradores e coordenadores podem
    gerenciar os registros de visitas.
    """

    usuario = obter_usuario_recom(request)

    if request.user.is_superuser:
        return True

    return (
        usuario is not None
        and usuario.perfil in [
            "ADMIN",
            "COORDENADOR",
        ]
    )


def validar_acesso_missao(request, missao):
    """
    Verifica se o GCM pode registrar visitas
    vinculadas à missão do Cartão Programa.

    C  = Comandante: permitido
    M  = Motorista: não permitido
    P1 = Patrulheiro 1: permitido
    P2 = Patrulheiro 2: permitido
    """

    # Confere a integridade do vínculo entre
    # missão, cartão e plantão da viatura.
    if (
        missao.cartao.plantao_id
        != missao.viatura.plantao_id
    ):
        raise PermissionDenied(
            "A missão não corresponde ao plantão "
            "da viatura."
        )

    # Administradores e coordenadores podem
    # gerenciar visitas vinculadas às missões.
    if pode_gerenciar_visitas(request):
        return

    usuario = obter_usuario_recom(request)

    if usuario is None or usuario.perfil != "GCM":
        raise PermissionDenied(
            "Você não possui permissão para "
            "registrar visitas nesta missão."
        )

    # A função considerada é a função do GCM
    # na viatura deste plantão, e não sua
    # função habitual na equipe.
    escala = EfetivoViatura.objects.filter(
        viatura_id=missao.viatura_id,
        gcm=usuario,
    ).first()

    if escala is None:
        raise PermissionDenied(
            "Esta missão não pertence à sua escala."
        )

    if escala.funcao == "M":
        raise PermissionDenied(
            "O Motorista possui acesso somente "
            "de visualização às missões. "
            "O registro de visitas é reservado "
            "ao Comandante e aos Patrulheiros."
        )

    if escala.funcao not in ["C", "P1", "P2"]:
        raise PermissionDenied(
            "Sua função não permite registrar "
            "visitas nesta missão."
        )


def obter_missao_autorizada(request, missao_id):
    """
    Recupera a missão e verifica as permissões
    do usuário antes de permitir o registro.
    """

    missao = get_object_or_404(
        MissaoCartao.objects.select_related(
            "escola",
            "viatura",
            "cartao__plantao",
        ),
        pk=missao_id,
    )

    validar_acesso_missao(
        request,
        missao
    )

    if missao.escola_id is None:
        raise PermissionDenied(
            "Esta missão não possui escola "
            "vinculada para registrar visita."
        )

    return missao


def adicionar_erros_modelo(form, erro):
    """
    Exibe os erros do full_clean() diretamente
    no formulário, quando possível.
    """

    if hasattr(erro, "error_dict"):

        for campo, erros in erro.error_dict.items():

            if campo in form.fields:
                form.add_error(
                    campo,
                    erros
                )

            else:
                form.add_error(
                    None,
                    erros
                )

    else:
        form.add_error(
            None,
            erro
        )


def redirecionar_apos_visita(request, visita):
    """
    Define o destino após cadastrar ou editar.

    GCM que registrou uma missão retorna
    ao próprio Cartão Programa.

    Visitas avulsas e registros administrativos
    retornam ao detalhe da escola.
    """

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
        pk=visita.escola_id
    )


# =========================================================
# CADASTRAR VISITA
# =========================================================

@login_required
def cadastrar_visita(request):
    """
    Permite cadastrar visitas avulsas e visitas
    vinculadas ao Cartão Programa.

    Quando existe missão:
    - valida a escala e a função do GCM;
    - preenche a escola automaticamente;
    - impede a troca da escola;
    - vincula a visita à missão;
    - retorna ao Cartão Programa do GCM.
    """

    usuario = obter_usuario_recom(request)

    # ==========================================
    # IDENTIFICAR A MISSÃO
    # ==========================================

    if request.method == "POST":

        missao_id = request.POST.get(
            "missao_cartao_id",
            ""
        ).strip()

    else:

        missao_id = request.GET.get(
            "missao",
            ""
        ).strip()

    missao = None

    if missao_id:

        missao = obter_missao_autorizada(
            request,
            missao_id
        )

    # ==========================================
    # CADASTRO VIA POST
    # ==========================================

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            missao=missao
        )

        if form.is_valid():

            visita = form.save(
                commit=False
            )

            # O vínculo da missão é definido
            # exclusivamente pelo servidor.
            if missao is not None:

                visita.missao_cartao = missao

                for campo, valor in dados_da_missao(missao).items():
                    setattr(visita, campo, valor)

            else:

                visita.missao_cartao = None

            # ==================================
            # VALIDAR MODELO
            # ==================================

            try:

                visita.full_clean()

            except ValidationError as erro:

                adicionar_erros_modelo(
                    form,
                    erro
                )

            else:

                visita.save()

                messages.success(
                    request,
                    "Visita registrada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    visita
                )

    # ==========================================
    # ABERTURA DO FORMULÁRIO VIA GET
    # ==========================================

    else:

        initial = {}

        if missao is not None:

            initial["escola"] = (
                missao.escola_id
            )

            initial["data_visita"] = (
                missao.cartao.plantao.data
            )

        else:

            escola_id = request.GET.get(
                "escola"
            )

            if escola_id:

                initial["escola"] = escola_id

        form = RondaVisitaForm(
            initial=initial,
            missao=missao
        )

    # ==========================================
    # RENDERIZAR FORMULÁRIO
    # ==========================================

    return render(
        request,
        "visitas/form_visita.html",
        {
            "form": form,
            "modo_edicao": False,
            "missao_cartao": missao,
            "missao_cartao_id": (
                missao.pk
                if missao is not None
                else None
            ),
            "usuario": usuario,
        }
    )


# =========================================================
# EDITAR VISITA
# =========================================================

@login_required
def editar_visita(request, pk):
    """
    Edita uma visita existente.

    Visitas vinculadas ao Cartão Programa
    exigem autorização para a missão.

    Visitas avulsas somente podem ser editadas
    pela administração ou coordenação.
    """

    usuario = obter_usuario_recom(request)

    visita = get_object_or_404(
        RondaVisita.objects.select_related(
            "escola",
            "missao_cartao",
        ),
        pk=pk
    )

    missao = visita.missao_cartao

    # ==========================================
    # VALIDAR PERMISSÕES
    # ==========================================

    if missao is not None:

        validar_acesso_missao(
            request,
            missao
        )

    elif not pode_gerenciar_visitas(request):

        raise PermissionDenied(
            "A edição de visitas avulsas está "
            "restrita aos administradores "
            "e coordenadores."
        )

    # ==========================================
    # EDITAR VIA POST
    # ==========================================

    if request.method == "POST":

        form = RondaVisitaForm(
            request.POST,
            instance=visita,
            missao=missao
        )

        if form.is_valid():

            atualizada = form.save(
                commit=False
            )

            # Preserva a missão original.
            atualizada.missao_cartao = missao

            if missao is not None:

                for campo, valor in dados_da_missao(missao).items():
                    setattr(atualizada, campo, valor)

            try:

                atualizada.full_clean()

            except ValidationError as erro:

                adicionar_erros_modelo(
                    form,
                    erro
                )

            else:

                atualizada.save()

                messages.success(
                    request,
                    "Visita atualizada com sucesso."
                )

                return redirecionar_apos_visita(
                    request,
                    atualizada
                )

    # ==========================================
    # ABRIR FORMULÁRIO DE EDIÇÃO
    # ==========================================

    else:

        form = RondaVisitaForm(
            instance=visita,
            missao=missao
        )

    # ==========================================
    # RENDERIZAR
    # ==========================================

    return render(
        request,
        "visitas/form_visita.html",
        {
            "form": form,
            "visita": visita,
            "modo_edicao": True,
            "missao_cartao": missao,
            "missao_cartao_id": (
                missao.pk
                if missao is not None
                else None
            ),
            "usuario": usuario,
        }
    )


# =========================================================
# EXCLUIR VISITA
# =========================================================

@login_required
@require_POST
def excluir_visita(request, pk):
    """
    Exclusão de visitas restrita à gestão.

    Somente Administradores e Coordenadores
    podem excluir registros.
    """

    if not pode_gerenciar_visitas(request):

        raise PermissionDenied(
            "Somente administradores e "
            "coordenadores podem excluir "
            "registros de visitas."
        )

    visita = get_object_or_404(
        RondaVisita,
        pk=pk
    )

    escola_id = visita.escola_id

    visita.delete()

    messages.success(
        request,
        "Visita excluída com sucesso."
    )

    return redirect(
        "escolas:detalhe_escola",
        pk=escola_id
    )
