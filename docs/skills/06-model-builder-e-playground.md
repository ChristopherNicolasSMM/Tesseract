# 06 — Model Builder Visual + API/SQL Playground

> **Status: SKILL FORMALIZADA (fase de decisão, 2026-07-01).** Nasceu de
> uma conversa sobre a ausência de uma entrada de CrudGen no menu do
> Tesseract. Análise do `BACKLOG.md` do PyTeca (seção "Model Builder
> Visual") mostrou que o projeto original já resolvia isso — esta skill
> herda o desenho, com três correções obrigatórias em relação à
> arquitetura tri-nível do Tesseract (seção 3) que não existiam no
> PyTeca (projeto monolítico, sem Core/Addon/Feature/Plugin).
>
> Como toda skill nova, tem o mesmo peso normativo das skills 00–04:
> qualquer implementação que divergir do que está aqui precisa ajustar
> este documento antes (regra de ouro, skill 00).
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

### 2.3 `tesseract_playground_request`

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `name` | String | |
| `http_method` | String | |
| `url` | String | |
| `headers_json` / `body_json` | JSON | |
| `last_response_json` | JSON, nullable | Base para o bridge da seção 5 |
| `last_status_code` | Integer, nullable | |
| `created_by_user_id` | Integer, FK → `tesseract_user.id` | |
| `created_at` / `updated_at` | DateTime | |

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
