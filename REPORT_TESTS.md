# Relatório de execução dos testes funcionais — Sprint 1

## Identificação

- **Projeto:** RECOM — Ronda Escolar Comunitária
- **Sprint:** 1
- **Data da execução:** 21/10/2026
- **Ferramenta:** Pytest 9.1.1 com pytest-django 4.14.0
- **Aplicação:** Django 6.0.3
- **Plataforma da execução:** Windows, Python 3.13.14

## Objetivo

Registrar o resultado da execução dos testes funcionais das funcionalidades
entregues na sprint 1:

- F01 — Cadastro e consulta de escolas;
- F02 — Problemáticas das escolas;
- F03 — Acompanhamento de visitas escolares;
- F04 — Visão inicial da atuação da RECOM.

## Especificação dos testes funcionais

Os casos abaixo descrevem o comportamento esperado antes da execução. Casos
parametrizados são executados mais de uma vez com dados diferentes, por isso a
quantidade de execuções é maior que a quantidade de casos especificados.

### F01 — Cadastro e consulta de escolas

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F01-01 | CA01.1 | Acessar o sistema | Abrir o cadastro de escola | O formulário apresenta Nome, Polo, Endereço, Gestor, Telefone, Monitoramento, Botão do Pânico, quantidades de alunos, Modalidade e Observações |
| CT-F01-02 | CA01.2 | Preparar um cadastro válido | Enviar separadamente Nome, Polo ou Endereço vazio | O campo é indicado como obrigatório e nenhuma escola é criada |
| CT-F01-03 | CA01.3 | Existir uma escola cadastrada | Enviar novo cadastro com o mesmo nome, mesmo alterando maiúsculas e minúsculas | O sistema informa a duplicidade e mantém apenas o registro original |
| CT-F01-04 | CA01.4 | Abrir o cadastro | Consultar as opções de Polo | São apresentadas somente as opções Polo 1 a Polo 9 |
| CT-F01-05 | CA01.5 | Abrir o cadastro | Consultar Monitoramento e Botão do Pânico | Ambos os campos apresentam somente Sim e Não |
| CT-F01-06 | CA01.6 | Preparar um cadastro válido | Informar valores negativos ou fracionários nas quantidades | O sistema rejeita os valores e não cria a escola |
| CT-F01-07 | CA01.7 e CA02.1 | Preparar dados válidos | Confirmar o cadastro e acessar a consulta | A escola é persistida e aparece na listagem |
| CT-F01-08 | CA02.2 | Existir uma escola cadastrada | Abrir os detalhes da escola selecionada | Os dados registrados são apresentados corretamente |
| CT-F01-09 | CA02.3 | Não existir escola cadastrada | Acessar a consulta | O sistema informa que nenhuma escola foi encontrada |

### F02 — Problemáticas das escolas

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F02-01 | CA03.1 | Não existir a escola indicada | Tentar acessar ou enviar o registro de problemática | O sistema impede a operação e nenhuma problemática é criada |
| CT-F02-02 | CA03.2–CA03.6 | Existir escola e tipo de problemática cadastrados | Informar tipo, situação e observações e confirmar | A problemática é persistida, vinculada à escola e disponibilizada para consulta |
| CT-F02-03 | CA03.3 | A escola já possuir uma problemática | Registrar uma problemática de outro tipo | Os dois registros permanecem vinculados à mesma escola |
| CT-F02-04 | CA04.1, CA04.2 e CA04.4 | Duas escolas possuírem problemáticas diferentes | Consultar uma das escolas | São exibidos tipo, situação e observações somente das problemáticas da escola selecionada |
| CT-F02-05 | CA04.3 | A escola não possuir problemáticas | Consultar seus detalhes | O sistema informa que não existem problemáticas registradas |

