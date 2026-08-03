# 01 — Visão Geral (Sistema)

## Propósito

Tesseract é o Hub modular (Core + Addons + Features + Plugins) que
unifica três projetos anteriores em uma única base:

- **PyTeca** — CrudGen (geração de CRUD a partir de model anotado),
  RBAC, versionamento de código gerado.
- **BrewStation** — motor de descoberta e registro de módulos.
- **DEVStationFlask** — transações, motor de regras, Designer
  drag-and-drop, OData.

Uso inicial: gestão de cervejaria caseira (`addon_brewstation`) +
gestão de estoque (`addon_estoque`) + integração com dispositivos IoT
via MQTT (`addon_device_manager`). Uso de longo prazo: base
reaproveitável para outros domínios.

## Estado atual (ver `BACKLOG.md` para o detalhe fase a fase)

| Camada | Status |
|---|---|
| Core (`ModuleManager`, `EventBus`, DB factory, logging, Migrations) | Pronto |
| Auto-descoberta de módulos (skill 09) — `addon.py`/`feature.py` sem wiring manual | Pronto |
| RBAC + Usuários (+ telas de admin, Roles/Permissions) | Pronto |
| Versionamento (`CodeSnapshot`) + tela de histórico/diff/restauração | Pronto |
| CrudGen + Anotações (smart-list completo: filtro tipado/colunas/export) | Pronto |
| Referência fraca cross-Addon + `display_field` (skill 11) | Pronto |
| Páginas HTML de Core (login, home, perfil, tema claro/escuro) | Pronto |
| Catálogo de Transações + Menu **hierárquico** em árvore (skill 10) | Pronto |
| Gestão de Transações (`/admin/transactions/`) | Pronto |
| Configurações de Menu (`/admin/menu-settings/`) — ordem/colapso/ícone por nível | Pronto |
| Preferência pessoal de menu (`/perfil/menu-preferencias`) | Pronto |
| Motor de regras — grupo Validação (`/admin/field-rules/`) | Pronto |
| Visibilidade/Cálculo (motor de regras) | Catalogado, sem função JS ainda |
| Designer visual drag-and-drop (`/admin/designer/`) | Pronto — canvas, 16 tipos de componente (Tier 1+2, Fase 10), Ações por evento, substituição de tela CrudGen |
| Ações do Designer (catálogo + execução server-side) — Fase 10 | Pronto — `core/actions_catalog.py`, endpoint `/admin/designer/data-action/<id>/execute` |
| Ação de Dado (`tesseract_designer_data_action`) — Fase 10 | Pronto — configuração reutilizável de acesso a dado via `ODataConnection`, sempre executada no servidor |
| Provedor OData local (`/api/odata-provider/`) — Fase 10 | Pronto — expõe entidades `@odata_expose`, atalho em processo (sem HTTP) quando a conexão é local |
| Substituição de tela CrudGen pelo Designer — Fase 10 | Pronto — troca só o item de MENU; rota original do CrudGen nunca é removida |
| OData — conexão + navegador de dados read-only (`/admin/odata/`) | Pronto (2 bugs de descoberta/rota corrigidos, ver BACKLOG.md) |
| Model Builder Visual (`/admin/model-builder/`) | Pronto — cria Model em Addon/Feature existente ou novo, gera via CrudGen |
| API/SQL Playground v2 (`/admin/playground/`) | Pronto — Auth, Query Params, pastas em árvore, cookie jar por usuário |
| Logging/Observabilidade admin (`/admin/logs/`) — skill 08 | Pronto |
| Sistema de Tasks/Jobs agendados (`/admin/tasks/`) | Pronto |
| EventBus (`core/event_bus.py`) — único canal de comunicação cross-Addon (skill 14) | Pronto |
| `addon_brewstation` — `feature_yeast_bank` (8 entidades) | Completo, com motor de viabilidade |
| `addon_brewstation` — `feature_mash_control` (18 entidades) | CRUD completo + motor de automação reativo via EventBus |
| `addon_brewstation` — `feature_ingredientes`/`feature_envase`/`feature_brew_father` | Completo (CRUD) |
| `addon_device_manager` (promovido de Feature, skill 05) | Completo — MQTT (LWT agregado), API `get_value`/`set_value`/`on_change` |
| `addon_estoque` (Material/Composição/Movimentação/Saldo + lookups) | Completo |
| `screen_generator.py` (gerar tela do Designer inteira a partir de metadata OData) | Não iniciado — diferente da Fase 10 (que dá os componentes soltos, não a geração automática de página) |
| Fase F skill 05 (validação ponta a ponta com `tesseract-device-bridge` real) | Pendente — repositório separado |

