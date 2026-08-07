# 16 — Designer: Ações, Ação de Dado, Provedor OData Local e Substituição de Tela

> **REVISÃO (Fase 12, 2026-08-05): o construtor visual foi REMOVIDO.**
> As seções 1 (catálogo de Ações), 4 (Tier 1/2 de componente) e o que
> a Fase 11 acrescentou (árvore de componentes, catálogo de
> propriedades) **não descrevem mais o código real** — ficam como
> registro histórico da decisão e do que foi tentado.
>
> **O que continua valendo e em produção:** seção 2 (Ação de Dado,
> `tesseract_designer_data_action`), seção 3 (Provedor OData Local,
> `@odata_expose`, atalho em processo) e seção 5 (substituição de tela
> do CrudGen no menu). Esses três nasceram junto do Designer mas são
> independentes dele.
>
> **Por que foi removido:** três ciclos de correção não fizeram o
> aninhamento por drag-and-drop funcionar de forma confiável. Causa de
> fundo: a suíte de testes do projeto não executa navegador, então
> todo bug de interação JS só aparecia no uso real, um por vez.
> Decisão de escopo: construtor visual é um produto inteiro, não uma
> feature — e num time onde quem monta as telas já programa, escrever
> HTML é mais rápido e previsível. A página customizada passou a ser
> `DesignerPage.content_html`, escrita à mão, com `/freestyle/` (Fase
> 13, skill 18) como referência viva e testada, mais os modelos
> estáticos `static/modelo_paginas_nice_admin/_modelo-pagina-basico.html`
> e `_modelo-pagina-completo.html` (Fase 12), e o fluxo de consumo de
> dados documentado na skill 17.
>
> **Se um dia isso voltar**, o pré-requisito é teste de navegador
> (Playwright ou equivalente) antes da primeira linha de canvas.

> **Status: EXECUTADA (Fase 10, Patches 1–6, 2026-07-31).** Nasceu de
> uma rodada de planejamento sobre `/admin/designer/` (Designer visual
> drag-and-drop, Fase 7c) — pedido original: dar a ele ações/eventos,
> consumo de dado com regras claras, e a capacidade de substituir uma
> tela do CrudGen quando configurado pra isso. Documento escrito
> **depois** da implementação (diferente da skill 05, que nasceu como
> proposta) — todo `[EXECUTADO]` aqui já está em código real, testado.
>
> Mapeamento de componente por exemplo do template NiceAdmin:
> `mapeamento_niceadmin_designer.md` (entregue antes do Patch 1,
> raiz do repositório — referência de planejamento, não parte do
> `docs/skills/`).

---

## 1. Ações — catálogo em duas camadas [EXECUTADO]

`core/actions_catalog.py` (mesmo padrão de `core/rules_catalog.py`):
metadado só em código, sem tabela — `ACTION_CATALOG`, lista de dict
com `id`/`label`/`icon`/`runs_on`/`params`/`description`.

| Ação | `runs_on` | Onde roda de fato |
|---|---|---|
| `navigate` | `client` | `static/js/actions_engine.js` |
| `show_message` | `client` | idem — reaproveita `window.__tesseractToast` (skill 15) |
| `set_component_value` | `client` | idem |
| `toggle_component` | `client` | idem |
| `call_data_action` | `server` | `POST /admin/designer/data-action/<id>/execute` |

**Regra de ouro desta skill**: toda Ação que toca dado/API roda
*sempre* no servidor — nunca client-side, porque a conexão por trás
pode envolver credencial (`ODataConnection.auth_value`). É por isso
que existe só **uma** Ação server-side (`call_data_action`) em vez de,
por exemplo, uma Ação por operação (`query_data`/`update_data`) — o
tipo de operação já vive na `DesignerDataAction` referenciada, não
precisa duplicar no catálogo de Ação.

Ligação evento → Ação fica embutida em `DesignerComponent.events`
(JSON que existia desde a Fase 7c, morto até o Patch 3 — nenhum
controller/template lia ou escrevia nele):