### F03 — Acompanhamento de visitas escolares

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F03-01 | CA05.1 | Preparar os demais dados da visita | Enviar o formulário sem selecionar escola | O sistema indica a obrigatoriedade e não cria a visita |
| CT-F03-02 | CA05.2 | Usuário coordenador autenticado | Abrir o registro de visita | O formulário disponibiliza campos obrigatórios de data e horário |
| CT-F03-03 | CA05.3 | Usuário coordenador autenticado | Consultar as opções de equipe | O formulário permite identificar a equipe responsável |
| CT-F03-04 | CA05.4 | Usuário coordenador autenticado | Abrir o registro de visita | O formulário disponibiliza situação encontrada e relato |
| CT-F03-05 | CA05.5 | Usuário coordenador autenticado | Abrir o registro de visita | O formulário disponibiliza o campo de providências adotadas |
| CT-F03-06 | CA05.6 | Usuário coordenador autenticado | Abrir o registro de visita | O formulário disponibiliza campo específico de observações complementares |
| CT-F03-07 | CA05.7 e CA05.8 | Existir uma escola cadastrada | Enviar uma visita válida e consultar a escola | A visita é vinculada à escola e incluída em seu histórico |
| CT-F03-08 | CA06.1, CA06.2 e CA06.5 | Duas escolas possuírem visitas diferentes | Consultar o histórico de uma escola | São exibidos data, horário, equipe, situação, relato e providências somente das visitas da escola selecionada |
| CT-F03-09 | CA06.3 | A escola possuir visitas em datas diferentes | Consultar o histórico | As visitas aparecem da mais recente para a mais antiga |
| CT-F03-10 | CA06.4 | A escola não possuir visitas | Consultar o histórico | O sistema informa que não existem visitas registradas |

### F04 — Visão inicial da atuação da RECOM

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F04-01 | CA07.1, CA07.3 e CA07.5 | Existirem escolas, visitas e problemáticas | Acessar a visão gerencial | Os totais de escolas, visitas e problemáticas correspondem aos registros existentes |
| CT-F04-02 | CA07.2 | Duas escolas distintas possuírem visitas | Acessar a visão gerencial | O indicador Escolas Visitadas apresenta o valor 2, sem duplicar escola com mais de uma visita |
| CT-F04-03 | CA07.4 | Existirem problemáticas de tipos diferentes | Acessar a visão gerencial | Os tipos são apresentados pela frequência de registros |
| CT-F04-04 | CA07.6 | A visão começar sem registros | Criar escola, visita e problemática e atualizar a visão | Os indicadores passam a refletir os novos registros |
| CT-F04-05 | CA07.7 | Não existirem registros | Acessar a visão gerencial | Os indicadores apresentam zero e as tabelas informam a ausência de dados |

## Resultado geral

| Situação | Quantidade |
|---|---:|
| Testes executados | 36 |
| Aprovados | 34 |
| Reprovados | 2 |
| Não executados | 0 |
| Percentual de aprovação | 94,4% |

O comando terminou com código de saída `1`, pois foram identificadas duas
não conformidades funcionais.

## Resultado por módulo

| Módulo | Funcionalidades | Aprovados | Reprovados | Resultado |
|---|---|---:|---:|---|
| Gestão de Escolas | F01 e F02 | 21 | 0 | Aprovado |
| Rondas e Visitas | F03 | 9 | 1 | Reprovado |
| Visão Gerencial | F04 | 4 | 1 | Reprovado |
| **Total** | **F01 a F04** | **34** | **2** | **Reprovado** |

## Rastreabilidade dos critérios de aceitação

| Critérios | Descrição resumida | Resultado | Evidência |
|---|---|---|---|
| CA01.1–CA01.7 | Cadastro de escola, campos, opções e validações | Aprovado | Todos os testes de cadastro passaram |
| CA02.1–CA02.3 | Consulta, detalhe e ausência de escolas | Aprovado | Todos os testes de consulta passaram |
| CA03.1–CA03.6 | Registro e vínculo de problemáticas | Aprovado | Todos os testes de registro passaram |
| CA04.1–CA04.4 | Consulta das problemáticas por escola | Aprovado | Todos os testes de histórico passaram |
| CA05.1–CA05.5 | Dados e vínculo do registro de visita | Aprovado | Os campos implementados e suas regras passaram |
| CA05.6 | Observações complementares da visita | **Reprovado** | O formulário não contém o campo `observacoes` |
| CA05.7–CA05.8 | Persistência e inclusão da visita no histórico | Aprovado | O registro apareceu no histórico da escola |
| CA06.1–CA06.5 | Conteúdo, ordem, ausência e vínculo do histórico | Aprovado | Todos os testes do histórico passaram |
| CA07.1 | Quantidade total de escolas | Aprovado | O total correspondeu aos registros criados |
| CA07.2 | Quantidade de escolas com visitas | **Reprovado** | O indicador `escolas_com_visitas` não é calculado nem exibido |
| CA07.3–CA07.7 | Visitas, problemáticas, atualização e ausência de dados | Aprovado | Os demais indicadores corresponderam aos registros |