## Dependências do Core

`Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `Flask-Migrate`/`Alembic`,
`openpyxl` (export Excel), `Jinja2` (via Flask), `psycopg2-binary`
(produção/Postgres), `paho-mqtt` (device_manager), `requests`
(Playground HTTP), `sqlparse` (validação de SQL somente-leitura no
Playground). Ver `requirements.txt` (UTF-16LE — ver skill 00/BACKLOG).

## O que o Core expõe (`provides`)

- `core.module_manager.ModuleManager` — descoberta/registro de Addons,
  prefixo de tabela, sincronização de permissão e de transação,
  ChoiceLoader de templates, auto-descoberta (skill 09).
- `core.event_bus.event_bus` — pub/sub síncrono em memória, **único**
  canal permitido de comunicação entre Addons diferentes (skill 14).
- `core.permissions.permission_required` — decorator de autorização.
- `core.crudgen.generator.generate()` — geração de CRUD a partir de
  model anotado (filtro tipado, colunas configuráveis por usuário,
  export CSV/Excel, validação client-side, referência fraca
  cross-Addon com `display_field` — skill 11).
- `core.versioning.snapshot_if_needed()` + `core.snapshot_service.py`
  — versionamento, diff e restauração.
- `core.transactions_sync.py` — catálogo de transações navegáveis, em
  **árvore** (skill 10) — `parent_id`/`order_index`/`is_folder`.
- `core.rules_catalog.py` + `static/js/rule_engine.js` — catálogo de
  regras de negócio e motor de validação client-side.
- `core.odata.connection_manager.py` — conexão e descoberta de
  metadata de servidores OData V4 externos (XML/JSON EDMX + formato
  customizado com fallback de pluralização/override manual); atalho
  em processo (sem HTTP) quando `ODataConnection.is_local` — Fase 10.
- `core.odata_provider.*` — provedor OData do próprio Tesseract (Fase
  10): `registry.py` descobre entidades `@odata_expose`,
  `metadata.py` monta o schema (enriquecido com enum/weak_ref em
  `ui`), `service.py` executa `query`/`patch` com permissão via Role.
- `core.actions_catalog.py` + `static/js/actions_engine.js` — Ações
  disparáveis por evento de componente do Designer (Fase 10):
  `navigate`/`show_message`/`set_component_value`/`toggle_component`
  (client-side) e `call_data_action` (server-side, único ponto que
  toca credencial).
- `core.designer_menu_override.py` — resolve o checkbox
  `DesignerPage.replace_in_menu`, trocando o item de menu de uma tela
  do CrudGen pela DesignerPage publicada (Fase 10) — nunca a rota em
  si, que continua acessível direto.
- `services/core/model_builder_service.py` — rascunho + geração de
  Model novo em Addon/Feature existente ou novo (scaffold completo).
- `services/core/playground_service.py` — execução de requisição HTTP
  (com Auth/Params/cookie jar) e SQL somente-leitura, com bridge pro
  Model Builder.
- `services/core/menu_preference_service.py` — árvore de menu,
  overrides de ordem/colapso globais e por usuário, profundidade
  máxima de ícone.
- `services/core/task_service.py` + `TaskRegistry` — jobs agendados.
- `migrate` (Flask-Migrate) — `python run.py db migrate`/`db upgrade`,
  para qualquer ALTER em tabela já existente ou CREATE de tabela nova
  de Core (ver nota de `db.create_all()` vs. Alembic abaixo).

## Páginas HTML disponíveis

| Rota | O que é |
|---|---|
| `/login` | Login |
| `/` | Home — menu dinâmico em árvore vindo do catálogo de Transações |
| `/perfil/` | Dados próprios, troca de senha, tema claro/escuro |
| `/perfil/menu-preferencias` | Preferência pessoal de ordem/colapso do menu |
| `/admin/users/` | Gestão de usuários |
| `/admin/roles/` | Gestão de Roles/Permissions |
| `/admin/versioning/` | Histórico/diff/restauração de código |
| `/admin/field-rules/` | Regras de validação anexadas a campos |
| `/admin/transactions/` | Gestão do catálogo de Transações (árvore, promover/rebaixar) |
| `/admin/menu-settings/` | Padrão global de ordem/colapso/ícone do menu |
| `/admin/odata/` | Conexões OData + navegador de dados read-only |
| `/admin/model-builder/` | Model Builder Visual — rascunho de campos + geração via CrudGen |
| `/admin/playground/` | API/SQL Playground — testar requisições HTTP externas e SQL somente-leitura |
| `/admin/logs/` | Consulta/gestão de logs (globais e de integração por Addon) |
| `/admin/tasks/` | Jobs agendados (criar/pausar/rodar agora/histórico) |
| `/admin/designer/` | Designer visual (canvas drag-and-drop) |
| `/admin/designer/data-action/<id>/execute` | Execução server-side de uma Ação de Dado (Fase 10) |
| `/api/odata-provider/` | Provedor OData local — entidades `@odata_expose` (Fase 10) |
| `/designer/<slug>` | Execução de uma página montada no Designer |
| `/<addon>/<entidade>/` | CRUD de cada entidade gerada pelo CrudGen |

Todas as rotas `/admin/*` exigem a permissão `admin` (ou, no caso do
Playground, `playground_requests.execute`). Páginas HTML sem sessão
válida redirecionam para `/login`; rotas `/api/*` retornam 401 JSON em
vez de redirecionar.

## Decisões e correções importantes ao longo do caminho

- **Prefixo de tabela** é aplicado no registro (`ModuleManager`), não
  na geração (`CrudGen`) — só assim sobrevive a um reboot normal.
- **FK cross-Feature dentro do mesmo Addon é permitida** (skill 02) —
  só FK entre Addons diferentes é proibida; nesse caso usa-se
  referência fraca (Integer sem FK, resolvida por `display_field`
  único — skill 11) ou EventBus.
- **Nome curto de tabela deve ser único em todo o Addon**, não só na
  Feature — `ModuleManager` importa tudo antes de prefixar qualquer
  coisa (necessário pra FK cross-Feature funcionar).
- **`db.create_all()` nunca altera tabela existente** — só cria a que
  não existe. Qualquer coluna nova em model já existente exige
  `python run.py db migrate && db upgrade` (Flask-Migrate).
- **`db.create_all()` roda em todo boot, inclusive `flask db ...`** —
  corrigido (ver BACKLOG.md) pra pular esse `create_all()` quando o
  processo é um comando `flask db`, senão ele "ganha a corrida" do
  Alembic em qualquer migration que crie tabela nova.
- **PK Integer + `external_id` UUID** para entidades que precisam de
  identificador estável externo (ex.: dispositivos IoT) — nunca UUID
  como PK.
- **Tema escuro usa `html[data-theme="dark"]`**, não classe no body —
  é a convenção real do `style_dark.css` herdado do PyTeca/BrewStation.
  Toda página define `<meta name="color-scheme">` explicitamente, para
  o navegador não "ajudar" com dark mode forçado por fora do nosso
  controle.
- **Transação vinda do código só permite ativar/desativar pela tela**
  — `sync_transaction()` sobrescreve label/rota/ícone a partir do
  código a cada boot; edição completa só é segura para transações
  manuais (`source_module="manual"`).
- **EventBus é o único canal cross-Addon** — nenhum callback paralelo
  em memória é permitido (achado real na Fase E da skill 05, corrigido
  na Fase G).
- **Query Params sempre estruturados, nunca dentro da URL crua** — o
  Playground v1 deixava colar tudo na URL, o que gerava 404 por
  encoding errado; v2 corrigiu com campo dedicado (ver skill 06 §8).

## Documentos relacionados

- [02-diagrama-c4.md](02-diagrama-c4.md)
- [03-fluxos.md](03-fluxos.md)
- [04-modelo-de-dados.md](04-modelo-de-dados.md)
- [05-casos-de-uso.md](05-casos-de-uso.md)
- [06-manutencao-e-expansao.md](06-manutencao-e-expansao.md)
- [07-catalogo-de-transacoes.md](07-catalogo-de-transacoes.md) *(gerado, não editar à mão)*
