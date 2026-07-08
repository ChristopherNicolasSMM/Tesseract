# 06 — Model Builder Visual + API/SQL Playground

> **Status: EXECUTADA (2026-07-02).** Nasceu de uma conversa sobre a
> ausência de uma entrada de CrudGen no menu do Tesseract. Análise do
> `BACKLOG.md` do PyTeca (seção "Model Builder Visual") mostrou que o
> projeto original já resolvia isso — esta skill herda o desenho, com
> três correções obrigatórias em relação à arquitetura tri-nível do
> Tesseract (seção 3) que não existiam no PyTeca (projeto monolítico,
> sem Core/Addon/Feature/Plugin).
>
> **Patch A** (`existing_addon`/`existing_feature`), **Patch B**
> (`new_addon`/`new_feature`, scaffold completo — dependeu da skill 09
> pra não deixar `addon.py`/`feature.py` com wiring manual) e
> **Patch C** (API/SQL Playground + ponte com o Model Builder) estão
> todos implementados e testados (39 testes entre os três patches).
>
> **Adenda registrada em 2026-07-08 (Playground v2), status
> [EXECUTADO] — Patch D implementado e testado (`tests/test_playground.py`
> + `tests/test_playground_v2.py`, 40 casos entre os dois arquivos;
> suíte completa do projeto 498/498 passando).** Uso real do Playground
> para consumir APIs externas (não só a própria API do Tesseract) expôs
> que o schema do Patch C
> era insuficiente: sem Query Params estruturados, uma URL
> montada à mão errava encoding e a API externa respondia 404 —
> sintoma que parecia "falha de autenticação" mas não era. Isso, mais
> pedidos novos de uso real (Auth dedicada, histórico organizável),
> vira a seção 8 desta skill. Ver `BACKLOG.md` para o registro da
> decisão.
>
> Como toda skill formalizada, tem o mesmo peso normativo das skills
> 00–04: qualquer implementação que divergir do que está aqui precisa
> ajustar este documento antes (regra de ouro, skill 00).
>
> Convenção de status (igual skill 05): **[DECIDIDO]** fechado, pronto
> para execução quando autorizado — **[ABERTO]** ainda sem decisão —
> **[PENDENTE-SKILL]** decidido aqui, mas corrige/estende skill já
> existente antes de poder ser executado sem conflito.

---

## 0. Decisão raiz

**[DECIDIDO]** Vive em **Core**, não em Addon próprio. É meta-ferramenta
de infraestrutura (mesma categoria de RBAC/Versionamento, que já são
Core), não regra de negócio de domínio — compatível com a definição de
Core na skill 00.

**[DECIDIDO]** Duas Transações (skill 00, "Transação") num mesmo grupo
de menu, cujo nome de exibição fica a critério da implementação (ex.:
"Ferramentas de Desenvolvimento"):

| Transação | Rota web |
|---|---|
| Model Builder | `/admin/model-builder` |
| API/SQL Playground | `/admin/playground` |

**[DECIDIDO]** Escopo do Model Builder cobre os dois cenários:
1. Criar um **Model novo dentro de um Addon/Feature já existente**.
2. Criar um **Addon ou Feature inteiro do zero** (scaffold completo de
   pastas + manifesto + primeiro Model), disparando o checklist de
   manifesto da skill 03 (seção 6) antes de escrever qualquer arquivo.

---

## 1. Origem: o que o PyTeca já resolvia

Página `/admin/model-builder`, duas abas (lista de models via SmartList
+ formulário de criação/edição). Formulário: nome do model, nome de
tabela, módulo; editor de campos em grid (nome, tipo, nullable/unique/
default/FK); editor de anotações (`@label`, `@plural`, `@listview`,
`@form`, `@required`, `@max_length`); preview de código (Ace Editor);
botão "Gerar Modelo". Backend: tabela `model_definition`, serviço que
renderiza os mesmos templates Jinja2 do gerador CLI, escreve o arquivo
`.py`, roda `db.create_all()` (dev) ou gera migration Alembic
(produção). Reaproveitado quase integralmente — ver seção 3 para as
correções obrigatórias.

---

## 2. Schema de dados (Core, prefixo `tesseract_` fixo — skill 02)

