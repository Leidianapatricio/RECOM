from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from escolas.models import Escola
from .models import RondaVisita


class RondaVisitaModelTest(TestCase):

    def setUp(self):
        self.escola = Escola.objects.create(
            nome="Escola Municipal Teste Visita",
            polo=1,
            endereco="Rua Teste, 100",
            bairro="Centro",
            gestor="Maria da Silva",
            telefone="(83) 99999-9999",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=400,
            quantidade_alunos_pcd=10,
            modalidade="Ensino Fundamental",
            ativa=True,
        )

        self.visita = RondaVisita.objects.create(
            escola=self.escola,
            equipe="A",
            data_visita=date(2026, 9, 15),
            horario=time(9, 30),
            tipo_visita="ROTINA",
            situacao="SEM_ALTERACAO",
            relato="Visita realizada sem alterações.",
            orientacoes="Nenhuma providência necessária.",
        )

    def test_criar_visita(self):
        """Verifica se uma visita pode ser registrada."""

        self.assertEqual(
            RondaVisita.objects.count(),
            1
        )

    def test_visita_associada_escola(self):
        """Verifica se a visita está associada à escola correta."""

        self.assertEqual(
            self.visita.escola,
            self.escola
        )

    def test_equipe_visita(self):
        """Verifica se a equipe foi registrada corretamente."""

        self.assertEqual(
            self.visita.equipe,
            "A"
        )

    def test_tipo_visita(self):
        """Verifica se o tipo da visita foi registrado corretamente."""

        self.assertEqual(
            self.visita.tipo_visita,
            "ROTINA"
        )

    def test_situacao_visita(self):
        """Verifica se a situação foi registrada corretamente."""

        self.assertEqual(
            self.visita.situacao,
            "SEM_ALTERACAO"
        )

    def test_historico_visitas_escola(self):
        """Verifica o acesso ao histórico de visitas pela escola."""

        historico = self.escola.visitas.all()

        self.assertEqual(
            historico.count(),
            1
        )

        self.assertEqual(
            historico.first(),
            self.visita
        )

    def test_equipe_extraordinario(self):
        """Verifica o registro da Equipe Extraordinário."""

        visita_extra = RondaVisita.objects.create(
            escola=self.escola,
            equipe="EXTRA",
            data_visita=date(2026, 9, 16),
            horario=time(10, 0),
            tipo_visita="APOIO",
            situacao="SEM_ALTERACAO",
        )

        self.assertEqual(
            visita_extra.equipe,
            "EXTRA"
        )

        self.assertEqual(
            visita_extra.get_equipe_display(),
            "Equipe Extraordinário"
        )

    def test_visita_com_alteracao(self):
        """Verifica o registro de uma visita com alteração."""

        visita = RondaVisita.objects.create(
            escola=self.escola,
            equipe="B",
            data_visita=date(2026, 9, 16),
            horario=time(14, 0),
            tipo_visita="SAIDA",
            situacao="COM_ALTERACAO",
            relato="Foi identificada uma situação durante a saída.",
            orientacoes="A equipe realizou as orientações necessárias.",
        )

        self.assertEqual(
            visita.situacao,
            "COM_ALTERACAO"
        )

    def test_str_visita(self):
        """Verifica a representação textual da visita."""

        esperado = (
            "Escola Municipal Teste Visita - "
            "15/09/2026 - Equipe A"
        )

        self.assertEqual(
            str(self.visita),
            esperado
        )
class RondaVisitaViewsTest(TestCase):

    def setUp(self):
        self.escola = Escola.objects.create(
            nome="Escola Teste Views Visita",
            polo=1,
            endereco="Rua Teste, 100",
            bairro="Centro",
            gestor="Maria da Silva",
            telefone="(83) 99999-9999",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=300,
            quantidade_alunos_pcd=10,
            modalidade="Ensino Fundamental",
            ativa=True,
        )

        self.visita = RondaVisita.objects.create(
            escola=self.escola,
            equipe="A",
            data_visita=date(2026, 9, 15),
            horario=time(9, 0),
            tipo_visita="ROTINA",
            situacao="SEM_ALTERACAO",
            relato="Visita inicial.",
            orientacoes="Sem providências.",
        )

    def dados_visita(self):
        return {
            "escola": self.escola.pk,
            "equipe": "B",
            "data_visita": "2026-09-16",
            "horario": "10:30",
            "tipo_visita": "SAIDA",
            "situacao": "COM_ALTERACAO",
            "relato": "Situação identificada durante a visita.",
            "orientacoes": "Foram realizadas orientações.",
        }

    def test_pagina_cadastrar_visita(self):
        """Verifica se a página de cadastro de visita é carregada."""

        response = self.client.get(
            reverse("visitas:cadastrar_visita")
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertFalse(
            response.context["modo_edicao"]
        )

    def test_cadastrar_visita_com_escola_preselecionada(self):
        """Verifica se a escola pode vir selecionada pela URL."""

        response = self.client.get(
            reverse("visitas:cadastrar_visita"),
            {
                "escola": self.escola.pk
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response.context["form"].initial["escola"],
            str(self.escola.pk)
        )

    def test_cadastrar_visita(self):
        """Verifica o cadastro de uma visita pela view."""

        quantidade_antes = RondaVisita.objects.count()

        response = self.client.post(
            reverse("visitas:cadastrar_visita"),
            data=self.dados_visita()
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertEqual(
            RondaVisita.objects.count(),
            quantidade_antes + 1
        )

        self.assertTrue(
            RondaVisita.objects.filter(
                escola=self.escola,
                equipe="B",
                tipo_visita="SAIDA"
            ).exists()
        )

    def test_pagina_editar_visita(self):
        """Verifica se a página de edição é carregada."""

        response = self.client.get(
            reverse(
                "visitas:editar_visita",
                kwargs={
                    "pk": self.visita.pk
                }
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTrue(
            response.context["modo_edicao"]
        )

        self.assertEqual(
            response.context["visita"],
            self.visita
        )

    def test_editar_visita(self):
        """Verifica a atualização de uma visita."""

        response = self.client.post(
            reverse(
                "visitas:editar_visita",
                kwargs={
                    "pk": self.visita.pk
                }
            ),
            data=self.dados_visita()
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.visita.refresh_from_db()

        self.assertEqual(
            self.visita.equipe,
            "B"
        )

        self.assertEqual(
            self.visita.tipo_visita,
            "SAIDA"
        )

        self.assertEqual(
            self.visita.situacao,
            "COM_ALTERACAO"
        )

    def test_excluir_visita(self):
        """Verifica a exclusão de uma visita."""

        visita_id = self.visita.pk

        response = self.client.post(
            reverse(
                "visitas:excluir_visita",
                kwargs={
                    "pk": visita_id
                }
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertFalse(
            RondaVisita.objects.filter(
                pk=visita_id
            ).exists()
        )

    def test_excluir_visita_nao_aceita_get(self):
        """Verifica que a exclusão não pode ser realizada por GET."""

        response = self.client.get(
            reverse(
                "visitas:excluir_visita",
                kwargs={
                    "pk": self.visita.pk
                }
            )
        )

        self.assertEqual(
            response.status_code,
            405
        )

        self.assertTrue(
            RondaVisita.objects.filter(
                pk=self.visita.pk
            ).exists()
        )
