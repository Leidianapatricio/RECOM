from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cartao_programa.models import EfetivoViatura, MissaoCartao
from usuarios.models import Usuario
from .forms import RondaVisitaForm, dados_da_missao
from .models import RondaVisita


def obter_usuario_recom(request):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied('É necessário estar autenticado e ativo.')
    usuario = Usuario.objects.filter(user=request.user).first()
    if usuario is None or not usuario.ativo:
        if request.user.is_superuser:
            return None
        raise PermissionDenied('Usuário RECOM não encontrado ou inativo.')
    return usuario


def pode_gerenciar_visitas(request):
    usuario = obter_usuario_recom(request)
    return request.user.is_superuser or (
        usuario is not None and usuario.perfil in ('ADMIN', 'COORDENADOR')
    )


def validar_acesso_missao(request, missao):
    if missao.cartao.plantao_id != missao.viatura.plantao_id:
        raise PermissionDenied('A missão não corresponde ao plantão da viatura.')
    if pode_gerenciar_visitas(request):
        return
    usuario = obter_usuario_recom(request)
    if usuario is None or usuario.perfil != 'GCM':
        raise PermissionDenied('Você não possui permissão para registrar visitas nesta missão.')
    escala = EfetivoViatura.objects.filter(
        viatura_id=missao.viatura_id, gcm=usuario
    ).first()
    if escala is None:
        raise PermissionDenied('Esta missão não pertence à sua escala.')
    if escala.funcao not in ('C', 'P1', 'P2'):
        raise PermissionDenied('Sua função na viatura não permite registrar visitas nesta missão.')


def obter_missao_autorizada(request, missao_id):
    missao = get_object_or_404(
        MissaoCartao.objects.select_related('escola', 'viatura', 'cartao__plantao'),
        pk=missao_id,
    )
    validar_acesso_missao(request, missao)
    if missao.escola_id is None:
        raise PermissionDenied('Esta missão não possui escola vinculada.')
    return missao


def validar_exclusao_visita(request, visita):
    """GCM só exclui visita própria; a missão nunca é excluída."""
    if pode_gerenciar_visitas(request):
        return
    usuario = obter_usuario_recom(request)
    if usuario is None or usuario.perfil != 'GCM':
        raise PermissionDenied('Você não possui permissão para excluir visitas.')
    if visita.registrado_por_id != usuario.pk:
        raise PermissionDenied('Você só pode excluir visitas cadastradas por você.')


def adicionar_erros_modelo(form, erro):
    if hasattr(erro, 'error_dict'):
        for campo, erros in erro.error_dict.items():
            form.add_error(campo if campo in form.fields else None, erros)
    else:
        form.add_error(None, erro)


def redirecionar_apos_visita(request, visita):
    usuario = obter_usuario_recom(request)
    if visita.missao_cartao_id and usuario is not None and usuario.perfil == 'GCM':
        return redirect('cartao_programa:meu_cartao_programa')
    return redirect('escolas:detalhe_escola', pk=visita.escola_id)


@login_required
def cadastrar_visita(request):
    usuario = obter_usuario_recom(request)
    missao_id = (
        request.POST.get('missao_cartao_id', '').strip()
        if request.method == 'POST'
        else request.GET.get('missao', '').strip()
    )
    missao = obter_missao_autorizada(request, missao_id) if missao_id else None

    if missao is not None and (
        missao.status_execucao != 'PENDENTE'
        or RondaVisita.objects.filter(missao_cartao_id=missao.pk).exists()
    ):
        messages.warning(request, 'Esta missão já possui um resultado registrado.')
        if pode_gerenciar_visitas(request):
            return redirect('escolas:detalhe_escola', pk=missao.escola_id)
        return redirect('cartao_programa:meu_cartao_programa')

    if request.method == 'POST':
        form = RondaVisitaForm(request.POST, missao=missao)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if missao is not None:
                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(of=('self',)),
                            pk=missao.pk,
                        )
                        validar_acesso_missao(request, missao)
                        if missao.status_execucao != 'PENDENTE':
                            raise ValidationError('Esta missão já possui um resultado registrado.')
                        if RondaVisita.objects.filter(missao_cartao_id=missao.pk).exists():
                            raise ValidationError('Já existe uma visita registrada para esta missão.')

                    visita = form.save(commit=False)
                    visita.missao_cartao = missao
                    visita.registrado_por = usuario
                    if missao is not None:
                        for campo, valor in dados_da_missao(missao).items():
                            setattr(visita, campo, valor)
                    visita.full_clean()
                    visita.save()

                    if missao is not None:
                        missao.status_execucao = 'REALIZADA'
                        missao.motivo_nao_realizacao = ''
                        missao.registrado_por = usuario
                        missao.atualizado_execucao_em = timezone.now()
                        missao.save(update_fields=[
                            'status_execucao', 'motivo_nao_realizacao',
                            'registrado_por', 'atualizado_execucao_em',
                        ])
            except ValidationError as erro:
                adicionar_erros_modelo(form, erro)
            except IntegrityError:
                form.add_error(None, 'Esta missão já possui uma visita ou ocorreu um conflito ao salvar.')
            else:
                messages.success(request, 'Visita registrada com sucesso.')
                return redirecionar_apos_visita(request, visita)
    else:
        initial = {}
        if missao is not None:
            initial['escola'] = missao.escola_id
            initial['data_visita'] = missao.cartao.plantao.data
        elif request.GET.get('escola'):
            initial['escola'] = request.GET['escola']
        form = RondaVisitaForm(initial=initial, missao=missao)

    return render(request, 'visitas/form_visita.html', {
        'form': form,
        'modo_edicao': False,
        'missao_cartao': missao,
        'missao_cartao_id': missao.pk if missao is not None else None,
        'usuario': usuario,
    })


