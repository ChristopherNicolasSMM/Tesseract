# 01 — Visão Geral (Sistema)

## Propósito

Tesseract é o Hub modular (Core + Addons + Features + Plugins) que
unifica três projetos anteriores em uma única base:

- **PyTeca** — CrudGen (geração de CRUD a partir de model anotado),
  RBAC, versionamento de código gerado.
- **BrewStation** — motor de descoberta e registro de módulos.
- **DEVStationFlask** — transações, motor de regras, Designer
  drag-and-drop, OData.

Uso inicial: gestão de cervejaria caseira (`addon_brewstation`). Uso de
longo prazo: base reaproveitável para outros domínios.

## Estado atual (ver `BACKLOG.md` para o detalhe fase a fase)

| Camada | Status |
|---|---|
| Core (`ModuleManager`, `EventBus`, DB factory, logging, Migrations) | Pronto |
| RBAC + Usuários (+ telas de admin, Roles/Permissions) | Pronto |
| Versionamento (`CodeSnapshot`) + tela de histórico/diff/restauração | Pronto |
| CrudGen + Anotações (smart-list completo: filtro tipado/colunas/export) | Pronto |
| Páginas HTML de Core (login, home, perfil, tema claro/escuro) | Pronto |
| Catálogo de Transações (menu dinâmico, submenus colapsáveis) | Pronto |
| Gestão de Transações (`/admin/transactions/`) | Pronto |
| Motor de regras — grupo Validação (`/admin/field-rules/`) | Pronto |
| Designer visual drag-and-drop (`/admin/designer/`) | Pronto |
| OData — conexão + navegador de dados read-only (`/admin/odata/`) | Pronto |
| `addon_brewstation` — `feature_yeast_bank` (8 entidades) | Completo, com motor de viabilidade |
| `addon_brewstation` — `feature_device_manager` (4 entidades) | Completo (CRUD) |
| `addon_brewstation` — `feature_mash_control` (12 entidades) | CRUD completo, sem motor de controle em tempo real |
| Visibilidade/Cálculo (motor de regras) | Catalogado, sem função JS ainda |
| `screen_generator.py` (gerar tela do Designer a partir de OData) | Não iniciado — agora possível, Designer já existe |
| `integ_bfather` | Fora de escopo — aguardando reescrita dedicada |

## Dependências do Core

`Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `Flask-Migrate`/`Alembic`,
`openpyxl` (export Excel), `Jinja2` (via Flask), `psycopg2-binary`
(produção/Postgres). Ver `requirements.txt`.

## O que o Core expõe (`provides`)

- `core.module_manager.ModuleManager` — descoberta/registro de Addons,
  prefixo de tabela, sincronização de permissão e de transação,
  ChoiceLoader de templates.
- `core.event_bus.event_bus` — pub/sub síncrono em memória.
- `core.permissions.permission_required` — decorator de autorização.
- `core.crudgen.generator.generate()` — geração de CRUD a partir de
  model anotado (filtro tipado, colunas configuráveis por usuário,
  export CSV/Excel, validação client-side — ver skill 04/seção CrudGen).
- `core.versioning.snapshot_if_needed()` + `core.snapshot_service.py`
  — versionamento, diff e restauração.
- `core.transactions_sync.py` — catálogo de transações navegáveis.
- `core.rules_catalog.py` + `static/js/rule_engine.js` — catálogo de
  regras de negócio e motor de validação client-side.
- `core.odata.connection_manager.py` — conexão e descoberta de
  metadata de servidores OData V4 externos.
- `migrate` (Flask-Migrate) — `python run.py db migrate`/`db upgrade`,
  para qualquer ALTER em tabela já existente.

## Páginas HTML disponíveis

| Rota | O que é |
|---|---|
| `/login` | Login |
| `/` | Home — menu dinâmico vindo do catálogo de Transações |
| `/perfil/` | Dados próprios, troca de senha, tema claro/escuro |
| `/admin/users/` | Gestão de usuários |
| `/admin/roles/` | Gestão de Roles/Permissions |
| `/admin/versioning/` | Histórico/diff/restauração de código |
| `/admin/field-rules/` | Regras de validação anexadas a campos |
| `/admin/transactions/` | Gestão do catálogo de Transações (menu) |
| `/admin/odata/` | Conexões OData + navegador de dados read-only |
| `/admin/designer/` | Designer visual (canvas drag-and-drop) |
| `/designer/<slug>` | Execução de uma página montada no Designer |
| `/<addon>/<entidade>/` | CRUD de cada entidade gerada pelo CrudGen |

Todas as rotas `/admin/*` exigem a permissão `admin`. Páginas HTML sem
sessão válida redirecionam para `/login`; rotas `/api/*` retornam 401
JSON em vez de redirecionar.

## Decisões e correções importantes ao longo do caminho

- **Prefixo de tabela** é aplicado no registro (`ModuleManager`), não
  na geração (`CrudGen`) — só assim sobrevive a um reboot normal.
- **FK cross-Feature dentro do mesmo Addon é permitida** (skill 02) —
  só FK entre Addons diferentes é proibida.
- **Nome curto de tabela deve ser único em todo o Addon**, não só na
  Feature — `ModuleManager` importa tudo antes de prefixar qualquer
  coisa (necessário pra FK cross-Feature funcionar).
- **`db.create_all()` nunca altera tabela existente** — só cria a que
  não existe. Qualquer coluna nova em model já existente exige
  `python run.py db migrate && db upgrade` (Flask-Migrate).
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

## Documentos relacionados

- [02-diagrama-c4.md](02-diagrama-c4.md)
- [03-fluxos.md](03-fluxos.md)
- [04-modelo-de-dados.md](04-modelo-de-dados.md)
- [05-casos-de-uso.md](05-casos-de-uso.md)
- [06-manutencao-e-expansao.md](06-manutencao-e-expansao.md)
- [07-catalogo-de-transacoes.md](07-catalogo-de-transacoes.md) *(gerado, não editar à mão)*
