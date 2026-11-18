# Safe-Track — Etapa 1: Pytest com preservação da aplicação

Data: **17/11/2026**, referência de apresentação `America/Sao_Paulo`.

Branch: **`desenvolvimento`**, commit de referência **`08990a2`**. O checkout estava limpo no início. Esta etapa foi autorizada após a inspeção do documento “SAFE-TRACK — DESENVOLVIMENTO CONTROLADO E PRESERVAÇÃO DA ARQUITETURA ORIGINAL”.

O escopo executado foi exclusivamente preparar o ambiente, corrigir os testes e ampliá-los. Os defeitos identificados na API não foram corrigidos. Visitantes, dashboards e front-end não foram implementados nesta etapa.

## 1. Resultado efetivamente obtido

| Métrica | Resultado |
|---|---:|
| Casos executados | **181** |
| Aprovados | **171** |
| Reprovados | **10** |
| Erros de coleta/execução | **0** |
| Ignorados | **0** |
| Tempo reportado pelo Pytest | **9,05 s** |
| Linhas executadas | **691 / 714 — 96,78%** |
| Ramos executados | **127 / 138 — 92,03%** |
| Cobertura combinada de linhas e ramos | **96,01%** |
| Avisos, sem supressão | **71** |

**A suíte completa não está verde:** termina com código de saída 1 pelas dez falhas descritas abaixo. A infraestrutura de coleta e execução funciona; as falhas restantes exercitam defeitos preexistentes da aplicação. Não foram usados `skip`, `xfail`, alteração da API ou desativação das verificações para ocultá-las.

O marcador `defeito_api` apenas identifica esses casos; eles continuam executando e reprovando normalmente. A cobertura também inclui linhas percorridas por testes que falharam. Portanto, cobertura alta não significa que todos os comportamentos estejam corretos.

| Arquivo | Casos | Aprovados | Reprovados | Escopo |
|---|---:|---:|---:|---|
| `test_auth.py` | 49 | 46 | 3 | Login, JWT, permissões, cadastro, logout e associação RFID |
| `test_http.py` | 14 | 10 | 4 | Página, erros HTTP, logger, exceções e bloqueios de isolamento |
| `test_inventory.py` | 63 | 60 | 3 | Objetos, imagens, locais, dispositivos, MAC, tags e rollback |
| `test_access.py` | 7 | 7 | 0 | Acesso permitido/negado, conta inativa, local e histórico |
| `test_models.py` | 22 | 22 | 0 | Unicidade, nulabilidade, FKs e relacionamentos declarados |
| `test_mqtt.py` | 26 | 26 | 0 | Tópicos, encaminhamento, respostas, callbacks e falhas simuladas |
| **Total** | **181** | **171** | **10** | |

## 2. Diagnóstico inicial e correções dos testes

A coleta inicial, antes da aprovação para implementação, foi executada com cache e bytecode desativados. Retornou `ModuleNotFoundError: No module named 'flask'`, nenhum teste coletado e um erro em 0,07 s. O Python do sistema tinha pytest 7.4.4, mas não tinha Flask, SQLAlchemy e as extensões da aplicação; também não existia `.venv` neste checkout recuperado.

O `pytest.ini` já continha `pythonpath = . src`. A busca de módulos confirmou que `app` é encontrado quando `src` está no caminho. Não foi identificado um motivo para reorganizar os pacotes da API ou reescrever seus imports.

| Problema nos testes | Correção aplicada somente à infraestrutura de testes |
|---|---|
| Dependências da aplicação ausentes no Python usado | Criado ambiente virtual `.venv`; instalados os requisitos existentes e os requisitos de desenvolvimento |
| Cinco testes chamavam `/auth/login` | Corrigidos para a rota existente `/login`, sem mudar a URL da API |
| Dependência da conta de administrador do banco real | Criados usuários fictícios e senhas próprias dos testes, em SQLite em memória |
| Expectativa de 404 para login de usuário inexistente | Alinhada ao 401 que o código original retorna; continua exigindo ausência de token |
| Expectativa de 400 para e-mail vazio no login | Alinhada ao 401 que o código original retorna; continua exigindo ausência de token |
| Import da aplicação ocorria antes do isolamento | Removidos imports globais redundantes do teste; o primeiro import ocorre numa fixture dependente dos bloqueios de isolamento |
| Não existiam fixtures compartilhadas | Criado `conftest.py` para aplicação, banco, clientes, usuários, headers JWT, inventário e módulos MQTT |
| Ausência de cobertura e tempos | Criada configuração de cobertura e opção `--api-timings` |

