# 01 — Visão Geral (Sistema)

## Propósito

Tesseract é o Hub modular (Core + Addons + Features + Plugins) que
unifica três projetos anteriores em uma única base:

- **PyTeca** — CrudGen (geração de CRUD a partir de model anotado),
  RBAC, versionamento de código gerado.
- **BrewStation** — motor de descoberta e registro de módulos.
- **DEVStationFlask** — transações, motor de regras, Designer
  drag-and-drop, OData (parcialmente portado — ver estado abaixo).

Uso inicial: gestão de cervejaria caseira (`addon_brewstation`). Uso de
longo prazo: base reaproveitável para outros domínios.

## Estado atual (ver `BACKLOG.md` para o detalhe fase a fase)

| Camada | Status |
|---|---|
| Core (`ModuleManager`, `EventBus`, DB factory, logging, Migrations) | Pronto |
| RBAC + Usuários (+ telas de admin, Roles/Permissions) | Pronto |
| Versionamento (`CodeSnapshot`) + tela de histórico/diff/restauração | Pronto |
| CrudGen + Anotações (smart-list-lite: filtro/paginação) | Pronto |
| Páginas HTML de Core (login, home, perfil, tema claro/escuro) | Pronto |
| `addon_brewstation` — `feature_yeast_bank` (8 entidades) | Completo |
| `addon_brewstation` — `feature_device_manager` (4 entidades) | Completo (CRUD) |
| `addon_brewstation` — `feature_mash_control` (12 entidades) | CRUD completo, sem motor de controle em tempo real |
| Catálogo de Transações (menu dinâmico) | Pronto (Fase 7a) |
| Motor de regras (Fase 7b) | Não iniciado |
| Designer visual drag-and-drop (Fase 7c) | Não iniciado |
| OData / Screen Generator (Fase 8) | Não iniciado |
| `integ_bfather` | Fora de escopo — aguardando reescrita dedicada |

## Dependências do Core

`Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `Flask-Migrate`/`Alembic`,
`Jinja2` (via Flask), `psycopg2-binary` (produção/Postgres). Ver
`requirements.txt`.

## O que o Core expõe (`provides`)

- `core.module_manager.ModuleManager` — descoberta/registro de Addons,
  prefixo de tabela, sincronização de permissão e de transação.
- `core.event_bus.event_bus` — pub/sub síncrono em memória.
- `core.permissions.permission_required` — decorator de autorização.
- `core.crudgen.generator.generate()` — geração de CRUD a partir de
  model anotado (com filtro/paginação embutidos — smart-list-lite).
- `core.versioning.snapshot_if_needed()` + `core.snapshot_service.py`
  — versionamento, diff e restauração.
- `core.transactions_sync.py` — catálogo de transações navegáveis.
- `migrate` (Flask-Migrate) — `python run.py db migrate`/`db upgrade`,
  para qualquer ALTER em tabela já existente.

## Páginas HTML disponíveis

| Rota | O que é |
|---|---|
| `/login` | Login |
| `/` | Home — menu dinâmico vindo do catálogo de Transações |
| `/perfil/` | Dados próprios, troca de senha, tema claro/escuro |
| `/admin/users/` | Gestão de usuários (admin) |
| `/admin/roles/` | Gestão de Roles/Permissions (admin) |
| `/admin/versioning/` | Histórico/diff/restauração de código (admin) |
| `/<addon>/<entidade>/` | CRUD de cada entidade gerada pelo CrudGen |

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

## Documentos relacionados

- [02-diagrama-c4.md](02-diagrama-c4.md)
- [03-fluxos.md](03-fluxos.md)
- [04-modelo-de-dados.md](04-modelo-de-dados.md)
- [05-casos-de-uso.md](05-casos-de-uso.md)
- [06-manutencao-e-expansao.md](06-manutencao-e-expansao.md)
