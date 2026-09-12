import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from escolas.models import (
    Escola,
    TipoProblematica,
    EscolaProblematica,
)


class Command(BaseCommand):
    help = "Importa o levantamento das escolas da RECOM a partir de PDF."

    TOTAL_ESPERADO = 106

    # ============================================================
    # BAIRROS DE ENDEREÇOS COM FORMATAÇÃO DIFERENTE NO PDF
    # ============================================================
    #
    # A maioria dos endereços segue:
    #
    # Rua X - número - Bairro
    #
    # Nesses casos o bairro é identificado automaticamente.
    #
    # Algumas escolas possuem endereço com vírgulas, travessões,
    # hífens ou outras formas de escrita. Para essas situações,
    # utilizamos o mapeamento abaixo, validado durante a conferência.
    #
    # EMAI Augusto e Joacil de Brito Pereira permanecem sem bairro,
    # porque o levantamento não permite identificá-lo com segurança.
    # ============================================================

    BAIRROS_ESPECIAIS = {
        "padre pedro serrão": "Cristo Redentor",
        "maria madalena guedes pereira": "Varjão",
        "prof. matheus ribeiro": "Varjão",
        "dr. severino patrício": "Alto do Mateus",
        "luiza lima lobo": "Alto do Mateus",
        "dom josé maria pires": "Alto do Mateus",
        "arnaldo de barros moreira": "Bairro dos Novais",
        "euclides da cunha": "Jardim Planalto",
        "quilombola antônia do socorro machado": "Paratibe",
        "cícero leite": "Valentina",
        "professor abrão alves de carvalho": "Muçu Magro",
        "radegundes feitosa nunes": "José Américo",
        "luiz augusto crispim": "Bairro dos Ipês",
        "fernandes vieira": "Bairro dos Ipês",
        "lynaldo cavalcante de albuquerque": "Bairro das Indústrias",
        "professor paulo freire": "Jardim Veneza",
        "nominando diniz": "Mumbaba",
        "duque de caxias": "Costa",
        "antenor navarro": "Gramame",
        "fernando milanez": "Gramame",
        "oscar de castro": "Cruz das Armas",

        # Casos conferidos após a primeira importação.
        "agostinho fonseca neto": "Cristo",
        "frei albino": "Bessa",
        "chico xavier": "Bessa",
        "em nazinha barbosa": "Manaíra",
        "seráfico da nóbrega": "Manaíra",
        "joão monteiro da franca": "Jardim Veneza",

        # O PDF não permite determinar o bairro com segurança.
        # Se o bairro for preenchido manualmente no sistema, o
        # importador preservará esse valor nas próximas importações.
        "olivio ribeiro campos": "",
        "rotary francisco": "",
        "angelo francisco": "",
    }

    # ============================================================
    # ARGUMENTOS
    # ============================================================

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo",
            type=str,
            help="Caminho do arquivo PDF.",
        )

        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma a gravação dos dados no banco.",
        )

    # ============================================================
    # EXECUÇÃO PRINCIPAL
    # ============================================================

    def handle(self, *args, **options):
        caminho = Path(options["arquivo"])
        confirmar = options["confirmar"]

        if not caminho.exists():
            raise CommandError(
                f"Arquivo não encontrado: {caminho}"
            )

        if caminho.suffix.lower() != ".pdf":
            raise CommandError(
                "O arquivo informado precisa ser um PDF."
            )

        if confirmar:
            self.stdout.write(
                self.style.WARNING(
                    "\nMODO DE IMPORTAÇÃO "
                    "- os dados serão gravados no banco.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nMODO DE TESTE "
                    "- nenhum dado será salvo no banco.\n"
                )
            )

        registros = self.extrair_registros(
            caminho
        )

        self.adicionar_francisca_moura(
            registros
        )

        escolas_por_polo = self.identificar_polos(
            registros
        )

        total = sum(
            len(escolas)
            for escolas in escolas_por_polo.values()
        )

        self.mostrar_resumo(
            escolas_por_polo,
            total,
        )

        if total != self.TOTAL_ESPERADO:
            raise CommandError(
                f"Foram identificadas {total} escolas, "
                f"mas eram esperadas {self.TOTAL_ESPERADO}. "
                "A importação foi cancelada."
            )

        if len(escolas_por_polo) != 9:
            raise CommandError(
                "Não foram identificados exatamente 9 polos. "
                "A importação foi cancelada."
            )

        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    "\nNenhum dado foi gravado no banco."
                )
            )

            self.stdout.write(
                "\nPara gravar os dados, execute:"
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "python manage.py importar_escolas "
                    "dados\\levantamento_escolas.pdf --confirmar"
                )
            )

            return

        self.importar_para_banco(
            escolas_por_polo
        )

    # ============================================================
    # LEITURA DO PDF
    # ============================================================

    def extrair_registros(self, caminho):
        registros = []

        with pdfplumber.open(caminho) as pdf:
            self.stdout.write(
                f"PDF aberto com sucesso: "
                f"{len(pdf.pages)} páginas."
            )

            for numero_pagina, pagina in enumerate(
                pdf.pages,
                start=1,
            ):
                tabelas = pagina.extract_tables()

                if not tabelas:
                    continue

                for tabela in tabelas:
                    for linha in tabela:
                        if not linha:
                            continue

                        linha_limpa = [
                            self.limpar_texto(celula)
                            for celula in linha
                        ]

                        if not any(linha_limpa):
                            continue

                        if self.eh_cabecalho(
                            linha_limpa
                        ):
                            continue

                        numero = (
                            linha_limpa[0]
                            if linha_limpa
                            else ""
                        )

                        if not re.fullmatch(
                            r"\d+",
                            numero,
                        ):
                            continue

                        # Garante no mínimo 11 colunas.
                        while len(linha_limpa) < 11:
                            linha_limpa.append("")

                        registros.append(
                            {
                                "pagina": numero_pagina,
                                "numero": int(numero),
                                "nome": linha_limpa[1],
                                "colunas": linha_limpa,
                            }
                        )

        return registros

    # ============================================================
    # FRANCISCA MOURA
    # ============================================================
    #
    # A linha nº 1 do Polo 6 não foi reconhecida corretamente pelo
    # pdfplumber. Os dados foram conferidos visualmente no PDF.
    # ============================================================

    def adicionar_francisca_moura(self, registros):
        existe = any(
            self.normalizar_nome(
                registro["nome"]
            )
            == self.normalizar_nome(
                "Francisca Moura"
            )
            for registro in registros
        )

        if existe:
            return

        francisca = {
            "pagina": 27,
            "numero": 1,
            "nome": "Francisca Moura",
            "colunas": [
                "1",
                "Francisca Moura",
                "Rua Silvino Santos - 27 - Mandacaru",
                "SIM",
                "SIM",
                "560",
                "25",
                "Cíntia Brandão",
                "83 9 9912-9293",
                "Fund II e EJA",
                (
                    "Ciberbullying; "
                    "Pais vinculados a facções criminosas; "
                    "Muro com risco estrutural de desabamento; "
                    "Necessidade de ampliação do sistema "
                    "de monitoramento."
                ),
            ],
            "adicionado_manualmente": True,
        }

        posicao = None

        for indice, registro in enumerate(
            registros
        ):
            if (
                registro["numero"] == 2
                and self.normalizar_nome(
                    registro["nome"]
                )
                == self.normalizar_nome(
                    "José de Barros Moreira"
                )
            ):
                posicao = indice
                break

        if posicao is not None:
            registros.insert(
                posicao,
                francisca,
            )
        else:
            registros.append(
                francisca
            )

        self.stdout.write(
            self.style.WARNING(
                "Francisca Moura foi recuperada "
                "porque sua linha não foi extraída "
                "automaticamente do PDF."
            )
        )

    # ============================================================
    # IDENTIFICAÇÃO DOS POLOS
    # ============================================================

    def identificar_polos(self, registros):
        polo_atual = 1
        numero_anterior = None

        escolas_por_polo = defaultdict(
            list
        )

        for registro in registros:
            numero = registro["numero"]

            if (
                numero == 1
                and numero_anterior is not None
                and numero_anterior != 1
            ):
                polo_atual += 1

            registro["polo"] = polo_atual

            escolas_por_polo[
                polo_atual
            ].append(
                registro
            )

            numero_anterior = numero

        return escolas_por_polo

    # ============================================================
    # IMPORTAÇÃO PARA O BANCO
    # ============================================================

    @transaction.atomic
    def importar_para_banco(
        self,
        escolas_por_polo,
    ):
        criadas = 0
        atualizadas = 0
        problematicas_criadas = 0

        self.stdout.write(
            "\n" + "=" * 70
        )

        self.stdout.write(
            self.style.WARNING(
                "\nINICIANDO GRAVAÇÃO NO BANCO\n"
            )
        )

        for polo in sorted(
            escolas_por_polo
        ):
            for registro in escolas_por_polo[
                polo
            ]:
                dados = self.converter_registro(
                    registro,
                    polo,
                )

                nome = dados["nome"]

                escola = Escola.objects.filter(
                    nome__iexact=nome
                ).first()

                if escola:
                    self.atualizar_escola(
                        escola,
                        dados,
                    )

                    atualizadas += 1
                    acao = "ATUALIZADA"

                else:
                    escola = Escola.objects.create(
                        nome=dados["nome"],
                        polo=dados["polo"],
                        endereco=dados["endereco"],
                        bairro=dados["bairro"],
                        gestor=dados["gestor"],
                        telefone=dados["telefone"],
                        monitoramento=dados[
                            "monitoramento"
                        ],
                        botao_panico=dados[
                            "botao_panico"
                        ],
                        quantidade_alunos=dados[
                            "quantidade_alunos"
                        ],
                        quantidade_alunos_pcd=dados[
                            "quantidade_alunos_pcd"
                        ],
                        modalidade=dados[
                            "modalidade"
                        ],
                        observacoes="",
                        ativa=True,
                    )

                    criadas += 1
                    acao = "CRIADA"

                quantidade = (
                    self.importar_problematicas(
                        escola,
                        dados[
                            "problematica_original"
                        ],
                    )
                )

                problematicas_criadas += (
                    quantidade
                )

                bairro_exibicao = (
                    escola.bairro
                    if escola.bairro
                    else "Não informado"
                )

                self.stdout.write(
                    f"[{acao}] "
                    f"Polo {polo} | "
                    f"{registro['numero']} | "
                    f"{nome} | "
                    f"Bairro: {bairro_exibicao}"
                )

        self.stdout.write(
            "\n" + "=" * 70
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\nIMPORTAÇÃO CONCLUÍDA COM SUCESSO"
            )
        )

        self.stdout.write(
            f"Escolas criadas: {criadas}"
        )

        self.stdout.write(
            f"Escolas atualizadas: {atualizadas}"
        )

        self.stdout.write(
            f"Total processado: "
            f"{criadas + atualizadas}"
        )

        self.stdout.write(
            "Novos vínculos de problemáticas: "
            f"{problematicas_criadas}"
        )

        total_banco = Escola.objects.count()

        sem_bairro = Escola.objects.filter(
            bairro=""
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                "Total de escolas atualmente "
                f"no banco: {total_banco}"
            )
        )

        self.stdout.write(
            f"Escolas sem bairro informado: "
            f"{sem_bairro}"
        )

    # ============================================================
    # ATUALIZAÇÃO DE ESCOLA EXISTENTE
    # ============================================================

    def atualizar_escola(
        self,
        escola,
        dados,
    ):
        escola.polo = dados["polo"]
        escola.endereco = dados["endereco"]
        escola.gestor = dados["gestor"]
        escola.telefone = dados["telefone"]

        escola.monitoramento = dados[
            "monitoramento"
        ]

        escola.botao_panico = dados[
            "botao_panico"
        ]

        escola.quantidade_alunos = dados[
            "quantidade_alunos"
        ]

        escola.quantidade_alunos_pcd = dados[
            "quantidade_alunos_pcd"
        ]

        escola.modalidade = dados[
            "modalidade"
        ]

        escola.ativa = True

        # --------------------------------------------------------
        # BAIRRO
        # --------------------------------------------------------
        #
        # Se o PDF permitir identificar o bairro,
        # atualizamos o campo.
        #
        # Se o PDF não trouxer bairro e a escola já possuir
        # um bairro preenchido manualmente, preservamos o valor.
        # --------------------------------------------------------

        if dados["bairro"]:
            escola.bairro = dados["bairro"]

        # --------------------------------------------------------
        # OBSERVAÇÕES
        # --------------------------------------------------------
        #
        # O importador NÃO preenche observações.
        #
        # Também não apagamos automaticamente uma observação
        # que eventualmente seja cadastrada manualmente no futuro.
        # --------------------------------------------------------

        escola.save()

    # ============================================================
    # CONVERSÃO DE UMA LINHA DO PDF
    # ============================================================

    def converter_registro(
        self,
        registro,
        polo,
    ):
        colunas = registro["colunas"]

        nome = self.valor_coluna(
            colunas,
            1,
        )

        endereco = self.valor_coluna(
            colunas,
            2,
        )

        monitoramento_original = (
            self.valor_coluna(
                colunas,
                3,
            )
        )

        botao_original = self.valor_coluna(
            colunas,
            4,
        )

        quantidade_original = (
            self.valor_coluna(
                colunas,
                5,
            )
        )

        pcd_original = self.valor_coluna(
            colunas,
            6,
        )

        gestor = self.valor_coluna(
            colunas,
            7,
        )

        telefone = self.valor_coluna(
            colunas,
            8,
        )

        modalidade = self.valor_coluna(
            colunas,
            9,
        )

        problematica = self.valor_coluna(
            colunas,
            10,
        )

        bairro = self.extrair_bairro(
            nome,
            endereco,
        )

        endereco_sem_bairro = (
            self.remover_bairro_do_endereco(
                endereco,
                bairro,
            )
        )

        monitoramento = (
            self.converter_sim_nao(
                monitoramento_original
            )
        )

        botao_panico = (
            self.converter_sim_nao(
                botao_original
            )
        )

        quantidade_alunos = (
            self.converter_quantidade(
                quantidade_original
            )
        )

        quantidade_pcd = (
            self.converter_quantidade(
                pcd_original
            )
        )

        return {
            "nome": nome,
            "polo": str(polo),
            "endereco": endereco_sem_bairro,
            "bairro": bairro,
            "gestor": gestor,
            "telefone": telefone,
            "monitoramento": monitoramento,
            "botao_panico": botao_panico,
            "quantidade_alunos": (
                quantidade_alunos
            ),
            "quantidade_alunos_pcd": (
                quantidade_pcd
            ),
            "modalidade": modalidade,
            "problematica_original": (
                problematica
            ),
        }

    # ============================================================
    # ENDEREÇO E BAIRRO
    # ============================================================

    def extrair_bairro(
        self,
        nome,
        endereco,
    ):
        """
        Identifica o bairro da escola.

        Regra 1:
        Verifica se a escola possui tratamento especial.

        Regra 2:
        Para endereços no padrão:
        Rua X - 123 - Bairro
        utiliza o texto após o último ' - '.

        Caso não seja possível identificar com segurança,
        retorna string vazia.
        """

        nome_normalizado = (
            self.normalizar_nome(
                nome
            )
        )

        # --------------------------------------------------------
        # CASOS ESPECIAIS JÁ CONFERIDOS
        # --------------------------------------------------------

        if (
            nome_normalizado
            in self.BAIRROS_ESPECIAIS
        ):
            return self.BAIRROS_ESPECIAIS[
                nome_normalizado
            ]

        endereco = self.limpar_texto(
            endereco
        )

        if not endereco:
            return ""

        # --------------------------------------------------------
        # PADRÃO MAIS COMUM DO PDF
        #
        # Exemplo:
        #
        # Rua Emílio de Araújo Chaves - 118 - Altiplano
        #
        # Resultado:
        #
        # Altiplano
        # --------------------------------------------------------

        if " - " in endereco:
            partes = endereco.rsplit(
                " - ",
                1,
            )

            if len(partes) == 2:
                bairro = partes[1].strip()

                if self.bairro_valido(
                    bairro
                ):
                    return bairro

        # --------------------------------------------------------
        # TRAVESSÃO
        #
        # Alguns registros utilizam:
        #
        # Rua X – Bairro
        #
        # --------------------------------------------------------

        if " – " in endereco:
            partes = endereco.rsplit(
                " – ",
                1,
            )

            if len(partes) == 2:
                bairro = partes[1].strip()

                if self.bairro_valido(
                    bairro
                ):
                    return bairro

        # --------------------------------------------------------
        # Se nenhuma regra for segura, não inventamos o bairro.
        # --------------------------------------------------------

        return ""

    def remover_bairro_do_endereco(
        self,
        endereco,
        bairro,
    ):
        """
        Remove do campo de endereço o bairro que já foi identificado
        e será salvo separadamente.

        A remoção só acontece quando o bairro aparece no final do
        endereço. Assim preservamos rua, número, s/n e complementos.

        Exemplos:

        Rua Emílio de Araújo Chaves - 118 - Altiplano
        -> Rua Emílio de Araújo Chaves - 118

        Av. Dom Bosco, 755, Cristo Redentor
        -> Av. Dom Bosco, 755

        Av. Goiania, Gravatá (Valentina)
        -> Av. Goiania, Gravatá
        """

        endereco = self.limpar_texto(
            endereco
        )

        bairro = self.limpar_texto(
            bairro
        )

        if not endereco or not bairro:
            return endereco

        bairro_escapado = re.escape(
            bairro
        )

        padroes = [
            # Rua X - Bairro / Rua X – Bairro / Rua X — Bairro
            rf"\s*[-–—]\s*{bairro_escapado}\s*$",

            # Rua X, Bairro
            rf"\s*,\s*{bairro_escapado}\s*$",

            # Rua X (Bairro)
            rf"\s*\(\s*{bairro_escapado}\s*\)\s*$",
        ]

        for padrao in padroes:
            endereco_limpo = re.sub(
                padrao,
                "",
                endereco,
                flags=re.IGNORECASE,
            ).strip(
                " ,;-–—"
            )

            # Nunca transformamos um endereço válido em vazio.
            if (
                endereco_limpo
                and endereco_limpo != endereco
            ):
                return endereco_limpo

        return endereco

    def bairro_valido(self, bairro):
        """
        Evita gravar como bairro valores claramente inválidos.

        Essa validação também impede que número do imóvel,
        "s/n" ou trechos de endereço sejam confundidos com bairro.
        """

        bairro = self.limpar_texto(
            bairro
        )

        if not bairro:
            return False

        valores_invalidos = {
            "-",
            "--",
            "---",
            "s/n",
            "sn",
            "não informado",
            "nao informado",
        }

        bairro_normalizado = bairro.casefold()

        if bairro_normalizado in valores_invalidos:
            return False

        # Exemplos inválidos encontrados no PDF:
        # "195 -", "516 -", "4455, Bessa" e
        # "43 – Jardim Veneza".
        if re.search(
            r"\d",
            bairro,
        ):
            return False

        # Evita valores iniciados por s/n, como:
        # "s/n., Bessa".
        if re.match(
            r"^s\s*/?\s*n\b",
            bairro_normalizado,
        ):
            return False

        # Abreviações muito curtas, como "Jd.", não são
        # consideradas seguras para preenchimento automático.
        if len(
            bairro.strip()
        ) <= 3:
            return False

        return True

    # ============================================================
    # ACESSO ÀS COLUNAS
    # ============================================================

    def valor_coluna(
        self,
        colunas,
        indice,
    ):
        if indice >= len(colunas):
            return ""

        return self.limpar_texto(
            colunas[indice]
        )

    # ============================================================
    # QUANTIDADE DE ALUNOS
    # ============================================================

    def converter_quantidade(
        self,
        valor,
    ):
        valor = self.limpar_texto(
            valor
        )

        if self.eh_valor_ausente(
            valor
        ):
            return 0

        # Exemplo:
        # 900 +300 =1,200
        #
        # Utilizamos o valor após o "=".
        if "=" in valor:
            valor = valor.split(
                "="
            )[-1]

        valor = valor.strip()

        valor = valor.replace(
            " ",
            "",
        )

        # Exemplos:
        # 1.510
        # 1.200
        # 1,200
        valor = valor.replace(
            ".",
            "",
        )

        valor = valor.replace(
            ",",
            "",
        )

        numeros = re.findall(
            r"\d+",
            valor,
        )

        if not numeros:
            return 0

        try:
            return int(
                "".join(numeros)
            )

        except ValueError:
            return 0

    # ============================================================
    # CAMPOS SIM / NÃO
    # ============================================================

    def converter_sim_nao(
        self,
        valor,
    ):
        valor = self.limpar_texto(
            valor
        )

        valor_normalizado = (
            valor
            .casefold()
            .strip()
        )

        if valor_normalizado.startswith(
            "sim"
        ):
            return True

        if (
            valor_normalizado.startswith(
                "não"
            )
            or valor_normalizado.startswith(
                "nao"
            )
        ):
            return False

        return False

    # ============================================================
    # VALORES AUSENTES
    # ============================================================

    def eh_valor_ausente(
        self,
        valor,
    ):
        valor = self.limpar_texto(
            valor
        )

        if not valor:
            return True

        sem_tracos = valor.replace(
            "-",
            "",
        ).strip()

        return not sem_tracos

    # ============================================================
    # PROBLEMÁTICAS
    # ============================================================

    def importar_problematicas(
        self,
        escola,
        texto_original,
    ):
        texto_original = self.limpar_texto(
            texto_original
        )

        if self.eh_valor_ausente(
            texto_original
        ):
            return 0

        categorias = (
            self.identificar_problematicas(
                texto_original
            )
        )

        criadas = 0

        for nome_categoria in categorias:
            tipo, _ = (
                TipoProblematica.objects.get_or_create(
                    nome=nome_categoria
                )
            )

            _, criada = (
                EscolaProblematica.objects.get_or_create(
                    escola=escola,
                    tipo_problematica=tipo,
                    defaults={
                        "situacao": "ATIVA",
                        "observacoes": "",
                    },
                )
            )

            if criada:
                criadas += 1

        # --------------------------------------------------------
        # Se o texto não corresponder a nenhuma categoria conhecida,
        # cria vínculo com "Outras", sem preencher observações.
        # --------------------------------------------------------

        if not categorias:
            tipo, _ = (
                TipoProblematica.objects.get_or_create(
                    nome="Outras"
                )
            )

            _, criada = (
                EscolaProblematica.objects.get_or_create(
                    escola=escola,
                    tipo_problematica=tipo,
                    defaults={
                        "situacao": "ATIVA",
                        "observacoes": "",
                    },
                )
            )

            if criada:
                criadas += 1

        return criadas

    # ============================================================
    # CLASSIFICAÇÃO DAS PROBLEMÁTICAS
    # ============================================================

    def identificar_problematicas(
        self,
        texto,
    ):
        texto = self.normalizar_texto(
            texto
        )

        mapa = {
            "Bullying": [
                "bullying",
                "bullyng",
                "bulling",
            ],

            "Cyberbullying": [
                "cyberbullying",
                "ciberbullying",
                "ciberbullyng",
                "ciberbulling",
            ],

            "Drogas": [
                "droga",
                "drogas",
                "trafico",
                "tráfico",
                "entorpecente",
            ],

            "Racismo": [
                "racismo",
                "racista",
            ],

            "Violência / Agressões": [
                "violencia",
                "violência",
                "agressao",
                "agressão",
                "agressoes",
                "agressões",
                "briga",
                "brigas",
            ],

            "Indisciplina": [
                "indisciplina",
                "indisciplinado",
                "indisciplinados",
            ],

            "Furto / Roubo": [
                "furto",
                "furtos",
                "roubo",
                "roubos",
                "assalto",
                "assaltos",
            ],

            "Dano ao patrimônio": [
                "dano ao patrimonio",
                "dano ao patrimônio",
                "pichacao",
                "pichação",
                "pixacao",
                "pixação",
            ],

            "Facções": [
                "faccao",
                "facção",
                "faccoes",
                "facções",
                "faccionado",
                "faccionados",
            ],

            "Armas": [
                "arma",
                "armas",
                "arma branca",
            ],

            "Vulnerabilidade social": [
                "vulnerabilidade",
                "situacao de rua",
                "situação de rua",
                "medida socioeducativa",
            ],

            "Problemas estruturais": [
                "estrutura",
                "estrutural",
                "reforma",
                "muro",
                "iluminacao",
                "iluminação",
                "portao",
                "portão",
                "obra",
            ],

            "Ameaças": [
                "ameaca",
                "ameaça",
                "ameacas",
                "ameaças",
            ],
        }

        encontradas = []

        for categoria, termos in mapa.items():
            if any(
                termo in texto
                for termo in termos
            ):
                encontradas.append(
                    categoria
                )

        return encontradas

    # ============================================================
    # RESUMO
    # ============================================================

    def mostrar_resumo(
        self,
        escolas_por_polo,
        total,
    ):
        self.stdout.write(
            "\n" + "=" * 70
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\nRESUMO POR POLO"
            )
        )

        self.stdout.write(
            "=" * 70
        )

        for polo in sorted(
            escolas_por_polo
        ):
            registros = escolas_por_polo[
                polo
            ]

            numeros = [
                registro["numero"]
                for registro in registros
            ]

            self.stdout.write(
                f"\nPolo {polo}: "
                f"{len(registros)} escolas"
            )

            self.stdout.write(
                "Números: "
                + ", ".join(
                    map(
                        str,
                        numeros,
                    )
                )
            )

        self.stdout.write(
            "\n" + "-" * 70
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal identificado: {total}"
            )
        )

        if total == self.TOTAL_ESPERADO:
            self.stdout.write(
                self.style.SUCCESS(
                    "Total esperado confirmado: "
                    f"{self.TOTAL_ESPERADO}"
                )
            )

    # ============================================================
    # FUNÇÕES AUXILIARES
    # ============================================================

    def limpar_texto(
        self,
        valor,
    ):
        if valor is None:
            return ""

        valor = str(
            valor
        )

        valor = valor.replace(
            "\n",
            " ",
        )

        valor = valor.replace(
            "\r",
            " ",
        )

        valor = re.sub(
            r"\s+",
            " ",
            valor,
        )

        return valor.strip()

    def normalizar_nome(
        self,
        valor,
    ):
        return self.limpar_texto(
            valor
        ).casefold()

    def normalizar_texto(
        self,
        valor,
    ):
        return self.limpar_texto(
            valor
        ).casefold()

    def eh_cabecalho(
        self,
        linha,
    ):
        texto = " ".join(
            linha
        ).lower()

        termos = [
            "escola endereço",
            "monitoramento",
            "botão do pânico",
            "gestores telefone",
            "modalidade problemática",
        ]

        return any(
            termo in texto
            for termo in termos
        )