### 2.1 `tesseract_model_definition`

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | Padrão skill 02 |
| `target_scope` | String (`new_addon` / `existing_addon` / `new_feature` / `existing_feature`) | Decide o que "Gerar" precisa scaffoldar |
| `target_addon_name` | String | `snake_case`, obrigatório em todos os cenários |
| `target_feature_name` | String, nullable | Só quando `target_scope` envolve Feature |
| `model_name` | String | `PascalCase` — vira a classe (skill 01) |
| `table_short_name` | String | `snake_case`, nome curto sem prefixo — validado como único **em todo o Addon**, não só na Feature (skill 02, "regra adicional: nome curto único em todo o Addon") |
| `manifest_draft_json` | JSON | Campos ainda não confirmados de `addon.json`/`feature.json` (label, description, table_prefix/table_prefix_suffix, env_keys) |
| `status` | String (`draft` / `generated` / `error`) | |
| `created_by_user_id` | Integer, FK → `tesseract_user.id` | Sempre permitido (skill 02) |
| `created_at` / `updated_at` | DateTime | Padrão skill 02 |

### 2.2 `tesseract_model_field_definition`

FK interna Core→Core (`model_definition_id` → `tesseract_model_definition.id`), permitida sem restrição pela skill 02.

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `model_definition_id` | Integer, FK | |
| `field_name` | String | `snake_case` |
| `field_type` | String (enum: `string`/`integer`/`float`/`boolean`/`date`/`datetime`/`text`/`foreign_key`) | |
| `nullable` / `unique` / `is_required` | Boolean | `is_required` alimenta `@required` |
| `default_value` | String, nullable | Serializado, interpretado conforme `field_type` |
| `max_length` | Integer, nullable | Só para `field_type=string` |
| `fk_target_table` | String, nullable | Ver validação obrigatória na seção 3.2 |
| `label_text` | String (PT-BR) | Texto direto — vira `translation_key` na geração (skill 00) |
| `is_listview_column` / `is_form_field` | Boolean | Alimentam `@listview`/`@form` |
| `order_index` | Integer | Ordem de exibição |

### 2.3 `tesseract_playground_request` [REVISADO — Playground v2, seção 8]

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `name` | String | |
| `http_method` | String | |
| `url` | String | **Passa a guardar só a URL base, sem query string** — a query final é montada a partir de `params_json` na hora de executar (seção 8) |
| `headers_json` / `body_json` | JSON | `headers_json` continua existindo como complemento livre — deixa de ser o único jeito de autenticar (ver `auth_type`/`auth_config` abaixo) |
| `params_json` | JSON, nullable | **Novo.** Lista `[{"key": "...", "value": "...", "enabled": true}, ...]` — só relevante para `kind=http` |
| `auth_type` | String(20), nullable, default `"none"` | **Novo.** `none` / `bearer` / `basic` / `api_key` — só relevante para `kind=http` |
| `auth_config` | JSON, nullable | **Novo.** Formato por tipo: `{"token": "..."}` (bearer) / `{"username": "...", "password": "..."}` (basic) / `{"header_name": "...", "value": "..."}` (api_key) |
| `folder_id` | Integer, FK → `tesseract_playground_folder.id`, nullable | **Novo.** `NULL` = fica na raiz, fora de qualquer pasta |
| `is_archived` | Boolean, default `false` | **Novo.** Oculta da lista principal, recuperável — ação **separada** de apagar (que continua sendo DELETE físico da linha, sem `is_deleted`/`deleted_at` — este model não segue soft-delete porque não é entidade CrudGen, mesma categoria de `CodeSnapshot`, skill 00 Adendo Fase 7a) |
| `last_response_json` | JSON, nullable | Base para o bridge da seção 5 |
| `last_status_code` | Integer, nullable | |
| `created_by_user_id` | Integer, FK → `tesseract_user.id` | |
| `created_at` / `updated_at` | DateTime | |

### 2.4 `tesseract_playground_folder` [NOVO — Playground v2, seção 8]

Core, FK auto-referenciada — permitida sem restrição pela skill 02 (FK interna à mesma tabela/módulo Core).

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `name` | String | Nome da pasta |
| `parent_id` | Integer, FK → `tesseract_playground_folder.id`, nullable | Auto-referência — N níveis (estilo Collections/Folders do Postman) |
| `created_by_user_id` | Integer, FK → `tesseract_user.id`, nullable | |
| `created_at` / `updated_at` | DateTime | |

Regra de exclusão: apagar uma pasta com filhos (sub-pastas ou requisições dentro) é **bloqueado** até que os filhos sejam movidos ou apagados primeiro — sem cascade automático.

### 2.5 `tesseract_playground_cookie_jar` [NOVO — Playground v2, seção 8]

Um jar por usuário, escopo global (não por pasta/coleção).

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `user_id` | Integer, FK → `tesseract_user.id`, unique | |
| `cookies_json` | JSON | Snapshot de `requests.Session().cookies`, serializado |
| `updated_at` | DateTime | Atualizado a cada execução HTTP que retornar `Set-Cookie` |

---

## 3. Correções obrigatórias em relação ao PyTeca original