```json
{"onClick": [
  {"action_type": "call_data_action", "params": {"data_action_id": 3, "key": "42", "payload": "{}"}},
  {"action_type": "show_message", "params": {"message": "Salvo!", "variant": "success"}}
]}
```

Ações no mesmo evento rodam **em sequência**; se uma `call_data_action`
falhar (permissão negada, entidade não exposta, erro do servidor), a
cadeia para e mostra um toast de erro automático — as ações seguintes
não rodam.

`EVENT_TYPES = ("onClick", "onChange", "onLoad")` já existe no
catálogo, mas só `onClick` é disparado no runtime hoje (só `button`
tem interação de clique) — `onChange`/`onLoad` ficam prontos pra
quando um tipo de componente que os dispare existir.

---

## 2. Ação de Dado — `tesseract_designer_data_action` [EXECUTADO]

Configuração **reutilizável** de acesso a dado — nunca digitada à mão
duas vezes (mesmo princípio de tabela-de-configuração já usado por
`FieldRule`/`ODataConnection`). Aponta sempre pra uma
`ODataConnection` (local ou externa — ver seção 3) + `entity_name` +
`operation` (`query`/`update` implementados; `create`/`delete` já
estão no schema mas o motor de execução devolve `501` — sem fingir
que funciona) + `static_params` (JSON livre, ex. um `$filter` fixo) +
`permission_required` (Role via `User.has_permission()` — `NULL` =
público; **sem** permissão por usuário individual nesta fase, decisão
do usuário registrada em conversa: "vamos seguir com o que existe,
que é por grupo de usuários").

---

## 3. Provedor OData Local [EXECUTADO]

Antes da Fase 10, `ODataConnectionManager` (Fase 8) só **consumia**
servidores OData externos. Pra um componente do Designer poder mostrar
dado do próprio Tesseract pelo mesmo mecanismo (decisão do usuário:
"só via conexões OData, mesmo para dados que já estão no próprio
banco"), o Tesseract precisou virar **também provedor**:

- `@odata_expose("<entity_name>", permission_required="<opcional>")`
  (`annotations/__init__.py`, mesmo padrão de `@permission`) — **opt-in
  por entidade**, decisão do usuário. Sem a anotação, a entidade nunca
  aparece no provedor local, mesmo com o Addon ativo.
- `core/odata_provider/registry.py` — descobre em runtime todo model
  com `@odata_expose`, varrendo `db.Model.registry.mappers` (não
  precisa saber a que Addon/Feature pertence).
- `core/odata_provider/metadata.py` — monta o metadata no **mesmo
  formato JSON** que o consumidor da Fase 8 já reconhecia
  (`{"entities": [...]}`) — nenhum formato paralelo. Enriquecido com
  um bloco `"ui"` (`enum_fields`/`weak_refs`) que o OData EDMX padrão
  não carrega, usando informação que `@enum_field`/`@weak_ref`
  (skill 11) já tinham pronta.
- `core/odata_provider/service.py` — `query_local()`/`patch_local()`,
  checagem de permissão, `$top`/`$skip`/`$orderby`/`$filter` mínimo
  (só `campo eq valor`, sem parser OData completo — cresce quando um
  caso real pedir).
- `api/routes/core/odata_provider.py` — `/api/odata-provider/...`,
  pra consumidor **externo** de verdade (sempre atrás de login, mesmo
  padrão de `/api/options`).

### Atalho em processo (decisão técnica registrada em conversa)

`ODataConnection.is_local` marca a conexão auto-seedada (idempotente,
`core/odata_local_seed.py`) que representa o próprio Tesseract.
Quando uma Ação de Dado aponta pra essa conexão,
`ODataConnectionManager.fetch_metadata()`/`query()`/`patch()` **pulam
o HTTP inteiramente** e chamam `odata_provider/service.py` direto, em
processo — evita o Tesseract fazer requisição HTTP pra ele mesmo a
cada carregamento de página. Do ponto de vista do Designer (a tabela,
a UI, o evento) é o mesmo mecanismo único; a otimização é interna e
invisível.

**Achado real (validação do seed no boot)**: `run.py` (FlaskGroup)
roda `create_app()` — com todos os seeds de boot — **antes** de
qualquer subcomando `flask db ...`, inclusive `db upgrade`. O seed da
conexão local precisou de uma guarda defensiva
(`try/except OperationalError`) pra não quebrar o boot de uma
instalação existente com a migration ainda pendente — mesmo espírito
defensivo das migrations (`_column_exists`), só que em runtime.

---

## 4. Componentes — Tier 1 e Tier 2 [EXECUTADO]

16 tipos hoje (6 da Fase 7c + 10 da Fase 10). Mapeamento completo,
exemplo NiceAdmin → componente → tier, em
`mapeamento_niceadmin_designer.md`. Resumo:

| Tier | Componentes | Bind de dado |
|---|---|---|
| 0 (Fase 7c) | `heading`, `label`, `textbox`, `button`, `image`, `divider` | Só `textbox` (regras de Validação) |
| 1 (Patch 4) | `select`, `checkbox`, `radio`, `form_container`, `datagrid` | Sim — via Ação de Dado |
| 2 (Patch 5) | `card`, `alert`, `badge`, `progress_bar`, `list` | Só `list` |

`form_container` e `datagrid`/`list` sempre buscam dado via
`POST /admin/designer/data-action/<id>/execute` (o mesmo endpoint
server-side de `call_data_action`, seção 1) — nunca falam direto com
um provedor OData do navegador. `static/js/data_binding.js` concentra
essa lógica (`initSelects`/`initRadioGroups`/`initFormContainers`/
`initDatagrids`/`initLists`).

**`form_container` não é aninhamento real de DOM/schema** — casa
campo por nome (`name` do input) com a chave do registro retornado,
filtrando os componentes da página que caem geometricamente dentro do
retângulo do container (x/y/width/height do canvas). Coerente com o
canvas livre que o Designer já usa desde a Fase 7c — não precisou de
uma coluna `parent_component_id` nova.

`datagrid` usa `simple-datatables` (já vendorizado desde a correção de
caminho de `static/modelo_paginas_nice_admin/`, início desta rodada de
planejamento) — inicialização **manual**, depois de popular as linhas
via JS, não depende do auto-init do `main.js` de referência (que nunca
foi incluído em `base.html`).

`progress_bar` fica **estático** nesta leva (`value`/`min`/`max`
fixos) — vincular a outro componente em runtime é a regra "Controlar
ProgressBar" do catálogo de Cálculo (`core/rules_catalog.py`), ainda
`connected: False`, fora do escopo da Fase 10.

---

## 5. Substituição de tela CrudGen [EXECUTADO]

`DesignerPage` ganhou `replaces_entity_key` + `replaces_view`
(`"manage"`/`"detail"`) + `replace_in_menu` (checkbox).

**Achado real, corrigido no Patch 6**: o comentário original (Patch 1)
dizia pra usar o **singular** do `@odata_expose` como
`replaces_entity_key` — errado. A convenção certa é o **plural**,
mesma usada em `FieldRule.entity_key`/`UserListPreference.list_key`/
prefixo de `Permission` de toda entidade do CrudGen (ex.:
`"yeast_strains"`, não `"yeast_strain"`). `core/designer_menu_override.py`
resolve a `Transaction` a trocar via
`permission_required == "<replaces_entity_key>.list"` — mesmo padrão
de permissão automática (Camada 1) que o CrudGen já sincroniza pra
toda entidade gerada.

**Mecanismo**: troca só o item de **menu**
(`Transaction.route`) — a rota original do CrudGen nunca é tocada nem
desregistrada. Quem digitar a URL antiga na mão continua vendo a tela
crua do CrudGen (decisão do usuário: precisa ficar acessível pra
debug/conferência de valores).

**Auto-curativo, sem guardar estado**: o resolver sempre faz um
resync completo (`sync_all_transactions()` + `sync_core_transactions()`
— código lidera, banco segue) antes de reaplicar os overrides ainda
válidos. Despublicar a página, desmarcar o checkbox, ou apagar a
página restaura a rota original sozinho, no próximo boot **ou** na
próxima ação de publicar/salvar/apagar (o resolver roda nos três
lugares, não só no boot).

Só `replaces_view == "manage"` tem Transaction de menu pra trocar —
uma tela de "detail" nunca vira item de menu por conta própria (é
acessada por link dentro do "manage"). O campo existe no schema,
pronto pra quando um mecanismo de override de link "ver detalhe"
existir — não implementado nesta fase.

**Achado real**: não existia nenhuma rota que escrevesse
`replaces_entity_key`/`replaces_view`/`replace_in_menu` até o Patch 6
— os campos existiam desde o Patch 1, mas eram graváveis só via shell.
Corrigido com `POST /admin/designer/<id>/settings` + painel
"Configurações da página" no editor.

---

## 6. Outros achados reais registrados ao longo da Fase 10

- **Patch 3**: `GET /admin/designer/<id>/edit` quebrava sempre que a
  página já tinha componente — `page.components | map('tojson')`
  tentava serializar objeto ORM direto (nunca funciona no Flask/Jinja).
  Pré-existente desde a Fase 7c, nenhum teste chamava essa rota até
  então. Corrigido serializando no controller (`components_json`)
  antes de mandar pro template.
- **Patch 2**: 3 testes de `test_phase8_odata.py` dependiam
  implicitamente de `ODataConnection.query.first()` sem filtro
  (assumiam a tabela vazia antes do teste) — o seed da conexão local
  (sempre presente) expôs esse acoplamento. Corrigido filtrando por
  nome nos testes, não mudando produção.
- **Patch 1**: `run.py` roda `create_app()` antes de qualquer
  subcomando `flask db ...` — todo seed de boot que depende de uma
  coluna nova precisa tolerar ela ainda não existir (ver seção 3).

---

## 7. Roadmap de patches (para referência histórica)

| Patch | Escopo | Status |
|---|---|---|
| 1 | Schema completo (`tesseract_designer_data_action`, `is_local`, `replaces_*`, `@odata_expose`) | [EXECUTADO] |
| 2 | Provedor OData local — endpoint HTTP + atalho em processo | [EXECUTADO] |
| 3 | `core/actions_catalog.py` + execução server-side + UI de eventos no editor | [EXECUTADO] |
| 4 | Tier 1 de componente (`select`/`checkbox`/`radio`/`form_container`/`datagrid`) | [EXECUTADO] |
| 5 | Tier 2 de componente (`card`/`alert`/`badge`/`progress_bar`/`list`) | [EXECUTADO] |
| 6 | Substituição de tela CrudGen no menu (resolver real) | [EXECUTADO] |
| 7 | Documentação (esta skill + `docs/technical`/`docs/manual`) | [EXECUTADO] |

Fora do escopo da Fase 10, registrado como pendência conhecida:

- Tier 3 de componente (`tabs`/`accordion`/`chart`/`rich_text`/
  `carousel`; modal como Ação em vez de componente de canvas).
- Motor de Cálculo/Visibilidade do catálogo de regras — `progress_bar`
  fica estático até isso existir.
- `operation="create"`/`"delete"` em `DesignerDataAction` — schema
  pronto, motor de execução devolve `501`.
- `replaces_view="detail"` — schema pronto, sem resolver de link
  "ver detalhe" ainda.
- `screen_generator.py` (gerar `DesignerPage`/`DesignerComponent`
  inteira a partir de metadata OData, DEVStationFlask) — continua não
  portado; a Fase 10 deu os componentes soltos pra montar essa tela à
  mão, não a geração automática.
