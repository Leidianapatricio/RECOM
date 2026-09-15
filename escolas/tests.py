from django.test import TestCase
from django.db import IntegrityError, transaction

from .models import Escola, EscolaProblematica, TipoProblematica
from .forms import EscolaForm
from django.urls import reverse


class EscolaModelTest(TestCase):

    def setUp(self):
        self.escola = Escola.objects.create(
            nome="Escola Municipal Teste",
            polo="1",
            endereco="Rua Teste, 100",
            bairro="Centro",
            gestor="Maria da Silva",
            telefone="(83) 99999-9999",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=500,
            quantidade_alunos_pcd=10,
            modalidade="Ensino Fundamental",
            observacoes="Escola criada para teste.",
            ativa=True,
        )

    def test_criar_escola(self):
        """Verifica se uma escola pode ser cadastrada."""

        self.assertEqual(
            Escola.objects.count(),
            1
        )

    def test_nome_escola(self):
        """Verifica se o nome da escola foi salvo corretamente."""

        self.assertEqual(
            self.escola.nome,
            "Escola Municipal Teste"
        )

    def test_escola_ativa(self):
        """Verifica se a escola está ativa."""

        self.assertTrue(
            self.escola.ativa
        )

    def test_polo_escola(self):
        """Verifica se o polo foi salvo corretamente."""

        self.assertEqual(
            self.escola.polo,
            "1"
        )

    def test_quantidade_alunos(self):
        """Verifica a quantidade de alunos cadastrada."""

        self.assertEqual(
            self.escola.quantidade_alunos,
            500
        )

    def test_quantidade_alunos_pcd(self):
        """Verifica a quantidade de alunos PCD cadastrada."""

        self.assertEqual(
            self.escola.quantidade_alunos_pcd,
            10
        )

    def test_str_escola(self):
        """Verifica a representação textual da escola."""

        self.assertEqual(
            str(self.escola),
            "Escola Municipal Teste"
        )
    
class EscolaFormTest(TestCase):

    def dados_validos(self):
        return {
            "nome": "Escola Municipal Nova",
            "polo": "1",
            "endereco": "Rua das Flores, 100",
            "bairro": "Centro",
            "gestor": "Maria da Silva",
            "telefone": "(83) 99999-9999",
            "monitoramento": "True",
            "botao_panico": "False",
            "quantidade_alunos": 500,
            "quantidade_alunos_pcd": 20,
            "modalidade": "Ensino Fundamental",
            "observacoes": "Escola utilizada nos testes.",
        }

    def test_formulario_escola_valido(self):
        """Verifica se dados corretos geram um formulário válido."""

        form = EscolaForm(
            data=self.dados_validos()
        )

        self.assertTrue(
            form.is_valid()
        )

    def test_nome_escola_duplicado(self):
        """Não permite cadastrar duas escolas com o mesmo nome."""

        Escola.objects.create(
            nome="Escola Municipal Nova",
            polo="1",
            endereco="Rua Teste",
            bairro="Centro",
            gestor="Gestor Teste",
            telefone="123456789",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=100,
            quantidade_alunos_pcd=5,
            modalidade="Ensino Fundamental",
        )

        form = EscolaForm(
            data=self.dados_validos()
        )

        self.assertFalse(
            form.is_valid()
        )

        self.assertIn(
            "nome",
            form.errors
        )

    def test_nome_duplicado_ignora_maiusculas_minusculas(self):
        """Impede duplicidade mesmo com diferença entre maiúsculas e minúsculas."""

        Escola.objects.create(
            nome="ESCOLA MUNICIPAL NOVA",
            polo="1",
            endereco="Rua Teste",
            bairro="Centro",
            gestor="Gestor Teste",
            telefone="123456789",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=100,
            quantidade_alunos_pcd=5,
            modalidade="Ensino Fundamental",
        )

        dados = self.dados_validos()
        dados["nome"] = "escola municipal nova"

        form = EscolaForm(
            data=dados
        )

        self.assertFalse(
            form.is_valid()
        )

        self.assertIn(
            "nome",
            form.errors
        )

    def test_alunos_pcd_maior_que_total(self):
        """Não permite quantidade de alunos PCD maior que o total."""

        dados = self.dados_validos()

        dados["quantidade_alunos"] = 100
        dados["quantidade_alunos_pcd"] = 101

        form = EscolaForm(
            data=dados
        )

        self.assertFalse(
            form.is_valid()
        )

        self.assertIn(
            "quantidade_alunos_pcd",
            form.errors
        )

    def test_quantidade_alunos_negativa(self):
        """Não permite quantidade negativa de alunos."""

        dados = self.dados_validos()
        dados["quantidade_alunos"] = -1

        form = EscolaForm(
            data=dados
        )

        self.assertFalse(
            form.is_valid()
        )

        self.assertIn(
            "quantidade_alunos",
            form.errors
        )