Os cinco cenários originais de `test_login_dinamico` foram preservados: credenciais válidas, duas senhas incorretas, usuário inexistente e e-mail vazio. Agora usam dados fictícios, a rota correta e IDs de parametrização que não exibem senhas. As asserções também verificam a presença ou ausência do token. Não houve mudança na implementação do login.

`src/app/tests/ __init__.py`, cujo nome contém um espaço, foi preservado. Nenhum arquivo foi renomeado, movido ou excluído.

## 3. Arquivos criados e modificados

| Arquivo | Ação | Motivo |
|---|---|---|
| `pytest.ini` | Modificado | Preservar os caminhos Python, delimitar `testpaths`, validar configuração/marcadores e declarar `defeito_api` |
| `src/app/tests/test_auth.py` | Modificado | Corrigir os cinco cenários e ampliar a verificação dos contratos existentes |
| `requirements-dev.txt` | Criado | Declarar dependências do ambiente de teste, sem modificar `requirements.txt` |
| `.coveragerc` | Criado | Medir linhas/ramos da aplicação, modelos e logger, excluindo os próprios testes |
| `src/app/tests/conftest.py` | Criado | Isolamento anterior ao import, fixtures, bloqueios e medição HTTP |
| `src/app/tests/test_http.py` | Criado | Respostas HTTP, erros, logs e proteção do ambiente de testes |
| `src/app/tests/test_inventory.py` | Criado | Objetos, locais, uploads, dispositivos, tags, MAC e transações |
| `src/app/tests/test_access.py` | Criado | Decisão e persistência de acesso no fluxo original |
| `src/app/tests/test_models.py` | Criado | Integridade declarada pelos modelos e hierarquia User/Root |
| `src/app/tests/test_mqtt.py` | Criado | Contratos originais de MQTT e comunicação externa com mocks |
| `documents/etapa1_pytest_preservacao.md` | Criado | Este relatório |

O ambiente `.venv` é local e já é ignorado pelas regras existentes do repositório. Os artefatos desta execução foram guardados fora do checkout, em `/tmp/safe-track-etapa1-w8qcl86z`.

`requirements-dev.txt` inclui `requirements.txt`, pytest, pytest-cov, requests e paho-mqtt. Requests e Paho já são importados pelo código MQTT original; sua declaração aqui torna o ambiente de testes reproduzível sem mudar a lista de requisitos da implantação. O arquivo original `requirements.txt` permaneceu intacto. Nenhum pacote foi instalado no Python do sistema.

## 4. Isolamento e preservação

O import de `app.py` originalmente executa `db.create_all()`, consulta/cria o administrador e configura logs. A fixture instala a proteção antes desse import. Somente no processo de testes, o `SQLAlchemy.init_app` recebe SQLite em memória, `TESTING=True` e chaves JWT/sessão fictícias. O bootstrap original executa nesse banco descartável; cada caso depois recria as tabelas e usa seus próprios registros.

As rotas, os algoritmos JWT, os callbacks de revogação e as verificações de perfil são os originais. Os conjuntos `BLOCKLIST` de `auth.py` e `app.py` continuam separados: os testes não os unificam para fazer logout passar.

Para logs, a função original `configurar_logger()` continua executando com seus handlers, níveis, mensagens e formatter originais. A fixture altera apenas o caminho de origem visto por essa função durante os testes, direcionando a saída para uma pasta temporária. Há um bloqueio adicional para impedir `FileHandler` fora desse limite. O arquivo `src/logs/config_log.py` não foi modificado.

