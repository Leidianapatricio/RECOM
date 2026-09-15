from django.test import TestCase
from django.urls import reverse

from datetime import date, time

from escolas.models import (
    Escola,
    EscolaProblematica,
    TipoProblematica,
)
from visitas.models import RondaVisita



class HomePageTest(TestCase):

    def test_home_retorna_status_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        

class LoginPageTest(TestCase):

    def test_login_retorna_status_200(self):
        response = self.client.get(reverse("core:login"))
        self.assertEqual(response.status_code, 200)

class DashboardCoordenadorTest(TestCase):

    def setUp(self):
        # -------------------------------------------------
        # ESCOLAS
        # -------------------------------------------------

        self.escola_ativa_1 = Escola.objects.create(
            nome="Escola Ativa Polo 1",
            polo=1,
            endereco="Rua A",
            bairro="Centro",
            gestor="Gestor A",
            quantidade_alunos=300,
            quantidade_alunos_pcd=5,
            ativa=True,
        )

        self.escola_ativa_2 = Escola.objects.create(
            nome="Escola Ativa Polo 2",
            polo=2,
            endereco="Rua B",
            bairro="Bancários",
            gestor="Gestor B",
            quantidade_alunos=400,
            quantidade_alunos_pcd=10,
            ativa=True,
        )

        self.escola_inativa = Escola.objects.create(
            nome="Escola Inativa",
            polo=1,
            endereco="Rua C",
            bairro="Mangabeira",
            gestor="Gestor C",
            quantidade_alunos=200,
            quantidade_alunos_pcd=3,
            ativa=False,
        )

        # -------------------------------------------------
        # PROBLEMÁTICAS
        # -------------------------------------------------

        self.tipo_bullying = TipoProblematica.objects.create(
            nome="Bullying"
        )

        self.tipo_drogas = TipoProblematica.objects.create(
            nome="Drogas"
        )

        EscolaProblematica.objects.create(
            escola=self.escola_ativa_1,
            tipo_problematica=self.tipo_bullying,
        )

        EscolaProblematica.objects.create(
            escola=self.escola_ativa_2,
            tipo_problematica=self.tipo_drogas,
        )

        # -------------------------------------------------
        # VISITAS
        # -------------------------------------------------

        RondaVisita.objects.create(
            escola=self.escola_ativa_1,
            equipe="A",
            data_visita=date(2026, 9, 15),
            horario=time(9, 0),
            tipo_visita="ROTINA",
            situacao="SEM_ALTERACAO",
        )

        RondaVisita.objects.create(
            escola=self.escola_ativa_2,
            equipe="B",
            data_visita=date(2026, 9, 15),
            horario=time(14, 0),
            tipo_visita="SAIDA",
            situacao="COM_ALTERACAO",
        )

    def test_dashboard_carrega_corretamente(self):
        """Verifica se o dashboard do coordenador responde normalmente."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.status_code,
            200
        )

    def test_total_escolas(self):
        """Verifica o indicador total de escolas."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["total_escolas"],
            3
        )

    def test_total_escolas_ativas(self):
        """Verifica o indicador de escolas ativas."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["escolas_ativas"],
            2
        )

    def test_total_escolas_inativas(self):
        """Verifica o indicador de escolas inativas."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["escolas_inativas"],
            1
        )

    def test_total_problematicas(self):
        """Verifica o indicador total de problemáticas."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["total_problematicas"],
            2
        )

    def test_total_visitas(self):
        """Verifica o indicador total de visitas."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["total_visitas"],
            2
        )

    def test_visitas_sem_alteracao(self):
        """Verifica o indicador de visitas sem alteração."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["visitas_sem_alteracao"],
            1
        )

    def test_visitas_com_alteracao(self):
        """Verifica o indicador de visitas com alteração."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        self.assertEqual(
            response.context["visitas_com_alteracao"],
            1
        )

    def test_escolas_ativas_por_polo(self):
        """Verifica o agrupamento das escolas ativas por polo."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        resultado = list(
            response.context["escolas_por_polo"]
        )

        self.assertEqual(
            resultado,
            [
                {
                    "polo": 1,
                    "total": 1,
                },
                {
                    "polo": 2,
                    "total": 1,
                },
            ]
        )

    def test_problematicas_por_tipo(self):
        """Verifica o agrupamento das problemáticas por tipo."""

        response = self.client.get(
            reverse("core:dashboard_coordenador")
        )

        resultado = list(
            response.context["problematicas_por_tipo"]
        )

        self.assertEqual(
            len(resultado),
            2
        )