class ProblematicaModelTest(TestCase):

    def setUp(self):
        self.escola = Escola.objects.create(
            nome="Escola Municipal Teste Problemática",
            polo="2",
            endereco="Rua Teste, 200",
            bairro="Centro",
            gestor="João da Silva",
            telefone="(83) 99999-9999",
            monitoramento=True,
            botao_panico=False,
            quantidade_alunos=300,
            quantidade_alunos_pcd=5,
            modalidade="Ensino Fundamental",
            ativa=True,
        )

        self.tipo_problematica = TipoProblematica.objects.create(
            nome="Bullying",
            descricao="Situações relacionadas a bullying.",
            ativa=True,
        )

        self.problematica = EscolaProblematica.objects.create(
            escola=self.escola,
            tipo_problematica=self.tipo_problematica,
            observacoes="Problemática identificada na escola.",
        )

    def test_criar_tipo_problematica(self):
        """Verifica a criação de um tipo de problemática."""

        self.assertEqual(
            TipoProblematica.objects.count(),
            1
        )

    def test_criar_problematica_escola(self):
        """Verifica o registro de uma problemática para uma escola."""

        self.assertEqual(
            EscolaProblematica.objects.count(),
            1
        )

    def test_problematica_associada_escola(self):
        """Verifica se a problemática pertence à escola correta."""

        self.assertEqual(
            self.problematica.escola,
            self.escola
        )

    def test_situacao_padrao_problematica(self):
        """Verifica se uma nova problemática inicia como ativa."""

        self.assertEqual(
            self.problematica.situacao,
            "ATIVA"
        )

    def test_str_tipo_problematica(self):
        """Verifica a representação textual do tipo."""

        self.assertEqual(
            str(self.tipo_problematica),
            "Bullying"
        )

    def test_str_escola_problematica(self):
        """Verifica a representação textual da problemática da escola."""

        esperado = (
            "Escola Municipal Teste Problemática - Bullying"
        )

        self.assertEqual(
            str(self.problematica),
            esperado
        )
    def test_nao_permite_problematica_duplicada_na_mesma_escola(self):
        """Não permite a mesma problemática duas vezes na mesma escola."""

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
             EscolaProblematica.objects.create(
                escola=self.escola,
                tipo_problematica=self.tipo_problematica,
                observacoes="Tentativa de registro duplicado.",
            )