## Não conformidades encontradas

### NC-01 — Ausência do campo de observações complementares

- **Funcionalidade:** F03 — Acompanhamento de visitas escolares
- **Critério:** CA05.6
- **Teste:** `test_ca05_6_formulario_disponibiliza_observacoes_complementares`
- **Resultado esperado:** o formulário deve disponibilizar um campo específico
  para observações complementares.
- **Resultado obtido:** o formulário possui os campos `escola`, `equipe`,
  `data_visita`, `horario`, `tipo_visita`, `situacao`, `relato` e
  `orientacoes`, mas não possui `observacoes`.
- **Situação:** reprovado.

### NC-02 — Ausência do indicador de escolas visitadas

- **Funcionalidade:** F04 — Visão inicial da atuação da RECOM
- **Critério:** CA07.2
- **Teste:** `test_ca07_2_apresenta_quantidade_de_escolas_com_visitas`
- **Resultado esperado:** o dashboard deve calcular e apresentar a quantidade
  distinta de escolas que possuem visitas registradas.
- **Resultado obtido:** o contexto do dashboard não contém
  `escolas_com_visitas` e a interface não apresenta o indicador
  “Escolas Visitadas”.
- **Situação:** reprovado.

## BDDs verificados

| User Story | Cenário | Resultado |
|---|---|---|
| US01 | Cadastro com dados válidos | Aprovado |
| US01 | Campos obrigatórios | Aprovado |
| US01 | Escola já cadastrada | Aprovado |
| US02 | Consulta de escola cadastrada | Aprovado |
| US02 | Ausência de escolas cadastradas | Aprovado |
| US03 | Registro de problemática | Aprovado |
| US03 | Escola não informada | Aprovado conforme o vínculo definido pela URL |
| US03 | Múltiplas problemáticas | Aprovado |
| US04 | Consulta de problemáticas registradas | Aprovado |
| US04 | Ausência de problemáticas | Aprovado |
| US05 | Registro de visita | Aprovado |
| US05 | Escola não informada | Aprovado |
| US05 | Inclusão da visita no histórico | Aprovado |
| US06 | Consulta do histórico | Aprovado |
| US06 | Organização do histórico | Aprovado em ordem cronológica decrescente |
| US06 | Ausência de visitas | Aprovado |
| US07 | Apresentação dos indicadores | **Reprovado devido ao CA07.2** |
| US07 | Correspondência dos indicadores | **Reprovado devido ao CA07.2** |
| US07 | Ausência de dados | Aprovado para os indicadores implementados |
| US07 | Atualização dos indicadores | Aprovado para os indicadores implementados |

## Testes unitários do back-end

Os testes deste grupo verificam regras dos modelos, validações dos formulários,
valores padrão, relacionamentos e consultas usadas nos indicadores. Eles são
mantidos nos arquivos `test_unitarios.py` de cada módulo.

### Resultado

| Módulo | Executados | Aprovados | Reprovados |
|---|---:|---:|---:|
| Gestão de Escolas | 10 | 10 | 0 |
| Rondas e Visitas | 10 | 10 | 0 |
| Visão Gerencial | 3 | 3 | 0 |
| **Total** | **23** | **23** | **0** |

Os 23 testes foram aprovados. Como parte deles utiliza o ORM e o banco de dados
de teste do Django, tecnicamente alguns também possuem características de teste
de integração. Neste projeto acadêmico, eles foram classificados como unitários
do back-end porque exercitam diretamente modelos, formulários e consultas, sem
percorrer a interface do usuário.

## Testes unitários do front-end

Os testes deste grupo verificam campos, opções, validações do navegador,
mensagens, atualização visual e os principais fluxos apresentados nas páginas.
Eles são mantidos nos arquivos `test_frontend.py` e executados com Selenium no
Chrome em modo headless.

### Comando executado

```powershell
python -m pytest escolas/tests/test_frontend.py visitas/tests/test_frontend.py core/tests/test_frontend.py -m selenium -v -p no:cacheprovider
```

### Resultado