@login_required
def editar_visita(request, pk):
    usuario = obter_usuario_recom(request)
    visita = get_object_or_404(
        RondaVisita.objects.select_related('escola', 'missao_cartao'), pk=pk
    )
    missao = visita.missao_cartao
    if missao is not None:
        validar_acesso_missao(request, missao)
    elif not pode_gerenciar_visitas(request):
        raise PermissionDenied('A edição de visitas avulsas está restrita aos administradores e coordenadores.')

    if request.method == 'POST':
        form = RondaVisitaForm(request.POST, instance=visita, missao=missao)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if missao is not None:
                        missao = get_object_or_404(
                            MissaoCartao.objects.select_for_update(of=('self',)), pk=missao.pk
                        )
                        validar_acesso_missao(request, missao)
                        if missao.status_execucao == 'NAO_REALIZADA':
                            raise ValidationError('Esta missão está marcada como não realizada.')
                    atualizada = form.save(commit=False)
                    atualizada.missao_cartao = missao
                    # Preserva o autor original da visita ao editar.
                    atualizada.registrado_por_id = visita.registrado_por_id
                    if missao is not None:
                        for campo, valor in dados_da_missao(missao).items():
                            setattr(atualizada, campo, valor)
                    atualizada.full_clean()
                    atualizada.save()
                    if missao is not None and missao.status_execucao != 'REALIZADA':
                        missao.status_execucao = 'REALIZADA'
                        missao.motivo_nao_realizacao = ''
                        missao.save(update_fields=['status_execucao', 'motivo_nao_realizacao'])
            except ValidationError as erro:
                adicionar_erros_modelo(form, erro)
            except IntegrityError:
                form.add_error(None, 'Não foi possível salvar a visita devido a um conflito de dados.')
            else:
                messages.success(request, 'Visita atualizada com sucesso.')
                return redirecionar_apos_visita(request, atualizada)
    else:
        form = RondaVisitaForm(instance=visita, missao=missao)

    return render(request, 'visitas/form_visita.html', {
        'form': form,
        'visita': visita,
        'modo_edicao': True,
        'missao_cartao': missao,
        'missao_cartao_id': missao.pk if missao is not None else None,
        'usuario': usuario,
    })


@login_required
@require_POST
def excluir_visita(request, pk):
    """Exclui visita autorizada, nunca a missão; reabre missão se necessário."""
    usuario = obter_usuario_recom(request)
    referencia = get_object_or_404(RondaVisita, pk=pk)
    validar_exclusao_visita(request, referencia)
    missao_id = referencia.missao_cartao_id

    with transaction.atomic():
        missao = None
        if missao_id is not None:
            missao = get_object_or_404(
                MissaoCartao.objects.select_for_update(of=('self',)), pk=missao_id
            )
        visita = get_object_or_404(
            RondaVisita.objects.select_for_update(of=('self',)), pk=pk
        )
        if visita.missao_cartao_id != missao_id:
            raise ValidationError('O vínculo da visita foi alterado. Atualize a página.')
        # Confirma a autoria novamente após obter o bloqueio.
        validar_exclusao_visita(request, visita)
        escola_id = visita.escola_id
        visita.delete()

        if missao is not None and not RondaVisita.objects.filter(
            missao_cartao_id=missao.pk
        ).exists():
            missao.status_execucao = 'PENDENTE'
            missao.motivo_nao_realizacao = ''
            missao.registrado_por = None
            missao.atualizado_execucao_em = None
            missao.save(update_fields=[
                'status_execucao', 'motivo_nao_realizacao',
                'registrado_por', 'atualizado_execucao_em',
            ])

    messages.success(request, 'Visita excluída com sucesso.')
    return redirect('escolas:detalhe_escola', pk=escola_id)