### 3.1 [PENDENTE-SKILL → aprendizado já registrado sobre `db.create_all()`]

O PyTeca rodava `db.create_all()` em dev e só usava Alembic em
produção. Isso contraria um aprendizado já validado no próprio
Tesseract: `db.create_all()` não altera tabela existente, só cria
tabela nova — não é seguro como caminho de "dev". **Correção**: o
botão "Gerar" no Tesseract **sempre** passa por Flask-Migrate, em
qualquer ambiente. A migration é gerada e fica parada — quem aplica
(`flask db upgrade`) é o desenvolvedor, mesmo fluxo manual já usado
hoje para as demais migrations do projeto.

### 3.2 [PENDENTE-SKILL → skill 02, regra de FK entre módulos]

O combo de "tabela referenciada" do PyTeca era livre (projeto
monolítico, sem conceito de Addon isolado). **Correção**: o combo de
FK no Model Builder do Tesseract só lista, em runtime:
- tabelas já existentes no mesmo `target_addon_name`;
- `tesseract_user` (sempre permitido, skill 02).

Nunca lista tabela de outro Addon. Se `target_scope=new_addon` e ainda
não existe nenhum outro Model salvo no mesmo rascunho de Addon, a
lista de FK fica vazia até o segundo Model ser criado.

### 3.3 [DECIDIDO] Scaffold completo quando `target_scope` é `new_addon`/`new_feature`

"Gerar" roda, nesta ordem:
1. Checklist de manifesto da skill 03 (seção 6) — se falhar, nada é
   escrito em disco.
2. Estrutura de pastas da skill 01 (incluindo `menu_config.json` da
   skill 07, se aplicável).
3. `docs/technical/01-visao-geral.md` e `docs/manual/01-introducao.md`
   com **stub preenchido automaticamente** a partir de
   `manifest_draft_json.description`/`label` — nunca vazios, para já
   nascer conforme o checklist da skill 03. Revisão/expansão do
   conteúdo continua manual, depois.
4. Model `.py` com anotações (CrudGen) + `i18n/pt_BR.json` com as
   chaves extraídas dos `label_text` de cada campo.
5. Migration Flask-Migrate (seção 3.1) — nunca aplicada automaticamente.

---

## 4. RBAC (skill 00, convenção `<plural>.<acao>`)

| Permissão | Escopo |
|---|---|
| `model_definitions.create` | Criar/editar rascunho |
| `model_definitions.generate` | Disparar o botão "Gerar" (escreve arquivo + migration) |
| `model_definitions.view` | Ver lista/rascunhos |
| `playground_requests.execute` | Executar requisição HTTP no Playground |

---

## 5. API Playground → bridge com Model Builder

**[DECIDIDO]** Botão "Usar resposta como base de campos" em
`tesseract_playground_request`: lê `last_response_json` (objeto único,
ou primeiro item se for array), infere por tipo Python (`str`→
`string`, `int`→`integer`, `float`→`float`, `bool`→`boolean`, string
em formato ISO-8601 → `date`/`datetime`) e por presença/ausência entre
amostras (quando array, define `nullable`). Resultado pré-preenche o
editor de campos de um `tesseract_model_definition` (novo ou já
aberto) — nunca gera o Model direto do JSON sem passar pela tela de
revisão humana.

---

## 6. SQL Playground — restrição de segurança