| Módulo | Executados | Aprovados | Reprovados |
|---|---:|---:|---:|
| Gestão de Escolas | 5 | 5 | 0 |
| Rondas e Visitas | 4 | 4 | 0 |
| Visão Gerencial | 3 | 3 | 0 |
| **Total** | **12** | **12** | **0** |

Os 12 testes foram aprovados.

### Limitação da classificação

Esses testes não são unitários de front-end no sentido técnico estrito. O
Selenium abre um navegador real, inicia o servidor de testes do Django e, em
alguns cenários, utiliza o banco de dados. Por isso, eles também podem ser
classificados como testes de interface ou testes de integração de ponta a ponta.

O front-end atual é formado principalmente por templates renderizados pelo
Django e possui pouca lógica JavaScript isolada. Não há, portanto, unidades de
JavaScript suficientes para uma suíte unitária independente. A denominação
“testes unitários do front-end” foi mantida para seguir a organização acadêmica
solicitada, enquanto esta observação registra a limitação metodológica.

## Conclusão

Os testes confirmaram o funcionamento dos fluxos de escolas, problemáticas,
registro e histórico de visitas e dos indicadores já implementados. A sprint 1
apresentou duas não conformidades: ausência do campo de observações
complementares da visita e ausência do indicador de escolas com visitas. Os
testes correspondentes permanecerão reprovados até que os comportamentos sejam
implementados e validados em uma nova execução.

---

# Relatório de execução dos testes — Sprint 2

## Identificação

- **Projeto:** RECOM — Ronda Escolar Comunitária
- **Sprint:** 2
- **Data da execução:** 21/10/2026
- **Ferramenta:** Pytest 9.1.1 com pytest-django 4.14.0 e Selenium
- **Aplicação:** Django 6.0.3
- **Plataforma da execução:** Windows, Python 3.13.14, Chrome 155

## Objetivo

Registrar o resultado da execução dos testes das funcionalidades entregues na
sprint 2:

- F05 — Gerenciar Cartão Programa;
- F06 — Gerenciar Usuários;
- F07 — Gerenciar Acesso ao Sistema.

## Especificação dos testes funcionais

Os casos abaixo descrevem os comportamentos esperados das User Stories US08 a
US11. Casos parametrizados são executados mais de uma vez com dados diferentes,
por isso a quantidade de execuções pode ser maior que a quantidade de funções de
teste.

### F05 — Gerenciar Cartão Programa

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F05-01 | CA08.1 | Coordenador autenticado e plantão cadastrado | Acessar a criação do cartão | O cadastro é apresentado ao Coordenador RECOM |
| CT-F05-02 | CA08.1 | Mediador autenticado | Tentar acessar a criação do cartão | O acesso ao cadastro é impedido |
| CT-F05-03 | CA08.2 e CA08.9 | Existir plantão e coordenador ativo | Informar observações e confirmar o cartão | O cartão registra data, responsável e observações |
| CT-F05-04 | CA08.3, CA08.4, CA08.7 e CA08.10 | Existirem cartão, viatura, efetivo e escola | Registrar duas missões e consultar o cartão | As missões são vinculadas e disponibilizadas para consulta |
| CT-F05-05 | CA08.8 | Existir um Cartão Programa | Enviar missão sem os campos obrigatórios | Os erros são indicados e a missão não é criada |
| CT-F05-06 | CA08.3 e CA08.8 | Existir plantão sem missões | Confirmar e consultar o cartão | O cartão sem missão não deve ser concluído ou disponibilizado |
| CT-F05-07 | CA08.4 | Coordenador autenticado | Abrir o cadastro de missão | O formulário apresenta horário, local ou escola, viatura/efetivo e tipo |
| CT-F05-08 | CA08.6 | Existir GCM ativo escalado em uma viatura | Associar a viatura à missão | O GCM responsável fica associado à missão pelo efetivo da viatura |
| CT-F05-09 | CA09.1, CA09.3 e CA09.4 | Existir cartão completo | Consultar a listagem e o detalhe como coordenador | São apresentados data, responsável, missão, horário, local, tipo e efetivo |
| CT-F05-10 | CA09.2 e CA09.6 | GCM escalado em uma viatura | Acessar Meu Cartão Programa | Somente cartões e missões da viatura do GCM são apresentados |
| CT-F05-11 | CA09.6 | GCM autenticado | Tentar acessar a listagem gerencial | O acesso à consulta completa é impedido |
| CT-F05-12 | CA09.5 | Existirem cartões em datas e escolas diferentes | Filtrar por data e escola | Somente os cartões correspondentes são apresentados |
| CT-F05-13 | CA09.7 | Existirem cartões sem correspondência com o filtro | Consultar com critérios inexistentes | A consulta fica vazia e informa que nenhum cartão foi encontrado |
| CT-F05-14 | CA09.7 | Não existir cartão cadastrado | Acessar a consulta | O sistema informa a ausência de cartões |