class EscolaViewsTest(TestCase):

    def setUp(self):
        self.escola = Escola.objects.create(
            nome="Escola Teste Views",
            polo=1,
            endereco="Rua das Flores, 100",
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

        self.tipo_problematica = TipoProblematica.objects.create(
            nome="Bullying",
            descricao="Situações relacionadas a bullying.",
            ativa=True,
        )

    def dados_escola(self):
        return {
            "nome": "Nova Escola Municipal",
            "polo": "2",
            "endereco": "Rua Nova, 200",
            "bairro": "Bancários",
            "gestor": "João da Silva",
            "telefone": "(83) 98888-8888",
            "monitoramento": "True",
            "botao_panico": "False",
            "quantidade_alunos": 400,
            "quantidade_alunos_pcd": 15,
            "modalidade": "Ensino Fundamental",
            "observacoes": "Cadastro realizado durante teste.",
        }

    def test_listar_escolas(self):
        """Verifica se a página de escolas é carregada."""

        response = self.client.get(
            reverse("escolas:listar_escolas")
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            "Escola Teste Views"
        )

    def test_filtro_escolas_ativas(self):
        """Verifica se o filtro padrão apresenta escolas ativas."""

        Escola.objects.create(
            nome="Escola Inativa Teste",
            polo=2,
            endereco="Rua B",
            bairro="Centro",
            gestor="Gestor",
            ativa=False,
        )

        response = self.client.get(
            reverse("escolas:listar_escolas")
        )

        self.assertContains(
            response,
            "Escola Teste Views"
        )

        self.assertNotContains(
            response,
            "Escola Inativa Teste"
        )

    def test_filtro_escolas_inativas(self):
        """Verifica o filtro de escolas inativas."""

        escola_inativa = Escola.objects.create(
            nome="Escola Inativa Teste",
            polo=2,
            endereco="Rua B",
            bairro="Centro",
            gestor="Gestor",
            ativa=False,
        )

        response = self.client.get(
            reverse("escolas:listar_escolas"),
            {
                "situacao": "inativas"
            }
        )

        self.assertContains(
            response,
            escola_inativa.nome
        )

        self.assertNotContains(
            response,
            self.escola.nome
        )

    def test_busca_escola_por_nome(self):
        """Verifica a pesquisa de escola pelo nome."""

        response = self.client.get(
            reverse("escolas:listar_escolas"),
            {
                "busca": "Teste Views"
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            "Escola Teste Views"
        )

    def test_filtro_escola_por_polo(self):
        """Verifica o filtro de escolas por polo."""

        response = self.client.get(
            reverse("escolas:listar_escolas"),
            {
                "polo": "1"
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            self.escola.nome
        )

    def test_detalhe_escola(self):
        """Verifica a página de detalhes da escola."""

        response = self.client.get(
            reverse(
                "escolas:detalhe_escola",
                kwargs={
                    "pk": self.escola.pk
                }
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response.context["escola"],
            self.escola
        )

    def test_cadastrar_escola(self):
        """Verifica o cadastro de uma escola pela view."""

        response = self.client.post(
            reverse("escolas:cadastrar_escola"),
            data=self.dados_escola()
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertTrue(
            Escola.objects.filter(
                nome="Nova Escola Municipal"
            ).exists()
        )

    def test_editar_escola(self):
        """Verifica a edição de uma escola."""

        dados = self.dados_escola()

        dados["nome"] = "Escola Teste Views Atualizada"

        response = self.client.post(
            reverse(
                "escolas:editar_escola",
                kwargs={
                    "pk": self.escola.pk
                }
            ),
            data=dados
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.escola.refresh_from_db()

        self.assertEqual(
            self.escola.nome,
            "Escola Teste Views Atualizada"
        )

    def test_cadastrar_problematica(self):
        """Verifica o registro de problemática pela view."""

        response = self.client.post(
            reverse(
                "escolas:cadastrar_problematica",
                kwargs={
                    "pk": self.escola.pk
                }
            ),
            data={
                "tipo_problematica": self.tipo_problematica.pk,
                "situacao": "ATIVA",
                "observacoes": "Problemática identificada.",
            }
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertTrue(
            EscolaProblematica.objects.filter(
                escola=self.escola,
                tipo_problematica=self.tipo_problematica
            ).exists()
        )

    def test_editar_problematica(self):
        """Verifica a edição de uma problemática."""

        problematica = EscolaProblematica.objects.create(
            escola=self.escola,
            tipo_problematica=self.tipo_problematica,
            situacao="ATIVA",
        )

        response = self.client.post(
            reverse(
                "escolas:editar_problematica",
                kwargs={
                    "escola_pk": self.escola.pk,
                    "problematica_pk": problematica.pk,
                }
            ),
            data={
                "tipo_problematica": self.tipo_problematica.pk,
                "situacao": "EM_ACOMPANHAMENTO",
                "observacoes": "Em acompanhamento pela equipe.",
            }
        )

        self.assertEqual(
            response.status_code,
            302
        )

        problematica.refresh_from_db()

        self.assertEqual(
            problematica.situacao,
            "EM_ACOMPANHAMENTO"
        )

    def test_excluir_problematica(self):
        """Verifica a exclusão da problemática da escola."""

        problematica = EscolaProblematica.objects.create(
            escola=self.escola,
            tipo_problematica=self.tipo_problematica,
        )

        response = self.client.post(
            reverse(
                "escolas:excluir_problematica",
                kwargs={
                    "escola_pk": self.escola.pk,
                    "problematica_pk": problematica.pk,
                }
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertFalse(
            EscolaProblematica.objects.filter(
                pk=problematica.pk
            ).exists()
        )

    def test_desativar_escola(self):
        """Verifica a desativação de uma escola."""

        response = self.client.post(
            reverse(
                "escolas:desativar_escola",
                kwargs={
                    "pk": self.escola.pk
                }
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.escola.refresh_from_db()

        self.assertFalse(
            self.escola.ativa
        )

    def test_ativar_escola(self):
        """Verifica a reativação de uma escola."""

        self.escola.ativa = False
        self.escola.save()

        response = self.client.post(
            reverse(
                "escolas:ativar_escola",
                kwargs={
                    "pk": self.escola.pk
                }
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.escola.refresh_from_db()

        self.assertTrue(
            self.escola.ativa
        )