Uploads usam um diretório de trabalho temporário por teste. `PASTA_UPLOADS` e a rota de imagens não foram alteradas. A gravação de `FileStorage` é bloqueada se sair da área temporária. Conexões SQLite fora dessa área, conexões de socket e resolução DNS reais também são bloqueadas; a integração externa usa mocks.

Os testes da API mantêm o comportamento original do SQLite, incluindo `PRAGMA foreign_keys=0`. Um **engine separado**, somente para os testes de modelos, usa `foreign_keys=ON` para verificar as FKs declaradas. Isso não ativa FKs na API ou no banco implantado e não comprova a integridade de dados de produção.

Evidências de preservação:

- **54 arquivos de produção** comparados por SHA-256 com o estado anterior: **zero diferenças**.
- **Nove uploads existentes** comparados por inode, tamanho, mtime e ctime: **zero diferenças**.
- O banco real não foi aberto pelas fixtures; acessos fora do limite temporário são rejeitados antes da conexão.
- `src/database/hermes.db` não existia como arquivo no início desta execução e continua ausente no checkout; os testes não o criaram. Também não foram criados arquivos de log em `Logs/` ou `src/Logs/` do projeto.
- Docker, Compose, firmware, modelos, requisitos de produção, templates, JavaScript e logger permaneceram sem alterações.
- Não houve commit, push, mudança de branch ou implementação de outra etapa.

## 5. Dez falhas reais que dependem de decisão

| ID | Caso | Esperado pelo teste | Obtido | Causa observada no código original |
|---|---|---:|---:|---|
| API-01 | Cadastro com e-mail duplicado | 400 | 500 | `jsonify` recebe um set em vez de um objeto JSON |
| API-02 | Uso de token após logout | 401 | 200 | Logout grava em `auth.BLOCKLIST`, mas o callback consulta `app.BLOCKLIST` |
| API-03 | Root cadastra outro Root com dados válidos | 201 | 500 | Campo herdado `senha` não é preenchido e discriminador usa `root`, diferente de `roots` |
| API-04a | URL inexistente | 404 | 500 | Tratador genérico converte a exceção HTTP em 500 |
| API-04b | Método GET em `/login` | 405 | 500 | Mesmo tratador genérico |
| API-04c | JSON malformado | 400 | 500 | Mesmo tratador genérico |
| API-04d | Content-Type inadequado | 415 | 500 | Mesmo tratador genérico |
| API-05a | Cadastro de local sem endereço | 400 | 200 | Condição de preenchimento incorreta e retorno sem status de erro |
| API-05b | Cadastro de local sem descrição | 400 | 500 | Validação não impede tentativa de gravar coluna obrigatória nula |
| API-05c | Cadastro de local sem responsável | 400 | 500 | Mesmo problema de validação |

Não são erros de importação ou de fixtures: as requisições chegaram às rotas e os resultados acima foram observados. As expectativas referentes a 400/404/405/415 e à rejeição após logout permanecem explícitas para que esses comportamentos sejam decididos, em vez de transformar falhas em aprovação.

### Propostas mínimas, ainda não aplicadas

| Grupo | Arquivos envolvidos | Proposta | Efeito esperado |
|---|---|---|---|
| API-01 | `src/app/routes/auth.py` | Corrigir o objeto passado a `jsonify` | Preservar o retorno 400 pretendido para duplicidade |
| API-02 | `src/app/routes/auth.py`, `src/app/routes/app.py` | Fazer logout e callback consultarem o mesmo conjunto existente | Revogar JWT de usuário em memória, sem tabela nova ou autenticação de dispositivo |
| API-03 | `src/app/routes/auth.py` | Preencher `senha` com hash e usar o discriminador `roots` | Permitir o cadastro Root já previsto, sem criar novos perfis |
| API-04 | `src/app/routes/app.py` | Preservar status/cabeçalhos das exceções HTTP | Corrigir respostas de erro sem mudar URLs ou requests válidos |
| API-05 | `src/app/routes/local.py` | Verificar os três campos existentes e responder 400 quando faltarem | Rejeitar cadastro incompleto, mantendo os campos e o retorno de sucesso atuais |