### F06 — Gerenciar Usuários

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F06-01 | CA10.1, CA10.3 e CA10.6 | Administrador autenticado | Abrir o cadastro de usuário | São apresentados os campos básicos, opcionais e os quatro perfis permitidos |
| CT-F06-02 | CA10.1, CA10.3, CA10.6 e CA10.7 | Preparar dados válidos | Confirmar o cadastro | O perfil e a conta são criados com os dados informados e situação ativa |
| CT-F06-03 | CA10.2 e CA10.9 | Preparar um cadastro válido | Enviar separadamente nome, matrícula ou perfil vazio | O campo é indicado como obrigatório e nenhum usuário é criado |
| CT-F06-04 | CA10.4 e CA10.9 | Existir usuário com a matrícula informada | Tentar cadastrar outro usuário com a mesma matrícula | A duplicidade é informada e apenas o registro original permanece |
| CT-F06-05 | CA10.5 e CA10.9 | Existir usuário com o matrícula informado | Tentar cadastrar outro usuário com o mesmo matrícula | A duplicidade é informada e o novo registro não é criado |
| CT-F06-06 | CA10.8 | Preparar dados válidos | Concluir o cadastro | A conta recebe a senha provisória 1234 e fica marcada para primeiro acesso |

### F07 — Gerenciar Acesso ao Sistema

| ID | Critérios | Pré-condição e dados | Ação | Resultado esperado |
|---|---|---|---|---|
| CT-F07-01 | CA11.1 e CA11.2 | Usuário ativo com matrícula e senha válidas | Realizar o login | O usuário é autenticado e acessa a área correspondente ao perfil |
| CT-F07-02 | CA10.8 e CA11.2 | Usuário ativo com senha inicial 1234 | Realizar o primeiro login | O usuário é autenticado e direcionado para definir nova senha |
| CT-F07-03 | CA11.3 e CA11.4 | Existir usuário ativo | Informar matrícula inexistente ou senha incorreta | A autenticação é impedida e a mensagem de credenciais inválidas é apresentada |
| CT-F07-04 | CA11.5 e CA11.6 | Existir perfil RECOM inativo | Informar matrícula e senha corretas | O acesso é impedido e o sistema informa que o usuário está inativo |

## Resultado geral dos testes funcionais

| Situação | Quantidade |
|---|---:|
| Testes executados | 27 |
| Aprovados | 23 |
| Reprovados | 4 |
| Não executados | 0 |
| Percentual de aprovação | 85,2% |

O conjunto funcional terminou com código de saída `1`, pois foram identificadas
quatro execuções reprovadas relacionadas a quatro comportamentos não atendidos.

## Resultado funcional por módulo

| Módulo | Funcionalidades | Executados | Aprovados | Reprovados | Resultado |
|---|---|---:|---:|---:|---|
| Cartão Programa | F05 | 14 | 11 | 3 | Reprovado |
| Gestão de Usuários | F06 | 8 | 8 | 0 | Aprovado |
| Acesso ao Sistema | F07 | 5 | 4 | 1 | Reprovado |
| **Total** | **F05 a F07** | **27** | **23** | **4** | **Reprovado** |

## Rastreabilidade dos critérios de aceitação

