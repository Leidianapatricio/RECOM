
from django.urls import path

from . import views


app_name = "cartao_programa"


urlpatterns = [

    # =====================================================
    # ÁREA DO GCM - CARTÃO PROGRAMA INDIVIDUAL
    # =====================================================

    path(
        "meu-cartao/",
        views.meu_cartao_programa,
        name="meu_cartao_programa"
    ),

    path(
        "meu-cartao/viaturas/<int:viatura_id>/quilometragem/",
        views.registrar_quilometragem_gcm,
        name="registrar_quilometragem_gcm"
    ),
    
    path(
        "meu-cartao/missoes/<int:missao_id>/nao-realizada/",
        views.registrar_missao_nao_realizada,
        name="registrar_missao_nao_realizada"
    ),

    # =====================================================
    # EQUIPES
    # =====================================================

    path(
        "equipes/",
        views.listar_equipes,
        name="listar_equipes"
    ),

    path(
        "equipes/nova/",
        views.criar_equipe,
        name="criar_equipe"
    ),

    path(
        "equipes/<int:pk>/editar/",
        views.editar_equipe,
        name="editar_equipe"
    ),

    # =====================================================
    # INTEGRANTES DAS EQUIPES
    # =====================================================

    path(
        "equipes/<int:equipe_id>/integrantes/",
        views.listar_integrantes,
        name="listar_integrantes"
    ),

    path(
        "equipes/<int:equipe_id>/integrantes/adicionar/",
        views.adicionar_integrante,
        name="adicionar_integrante"
    ),

    path(
        "equipes/<int:equipe_id>/integrantes/<int:pk>/editar/",
        views.editar_integrante,
        name="editar_integrante"
    ),

    path(
        "equipes/<int:equipe_id>/integrantes/<int:pk>/remover/",
        views.remover_integrante,
        name="remover_integrante"
    ),

    # =====================================================
    # PLANTÕES
    # =====================================================

    path(
        "plantoes/",
        views.listar_plantoes,
        name="listar_plantoes"
    ),

    path(
        "plantoes/novo/",
        views.criar_plantao,
        name="criar_plantao"
    ),

    # =====================================================
    # VIATURAS DOS PLANTÕES
    # =====================================================

    path(
        "plantoes/<int:plantao_id>/viaturas/",
        views.listar_viaturas,
        name="listar_viaturas"
    ),

    path(
        "plantoes/<int:plantao_id>/viaturas/nova/",
        views.criar_viatura,
        name="criar_viatura"
    ),

    path(
        "plantoes/<int:plantao_id>/viaturas/<int:pk>/editar/",
        views.editar_viatura,
        name="editar_viatura"
    ),

    # =====================================================
    # EFETIVO DAS VIATURAS
    # =====================================================

    path(
        "plantoes/<int:plantao_id>/viaturas/<int:viatura_id>/efetivo/",
        views.listar_efetivo,
        name="listar_efetivo"
    ),

    path(
        "plantoes/<int:plantao_id>/viaturas/<int:viatura_id>/efetivo/adicionar/",
        views.adicionar_efetivo,
        name="adicionar_efetivo"
    ),

    path(
        "plantoes/<int:plantao_id>/viaturas/<int:viatura_id>/efetivo/<int:pk>/editar/",
        views.editar_efetivo,
        name="editar_efetivo"
    ),

    path(
        "plantoes/<int:plantao_id>/viaturas/<int:viatura_id>/efetivo/<int:pk>/remover/",
        views.remover_efetivo,
        name="remover_efetivo"
    ),

    # =====================================================
    # CARTÃO PROGRAMA - GESTÃO
    # =====================================================

    path(
        "plantoes/<int:plantao_id>/cartao/",
        views.visualizar_cartao,
        name="visualizar_cartao"
    ),

    path(
        "plantoes/<int:plantao_id>/cartao/criar/",
        views.criar_cartao,
        name="criar_cartao"
    ),

    path(
        "plantoes/<int:plantao_id>/cartao/editar/",
        views.editar_cartao,
        name="editar_cartao"
    ),

    # =====================================================
    # MISSÕES DO CARTÃO PROGRAMA
    # =====================================================

    path(
        "plantoes/<int:plantao_id>/cartao/missoes/",
        views.listar_missoes,
        name="listar_missoes"
    ),

    # Cadastro individual de missão
    path(
        "plantoes/<int:plantao_id>/cartao/missoes/nova/",
        views.criar_missao,
        name="criar_missao"
    ),

    # Cadastro de várias missões por polo
    path(
        "plantoes/<int:plantao_id>/cartao/missoes/lote/",
        views.criar_missoes_em_lote,
        name="criar_missoes_em_lote"
    ),

    path(
        "plantoes/<int:plantao_id>/cartao/missoes/<int:pk>/editar/",
        views.editar_missao,
        name="editar_missao"
    ),

    path(
        "plantoes/<int:plantao_id>/cartao/missoes/<int:pk>/remover/",
        views.remover_missao,
        name="remover_missao"
    ),

    # =====================================================
    # LISTAGEM DOS CARTÕES PROGRAMA
    # =====================================================

    path(
        "cartoes/",
        views.listar_cartoes,
        name="listar_cartoes"
    ),

    # =====================================================
    # EXCLUIR PLANTÃO
    # =====================================================

    path(
        "plantoes/<int:plantao_id>/excluir/",
        views.excluir_plantao,
        name="excluir_plantao"
    ),
    
    path(
        "meu-cartao/",
        views.meu_cartao_programa,
        name="meu_cartao_programa"
    ),

    path(
        "meu-cartao/viaturas/<int:viatura_id>/quilometragem/",
        views.registrar_quilometragem_gcm,
        name="registrar_quilometragem_gcm"
    ),
    
    path(
        "cartoes/<int:pk>/excluir/",
        views.excluir_cartao,
        name="excluir_cartao"
    ),

]