**[DECIDIDO]** Somente leitura (`SELECT`), validado por parser antes
de executar — `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`TRUNCATE` e
qualquer DDL/DML são rejeitados antes de chegar ao banco, mesmo que o
usuário tenha a permissão `playground_requests.execute`.

**[DECIDIDO]** Duas travas independentes, propositalmente redundantes:
1. Permissão RBAC `playground_requests.execute` (controla quem acessa
   a tela).
2. `system_config` key `playground.sql_write_enabled` (bool, default
   `false`) — reservada para uma eventual liberação futura de
   escrita, **sem uso ativo nesta versão** (a validação de parser da
   seção 6 bloqueia escrita independentemente do valor desta flag;
   ativá-la sozinha não é suficiente para liberar escrita — exigiria
   também remover/alterar a validação de parser, decisão que não está
   tomada aqui).

---

## 7. Pendências desta skill

- [ABERTO] Escolha de parser SQL para validar "somente `SELECT`"
  (biblioteca/abordagem) — decisão de implementação, não de
  arquitetura; fica para quando a Fase de código desta skill for
  autorizada.
- [ABERTO] Nome de exibição definitivo do grupo de menu no `menu_config.json`
  do Core para estas duas Transações (não bloqueia o schema, só a
  label visível).

---

## 8. Playground v2 — Auth, Params, Pastas e Cookie Jar [DECIDIDO — adenda 2026-07-08]

### 8.0 Motivação (achado real, não hipotético)

O Playground do Patch C nasceu pensado para exercitar a própria API do
Tesseract. Em uso real para consumir **APIs externas de terceiros**,
apareceu um caso onde uma chamada autenticada retornava **404** no
Playground enquanto o mesmo teste, com as mesmas credenciais, funcionava
no Postman. Causa raiz: `tesseract_playground_request` só tinha `url`
(string única) — todo parâmetro de query (incluindo, em várias APIs,
o próprio token/key de autenticação) precisava ser colado à mão dentro
da URL, sem encoding automático. Um erro de `&`/espaço/encoding vira
URL malformada, e várias APIs externas respondem 404 genérico em vez
de 400/401 para isso — sintoma que parecia "autenticação rejeitada"
mas era, na real, "requisição montada errada antes de sair". A adenda
abaixo resolve isso estruturalmente (Query Params dedicados) e cobre,
junto, os demais pedidos de uso real (Auth dedicada, cookie/sessão
persistente, histórico organizável).

### 8.1 Fluxo de execução HTTP [DECIDIDO — substitui o fluxo simples do Patch C]

Textual (sem código nesta fase):

1. Monta a URL final concatenando a `url` base salva com os pares de
   `params_json` que estiverem `enabled=true`, com encoding correto
   (isso sozinho já elimina a causa raiz da seção 8.0).
2. Monta os headers finais combinando `headers_json` (livre, como já
   era) com o header derivado de `auth_type`/`auth_config`:
   - `bearer` → `Authorization: Bearer {token}`
   - `basic` → `Authorization: Basic {base64(username:password)}`
   - `api_key` → header cujo nome é `auth_config.header_name`, valor
     `auth_config.value`
   - `none` → nada é adicionado
3. Abre um `requests.Session()` (em vez de `requests.request()` avulso,
   como era no Patch C) e pré-carrega os cookies do
   `tesseract_playground_cookie_jar` do usuário logado, se existir.
4. Executa a requisição na sessão.
5. Persiste de volta o estado de cookies da sessão no jar do usuário
   (`cookies_json`, `updated_at`) — toda execução seguinte do mesmo
   usuário já parte com a sessão anterior, resolvendo o caso de "login
   funciona isolado, mas a próxima chamada perde a sessão".

### 8.2 Pastas (árvore) [DECIDIDO]

`tesseract_playground_folder` — árvore de N níveis (seção 2.4). A tela
de histórico do Playground passa a agrupar `tesseract_playground_request`
por `folder_id`, com requisições sem pasta (`folder_id IS NULL`)
listadas à parte, na raiz. Mover uma requisição de pasta é só um
UPDATE de `folder_id` — sem regra especial.

### 8.3 Apagar vs. Arquivar [DECIDIDO]

Duas ações independentes, nunca a mesma:
- **Arquivar** → `is_archived = true`. Some da lista principal, mas
  continua no banco, recuperável (desarquivar = `is_archived = false`).
- **Apagar** → DELETE físico da linha. Sem confirmação em duas etapas
  além do modal de confirmação padrão já usado nas demais telas do
  Core — não é entidade CrudGen, não segue soft-delete (skill 00,
  Adendo Fase 7a, mesma categoria de `CodeSnapshot`).

### 8.4 RBAC [DECIDIDO]

Nenhuma permissão nova. Reaproveita `playground_requests.execute` (já
existente, seção 4) para todas as ações novas (criar/mover pasta,
arquivar, apagar) — mesmo padrão já adotado na skill 08 para as telas
de admin do Core (permissão flat `admin`, sem fatiar por ação).

### 8.5 Segurança de `auth_config` [DECIDIDO — aceito como está, revisitar se necessário]

Token/senha em `auth_config` fica gravado em texto puro no histórico,
igual ao tratamento que `env_keys` de manifesto já recebe hoje (skill
03). Ferramenta de uso interno/admin, não exposta a usuário final —
suficiente para esta fase; só revisitar se virar exigência de
segurança mais adiante (ex.: mascarar no `to_dict()`/tela).

---

## 9. Pendências desta adenda (Playground v2)

- [ABERTO] Ordenação de requisições/sub-pastas dentro de uma pasta —
  por ora, ordena por `created_at`/nome; só adicionar `order_index` se
  o uso real pedir (mesmo princípio da skill 05 §2.2: "cresce só
  quando um caso real exigir").
- [ABERTO] Nome de exibição definitivo das novas ações na tela
  (rótulos de botão "Arquivar"/"Mover para pasta") — não bloqueia o
  schema, só a label visível (i18n, skill 00).
