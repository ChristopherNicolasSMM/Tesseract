# Backlog — Tesseract

> Lista viva. Itens migram de `Planejado` → `Em andamento` → `Concluído`.
> Cada item referencia a Fase do plano de construção (ver
> `README.md` → seção Fases) e a skill/doc relevante quando aplicável.

## Fase 0 — Scaffold

- [x] Estrutura de pastas do Core (`core/`, `annotations/`, `model/core/`,
      `addons/`, `plugins/`, `static/`, `docs/`)
- [x] `app_factory.py` mínimo — sobe e responde em `/health`
- [x] `wsgi.py`, `requirements.txt`, `.gitignore`
- [x] `README.md` raiz com navegação para `docs/skills/`, `docs/technical/`,
      `docs/manual/`
- [x] Skills 00–04 copiadas para `docs/skills/`
- [x] `BACKLOG.md` (este arquivo)
- [ ] Pasta `static/` vazia — aguardando você subir os assets do Nice Admin
      (`static/.gitkeep` criado como placeholder)
- [ ] Primeiro commit no GitHub + link compartilhado de volta nesta conversa

## Fase 1 — Core mínimo

- [x] `core/module_manager.py` — ciclo de vida de Addon/Plugin com estado em
      banco (`tesseract_module_state`). **Decisão**: Opção B (sem loop de
      múltiplas passadas) — discovery/import de todos os models ativos
      antes de uma única chamada a `db.create_all()`; SQLAlchemy ordena
      por FK automaticamente. Ver `core/module_manager.py` para o
      racional completo.
- [x] `core/event_bus.py` — pub/sub síncrono em memória, com 1 listener de
      exemplo (`register_example_listener`) provando o fluxo ponta a ponta
- [x] `core/template_loader.py` — `ChoiceLoader` mesclando templates de
      módulos ativos com o core (ainda sem nenhum módulo real pra mesclar)
- [x] DB factory (`core/db.py`) + `core/config.py` — **SQLite em dev/test,
      Postgres em produção** (`TESSERACT_ENV`), trocando só a
      `DATABASE_URL`
- [x] `model/core/module_state.py`, `model/core/system_config.py`
- [x] Testes automatizados (`tests/test_phase1_core.py`) — `/health`,
      criação de tabelas de Core, publish/subscribe, listener com erro
      não quebra os demais
- [ ] Algoritmo de múltiplas passadas do BrewStation — **descartado**
      (ver Opção B acima); registrado aqui só para não se perder a decisão
- [ ] Discovery automático de Addon/Plugin a partir de manifesto em disco
      (`addon.json`/`plugin.json`) — ainda não implementado; hoje
      `register_module()` espera um módulo já instanciado. Entra quando
      tivermos o primeiro Addon real (Fase 5) ou antes, se preferir
      adiantar

## Fase 2 — RBAC + Usuários

- [ ] `model/core/user.py`, `role.py`, `permission.py`
      (`tesseract_user`, `tesseract_role`, `tesseract_permission`)
- [ ] `User.has_permission()` — ponto único de decisão de autorização
- [ ] Sync automático de Permission a partir de rota gerada / `@permission`
- [ ] `/api/admin/users` — admin-only, soft-delete (deactivate/activate),
      validação de CPF (portado do PyTeca)
- [ ] Hooks `pbo_*`/`pai_*` (padrão de customização sem editar gerado)
- [ ] Teste: criar usuário, atribuir Role, confirmar 403 sem Permission

## Fase 3 — Versionamento

- [ ] `model/core/code_snapshot.py` (`tesseract_code_snapshot`)
- [ ] `core/versioning/snapshot_if_needed()`, `cleanup_old_snapshots()`
- [ ] Chaves `versioning.*` em `system_config` (skill 03, seção 5)
- [ ] Teste: gerar/escrever um arquivo duas vezes, confirmar 2 snapshots e
      diff entre eles

## Fase 4 — CrudGen + Anotações

- [ ] Portar decorators do PyTeca para `annotations/__init__.py`
      (`@label`, `@plural`, `@listview`, `@form`, `@required`, `@permission`...)
- [ ] `core/crudgen/generate_from_model.py` adaptado para escrever dentro de
      `addons/addon_x/...` (ou `addons/addon_x/features/feature_y/...`) com
      prefixo de tabela tri-nível (skill 02)
- [ ] CLI `tesseract generate --model ... [--addon] [--feature] [--overwrite]`
      (skill 03, seção 4)
- [ ] Teste: gerar um `addon_smoketest` a partir de 1 model simples, validar
      nome de tabela com prefixo correto e os 7 arquivos esperados

## Fase 5 — `addon_brewstation`: primeira Feature real

- [ ] Migrar `feature_yeast_bank` (mais madura e isolada no BrewStation atual)
- [ ] `addon.json` + `feature.json` válidos conforme checklist da skill 03
- [ ] `docs/technical/` e `docs/manual/` preenchidos (skill 04) para esse Addon
- [ ] Teste: ativar o Addon, CRUD funcional via UI

## Fase 6 — Demais Features Brew

- [ ] `feature_mash_control` (revisar/testar pontos already sinalizados como
      pendentes no BrewStation original)
- [ ] `feature_device_manager` (idem)
- [ ] `feature_integ_bfather` — reescrita (não só migração), conforme
      decisão já tomada na conversa de arquitetura
- [ ] Smoke test individual por Feature

## Fase 7 — `addon_builder` (Designer)

- [ ] Catálogo de transações `DS_*`/`NDS_*` (portado de
      `transactions/registry.py` do DEVStationFlask)
- [ ] Motor de regras (`rules/rule_types.py` — validação, visibilidade,
      cálculo, status)
- [ ] Designer drag-and-drop (UI) conectado ao `ModuleManager` do Tesseract
- [ ] Teste: criar 1 tela via designer, confirmar export

## Fase 8 — OData / Screen Generator

- [ ] `odata/connection_manager.py` portado (descoberta de `$metadata`)
- [ ] `screen_generator.py` — telas data-bound a partir de metadados OData
- [ ] Teste: conectar a uma fonte OData pública de teste

---

## Pendências em aberto (não bloqueiam Fase 0, mas precisam de decisão)

- [ ] Limite de 63 caracteres (Postgres `NAMEDATALEN`) ainda não foi
      incorporado à skill 02 — ver conversa de arquitetura
- [ ] Definir se `addon_builder` (Fase 7) e OData (Fase 8) entram antes ou
      depois das Features Brew restantes, dependendo de prioridade de uso real
- [ ] Confirmar com você se haverá Postgres em algum ambiente (hoje os 3
      projetos de origem usam SQLite) — impacta diretamente o item acima
EOF