| Critérios | Descrição resumida | Resultado | Evidência |
|---|---|---|---|
| CA08.1–CA08.2 | Permissão, data e responsável pelo cartão | Aprovado | O coordenador acessou e ficou registrado como responsável pelo plantão |
| CA08.3 | Uma ou mais missões por cartão | **Reprovado parcialmente** | Múltiplas missões são aceitas, mas o cartão também é disponibilizado sem nenhuma missão |
| CA08.4 | Dados operacionais da missão | Aprovado | O formulário apresenta horário, escola/local, endereço, viatura/efetivo e tipo |
| CA08.5 | Tipos de missão exigidos | **Reprovado** | A opção Entrada não está disponível |
| CA08.6–CA08.7 | GCMs ativos e associação com escola | Aprovado | O efetivo é vinculado pela viatura e a missão aceita escola cadastrada |
| CA08.8 | Bloqueio de cadastro incompleto | **Reprovado parcialmente** | A missão incompleta é bloqueada, mas o cartão sem missão é disponibilizado |
| CA08.9–CA08.10 | Observações, persistência e consulta | Aprovado | Observações, cartão e missões válidas foram persistidos e consultados |
| CA09.1–CA09.4 | Consultas do coordenador e do GCM | Aprovado | Cada perfil visualizou os cartões, missões e informações permitidas |
| CA09.5 | Filtros por data e escola/local | **Reprovado** | A tela não possui os filtros e a view ignora os parâmetros de consulta |
| CA09.6 | Permissões dos resultados | Aprovado | O GCM visualizou somente missões de sua viatura e não acessou a gestão completa |
| CA09.7 | Mensagem quando não houver resultado | **Reprovado parcialmente** | A consulta vazia sem cartões possui mensagem, mas filtros sem correspondência não são aplicados |
| CA10.1–CA10.9 | Cadastro, campos, unicidade, perfis, situação e senha inicial | Aprovado | Todos os testes de cadastro de usuário passaram |
| CA11.1 | Login por matrícula e senha | Aprovado | O mecanismo autenticou as credenciais válidas |
| CA11.2 | Acesso com credenciais válidas | **Reprovado parcialmente** | O Mediador é autenticado, mas sua página de destino retorna erro 500 |
| CA11.3–CA11.4 | Credenciais inválidas | Aprovado | O acesso foi impedido com mensagem apropriada |
| CA11.5–CA11.6 | Usuário inativo | Aprovado | O perfil inativo teve o acesso bloqueado e recebeu mensagem específica |

## Não conformidades encontradas

### NC-03 — Ausência do tipo de missão Entrada

- **Funcionalidade:** F05 — Gerenciar Cartão Programa
- **Critério:** CA08.5
- **Testes:** `test_ca08_5_tipos_contemplam_atividades_operacionais_obrigatorias`
  e `test_tipos_de_missao_exibem_atividades_previstas`
- **Resultado esperado:** as opções devem incluir Entrada, Saída, Visita de
  Rotina e Rondas com PB.
- **Resultado obtido:** Saída, Visita de Rotina e Rondas com PB estão
  disponíveis, mas Entrada não foi implementada.
- **Situação:** reprovado.

### NC-04 — Cartão Programa disponibilizado sem missão

- **Funcionalidade:** F05 — Gerenciar Cartão Programa
- **Critérios:** CA08.3 e CA08.8
- **Teste:** `test_bdd_campos_obrigatorios_cartao_sem_missao_nao_deve_ser_concluido`
- **Resultado esperado:** o Cartão Programa deve possuir ao menos uma missão
  antes de sua conclusão e disponibilização.
- **Resultado obtido:** o cartão é persistido e aparece na consulta mesmo sem
  missão cadastrada.
- **Situação:** reprovado.

### NC-05 — Ausência de filtros na consulta de cartões

- **Funcionalidade:** F05 — Gerenciar Cartão Programa
- **Critério:** CA09.5
- **Testes:** `test_bdd_consulta_por_filtros_restringe_por_data_e_escola` e
  `test_consulta_disponibiliza_filtros_de_data_e_escola_local`
- **Resultado esperado:** a consulta deve permitir filtrar por data e por
  escola ou local.
- **Resultado obtido:** a interface não apresenta os controles e a view retorna
  todos os cartões mesmo quando recebe parâmetros de filtro.
- **Situação:** reprovado.

### NC-06 — Consulta filtrada sem mensagem de ausência

- **Funcionalidade:** F05 — Gerenciar Cartão Programa
- **Critério:** CA09.7
- **Teste:** `test_bdd_nenhum_resultado_encontrado_informa_ausencia`
- **Resultado esperado:** uma consulta sem correspondência deve ficar vazia e
  informar que nenhum Cartão Programa foi encontrado.
- **Resultado obtido:** como os filtros não são aplicados, cartões não
  correspondentes continuam sendo apresentados e a mensagem não aparece.
- **Situação:** reprovado.

### NC-07 — Painel do Mediador inexistente após autenticação