Essas propostas alteram a aplicação e **exigem autorização específica**. A alternativa é manter o código atual e as dez falhas visíveis. Não é necessário trocar arquitetura, banco, broker, servidor, firmware ou contratos do ESP32 para tratar esses grupos.

## 6. HTTP, MAC, MQTT e demais contratos preservados

- `POST /cadastrar_rfid`: `uid`, `date`, `mac_adress`. A autorização continua exclusivamente pela existência do MAC em `Esp32_registro`. Os testes comprovam sucesso sem token/cabeçalho adicional e rejeição de MAC não cadastrado.
- `POST /acessar_porta`: `uid_solicitante`, `local`; respostas originais de acesso com `abrir`, status e histórico. Não foi acrescentada uma etapa de autenticação de dispositivo a esse endpoint.
- Broker MQTT: `test.mosquitto.org`, porta 1883, entrada `ESP_envia_tag` e resposta `Resposta_API`.
- A integração continua encaminhando os campos originais por `requests.post(API_URL, json=...)`, sem token de dispositivo, cabeçalhos novos, tradução de payload ou serviço intermediário adicional.
- Respostas MQTT continuam textuais: `200`, `401`, `500`, com o mapeamento original. Inclusive respostas HTTP 500 da API continuam mapeadas para `401`, porque esse comportamento não foi autorizado para alteração.
- Os imports de módulos irmãos do MQTT foram acomodados no caminho de importação dos testes, reproduzindo o uso original como script. Nenhum import do código de produção foi reescrito.
- Os nomes das rotas, campos de resposta, verificações JWT existentes, apresentação de logs e estilo visual foram preservados.

O teste Socket.IO exerce uma leitura HTTP e o recebimento do evento `rfid_update` em processo, usando o backend selecionado pela própria aplicação. Não abre um navegador nem um socket de rede real.

### Limitações preexistentes documentadas

Os exemplos versionados de firmware apresentam divergências: o MQTT envia `mac` sem `date`, enquanto a integração espera `mac_adress` e `date`; o sketch assina `ESP_resposta_API`, enquanto a integração publica `Resposta_API`. O exemplo `Teste_API.ino` também não inclui `mac_adress` no JSON mostrado. Existem ainda pontos sintáticos aparentes no sketch MQTT. Nenhum desses arquivos foi corrigido, compilado ou enviado a hardware nesta etapa; não se presume que o arquivo versionado seja idêntico ao firmware atualmente gravado no dispositivo.

A integração MQTT não trata UTF-8 inválido ou JSON que seja uma lista. Há testes de caracterização que demonstram essas exceções, sem afirmar recuperação inexistente. Outros comportamentos, como permissões de consultas públicas e validações incompletas, continuam conforme a aplicação original.

MAC é um identificador informável pelo cliente e não prova autenticidade criptográfica. Essa limitação é registrada aqui; não foram implementados tokens, certificados, autenticação adicional, novos tópicos ou novas tabelas para dispositivos.

O modelo mantém `User.credencial_rfid` como Integer referenciando UID textual. O protótipo `src/services/dashboards.py` continua com consulta SQL vazia e não foi tratado como dashboard funcional. Nenhuma dessas observações motivou alteração automática.

## 7. Tempos das requisições

| Medida | Resultado |
|---|---:|
| Chamadas ao cliente Flask | **132** |
| Média | **14,367 ms** |
| Mediana | **3,873 ms** |
| Percentil 95 | **116,325 ms** |
| Máximo | **197,166 ms** |

A medição usa `time.perf_counter_ns()` ao redor do cliente Flask, com instrumentação de cobertura ativa. Inclui cenários distintos, hashing de senha, erros e falhas simuladas. Não constitui benchmark de produção e não mede latência física do ESP32, rede Wi-Fi, broker MQTT, leitor ou servo.

