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

- [x] `model/core/user.py`, `role.py`, `permission.py`, `associations.py`
      (`tesseract_user`, `tesseract_role`, `tesseract_permission`,
      `tesseract_user_roles`, `tesseract_role_permissions`)
- [x] `User.has_permission()` — ponto único de decisão de autorização
- [x] `core/permissions.py` (`permission_required`) — 401 sem login, 403
      sem permissão
- [x] `core/auth.py` — Flask-Login com eager load (joinedload) de
      roles+permissions no `user_loader`
- [x] `@permission` (Camada 2) em `annotations/__init__.py` +
      `core/permissions_sync.py` — sincronização "código lidera, banco
      segue". **Camada 1** (permissão automática por rota gerada) só
      entra na Fase 4, junto com o CrudGen
- [x] `/api/admin/users` — admin-only, soft-delete (deactivate/activate),
      validação de CPF (dígito verificador + rejeita sequência repetida)
- [x] `/api/auth/login`, `/logout`, `/me`
- [x] `core/cli.py` (`flask init-admin`) — resolve o bootstrap do primeiro
      usuário (toda a API é admin-only, então precisa nascer por fora)
- [x] 14 testes automatizados (`tests/test_phase2_rbac.py`)
- [ ] Hooks `pbo_*`/`pai_*` (padrão de customização sem editar gerado) —
      ainda não aplicável: só existem para código *gerado* pelo CrudGen,
      que entra na Fase 4. Registrado aqui para não esquecer de aplicar
      no `users.py` gerado quando o CrudGen existir
- [ ] **Decisão pendente**: `RegistrationRequest` (fluxo de auto-cadastro
      órfão herdado do BrewStation) não foi portado. Hoje só existe
      criação admin-only. Decidir se/quando o auto-cadastro entra.

**Achado de comportamento (não é bug, vale documentar)**: o
`UserMixin.is_authenticated` do Flask-Login é definido como
`return self.is_active`. Se um usuário desativar a própria conta, a
sessão dele desautentica sozinha na requisição seguinte — sem precisar
de logout explícito. Coberto por
`test_autodesativacao_invalida_a_propria_sessao`.

## Fase 3 — Versionamento

- [x] `model/core/code_snapshot.py` (`tesseract_code_snapshot`) — versão
      completa do conteúdo (não diff incremental), `generation_run_id`,
      `parent_snapshot_id` (linha do tempo real), `is_current`
- [x] `core/versioning.py` — `start_generation_run()`,
      `snapshot_if_needed()` (com captura de edição manual perdida via
      `PRE_OVERWRITE`), `cleanup_old_snapshots()`
- [x] `core/config_service.py` + `core/seed_config.py` — seed idempotente
      de `versioning.*`/`rbac.*` em `system_config`, chamado no boot
- [x] 9 testes (`tests/test_phase3_versioning.py`) — seed idempotente,
      criação de snapshot, `on_diff` sem mudança real, agrupamento por
      `generation_run_id`, captura de edição manual perdida, retenção
- [ ] **Decisão registrada**: nenhuma chamada automática a
      `snapshot_if_needed()` existe ainda — a infraestrutura está pronta
      e testada, mas só passa a ser usada de fato quando o CrudGen
      (Fase 4) escrever arquivo via `_write_file()`. Não adiantar a
      integração antes de existir o que versionar.

## Fase 4 — CrudGen + Anotações

- [x] `annotations/__init__.py` completo — portado do PyTeca quase 1:1:
      `@label`, `@plural`, `@listview`/`Column`/`Filter`, `@form`/`Group`,
      `@required`/`@max_length`/`@min_length`/`@min_value`, `@choices`,
      `@display_field`, `get_model_metadata()` (+ `@permission` da Fase 2)
- [x] `core/crudgen/manifest_utils.py` — lê `addon.json`/`feature.json` em
      disco, resolve o prefixo tri-nível completo
- [x] `core/crudgen/table_prefix.py` — aplica o prefixo ao `__table__` do
      model em runtime (dev escreve `__tablename__` curto)
- [x] `core/crudgen/generator.py` + templates Jinja2 — gera
      `service.py`, `controller.py`, `routes.py` + 3 `_hooks.py` (nunca
      sobrescritos) + 3 templates HTML (`manage`/`detail`/`form_modal`)
- [x] `core/permissions_sync.py` estendido — **Camada 1 agora é real**:
      toda entidade gerada ganha as 7 permissões padrão automaticamente
- [x] CLI `flask generate --model <arquivo> --addon <nome> [--feature <nome>] [--overwrite]`
      (skill 03, seção 4) — testado ponta a ponta de verdade (banco real,
      manifesto real em disco, fora da suíte de testes)
- [x] 8 testes (`tests/test_phase4_crudgen.py`) + 23 das fases anteriores
      = 31 passando
- [ ] **Decisão registrada — divergência deliberada do PyTeca**: o
      `service.py` gerado usa soft-delete `is_deleted`/`deleted_at`
      (skill 02), não o workflow de `Status` Enum com
      draft/publish/trash do PyTeca original. Filtros `@choices`/
      `distinct_values()` e autosave de rascunho **não foram portados**
      nesta fase — ficam para quando um caso de uso real (Fase 5/6)
      pedir.
- [ ] **Decisão registrada — onde o prefixo é aplicado**: skill 02 diz
      "no momento do registro" (sugerindo `ModuleManager`); implementei
      no momento da GERAÇÃO (CrudGen), efeito prático equivalente com
      bem menos máquina, já que ainda não existem classes reais de
      Addon/Feature para o `ModuleManager` descobrir (chegam na Fase 5).
      Revisitar se a Fase 5 expuser um caso que isso não cubra.
- [ ] Templates HTML gerados são MVP deliberadamente simples (Bootstrap
      puro, sem o visual completo do Nice Admin) — refinar na Fase 5,
      quando houver de fato uma tela sendo usada.

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