- **Funcionalidade:** F07 — Gerenciar Acesso ao Sistema
- **Critério:** CA11.2
- **Testes:** `test_bdd_autenticacao_valida_permite_acesso` e
  `test_bdd_autenticacao_valida_direciona_para_area_do_perfil`
- **Resultado esperado:** o Mediador com matrícula e senha válidas deve ser
  autenticado e acessar sua área no sistema.
- **Resultado obtido:** a autenticação e o redirecionamento são realizados, mas
  `/dashboard/mediador/` retorna HTTP 500 porque o template
  `dashboard/mediador.html` não existe.
- **Situação:** reprovado.

## BDDs verificados

| User Story | Cenário | Resultado |
|---|---|---|
| US08 | Cadastro com dados válidos | Aprovado para cartão contendo missões válidas |
| US08 | Campos obrigatórios | **Reprovado parcialmente: o cartão pode ser disponibilizado sem missão** |
| US08 | Missão operacional | Aprovado para os campos; **CA08.5 reprovado pela ausência de Entrada** |
| US08 | Associação do efetivo | Aprovado por meio da viatura e seus GCMs ativos |
| US09 | Consulta de Cartões Programa cadastrados | Aprovado para Coordenador e GCM conforme as permissões |
| US09 | Consulta por filtros | **Reprovado** |
| US09 | Nenhum resultado encontrado | **Reprovado para consulta filtrada** |
| US10 | Cadastro com dados válidos | Aprovado |
| US10 | Campos obrigatórios | Aprovado |
| US10 | Matrícula já cadastrada | Aprovado |
| US10 | Definição da senha inicial | Aprovado |
| US11 | Autenticação com dados válidos | **Reprovado para o perfil Mediador devido ao erro 500** |
| US11 | Matrícula ou senha inválida | Aprovado |
| US11 | Usuário inativo | Aprovado |

## Testes unitários do back-end

Os testes deste grupo verificam diretamente modelos, formulários, valores
padrão, relacionamentos e validações dos módulos da sprint 2.

### Comando de execução

```powershell
python -m pytest cartao_programa/tests/test_unitarios.py usuarios/tests/test_unitarios.py -v
```

### Resultado

| Módulo | Executados | Aprovados | Reprovados |
|---|---:|---:|---:|
| Cartão Programa | 14 | 13 | 1 |
| Gestão de Usuários e Acesso | 13 | 13 | 0 |
| **Total** | **27** | **26** | **1** |

A reprovação do Cartão Programa corresponde à ausência da opção Entrada entre
os tipos de missão do CA08.5. Os testes de usuários e autenticação que exercitam
diretamente modelos e formulários foram aprovados.

## Testes unitários do front-end

Os testes deste grupo exercitam os formulários e fluxos visíveis no Chrome em
modo headless com Selenium. A denominação acadêmica foi mantida, embora esses
casos também sejam testes de interface e integração de ponta a ponta.

### Comando de execução

```powershell
python -m pytest cartao_programa/tests/test_frontend.py usuarios/tests/test_frontend.py -m selenium -v
```

### Resultado

| Módulo | Executados | Aprovados | Reprovados |
|---|---:|---:|---:|
| Cartão Programa | 7 | 5 | 2 |
| Gestão de Usuários e Acesso | 9 | 8 | 1 |
| **Total** | **16** | **13** | **3** |

As reprovações de interface confirmaram a ausência do tipo Entrada, a ausência
dos filtros de consulta de cartões e o erro 500 apresentado depois do login do
Mediador. As falhas transitórias de sincronização inicialmente observadas nos
testes de campos obrigatórios e credenciais inválidas foram corrigidas e esses
testes passaram na execução final.

## Conclusão da sprint 2

Os testes confirmaram o cadastro de usuários, as validações de matrícula,
a senha inicial, o primeiro acesso, o bloqueio de credenciais inválidas e de
usuários inativos, bem como os principais fluxos de criação e consulta do
Cartão Programa. Foram registradas cinco não conformidades distintas: ausência
do tipo de missão Entrada, disponibilização de cartão sem missão, ausência de
filtros, ausência de resultado adequado para filtros sem correspondência e erro
500 no painel do Mediador. Os testes correspondentes permanecerão reprovados
até que esses comportamentos sejam corrigidos e submetidos a uma nova execução.