O JSON de tempos contém apenas método, caminho, status e duração. Não armazena corpos de requisição, senhas ou JWTs.

## 8. Ambiente e dependências efetivamente utilizadas

Python 3.12.3; pytest 9.2.0; pytest-cov 7.1.0; Flask 3.1.3; Flask-SQLAlchemy 3.1.1; SQLAlchemy 2.1.9; Flask-JWT-Extended 4.7.4; Flask-SocketIO 5.7.2; Flask-MQTT 1.3.0; Eventlet 0.41.3; requests 2.34.2; paho-mqtt 2.2.0.

`pip check` retornou `No broken requirements found`. As versões completas estão em `requirements-tested.txt` junto dos artefatos. Os requisitos originais não fixam grande parte das versões; registrar o conjunto testado não garante que uma instalação futura resolva exatamente as mesmas versões.

Os 71 avisos incluem depreciações do callback v1 usado pela extensão Flask-MQTT, Eventlet, `Query.get`, defaults de data e avisos SQLAlchemy nos casos de conflito/polimorfismo. Não foram suprimidos. Não foi realizada uma modernização desses componentes.

## 9. Reproduzir

Na raiz do repositório:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -B -m pytest -q -p no:cacheprovider
```

O último comando deve reportar também os defeitos ainda presentes; não se espera código de saída zero enquanto eles permanecerem na aplicação.

Para cobertura, JUnit e tempos, com artefatos fora do checkout:

```bash
SAFE_TRACK_REPORT_DIR="$(mktemp -d /tmp/safe-track-etapa1.XXXXXX)"
COVERAGE_FILE="$SAFE_TRACK_REPORT_DIR/.coverage" .venv/bin/python -B -m pytest -q \
  -p no:cacheprovider --cov --cov-report=term-missing \
  --cov-report="xml:$SAFE_TRACK_REPORT_DIR/coverage.xml" \
  --cov-report="json:$SAFE_TRACK_REPORT_DIR/coverage.json" \
  --junitxml="$SAFE_TRACK_REPORT_DIR/junit.xml" \
  --api-timings="$SAFE_TRACK_REPORT_DIR/api-timings.json"
```

Artefatos desta execução:

- [Saída completa do Pytest](/tmp/safe-track-etapa1-w8qcl86z/pytest-completo.txt)
- [JUnit](/tmp/safe-track-etapa1-w8qcl86z/junit.xml)
- [Cobertura JSON](/tmp/safe-track-etapa1-w8qcl86z/coverage.json)
- [Cobertura XML](/tmp/safe-track-etapa1-w8qcl86z/coverage.xml)
- [Tempos HTTP](/tmp/safe-track-etapa1-w8qcl86z/api-timings.json)
- [Preservação dos arquivos](/tmp/safe-track-etapa1-w8qcl86z/preservacao.json)
- [Verificação de dependências](/tmp/safe-track-etapa1-w8qcl86z/pip-check.txt)
- [Versões instaladas](/tmp/safe-track-etapa1-w8qcl86z/requirements-tested.txt)

Os caminhos `/tmp` são evidências locais desta sessão e podem ser removidos pelo sistema; os comandos acima permitem regenerar os relatórios. Não foram incorporados arquivos com dados reais ao repositório.

## 10. Encerramento e pendências

A coleta e o ambiente de testes estão corrigidos, a suíte foi ampliada e os resultados reais estão registrados. Permanecem as dez falhas de aplicação agrupadas em API-01 a API-05. Elas foram mantidas para decisão do responsável, respeitando a proibição de modificar a API para satisfazer os testes.

Não foram executados broker real, ESP32, compilação de firmware, navegador, Docker/Compose, implantação ou GitHub Actions nesta etapa. MQTT externo usa mocks; API/SQLite/Socket.IO foram exercitados em processo e em área temporária. O código de produção e a infraestrutura permaneceram intactos.

As correções propostas para a API e o início de visitantes, dashboards ou front-end aguardam autorização. Nenhuma etapa seguinte foi iniciada.
