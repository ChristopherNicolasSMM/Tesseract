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
- [x] Pasta `static/` populada com os assets do Nice Admin (Bootstrap,
      ApexCharts, Boxicons, Quill, TinyMCE, ECharts + CSS do PyTeca)
- [x] Primeiro commit no GitHub — https://github.com/ChristopherNicolasSMM/Tesseract

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
- [x] Discovery automático de Addon/Plugin a partir de manifesto em
      disco — **implementado na Fase 5**
      (`ModuleManager.discover_and_register_addons`), não nesta fase
      como planejado originalmente; ficou pendente até existir um
      Addon real para testar contra

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
- [ ] **Decisão tomada**: `RegistrationRequest` (auto-cadastro) **entra
      no sistema**, mas será detalhado e implementado pelo Christopher
      diretamente — não faz parte das entregas desta conversa.

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
- [x] **Resolvido na Fase 4**: `core/crudgen/generator.py` chama
      `snapshot_if_needed()` a cada arquivo escrito — toda geração de
      CRUD agora é versionada automaticamente.

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

## Ajuste transversal — `run.py`

- [x] `run.py` na raiz — ponto de entrada único via `python run.py ...`,
      sem depender do executável `flask` instalado globalmente. Usa
      `flask.cli.FlaskGroup` por baixo, então `init-admin` e `generate`
      (já registrados em `core/cli.py`) funcionam automaticamente, sem
      duplicar lógica. Comando `start` adicionado como alias amigável
      para `flask run`. Testado ponta a ponta (`--help`, `init-admin`,
      `start`) sem o executável `flask` no PATH.

## Fase 5 — `addon_brewstation`: primeira Feature real

- [x] `core/feature_base.py` — classe `FeatureBase`, paralela ao
      `AddonBase` mas sem ciclo de ativação próprio (vive com o Addon pai)
- [x] `AddonBase.get_features()` — Addon expõe suas Features ativas
- [x] `ModuleManager.discover_and_register_addons()` — descoberta real a
      partir de `addons/addon_*/addon.json` + `addon.py` (lacuna aberta
      desde a Fase 1, fechada agora)
- [x] `addons/addon_brewstation/addon.json` + `addon.py`
      (`AddonBrewstation`)
- [x] `addons/addon_brewstation/features/feature_yeast_bank/feature.json`
      + `feature.py` (`FeatureYeastBank`)
- [x] `model/yeast_strain.py` — portado de
      `plugin_yeast_bank/model/yeast_bank_models.py` (BrewStation),
      anotado (`@label`, `@plural`, `@required`, `@max_length`,
      `@permission`)
- [x] CRUD gerado via `python run.py generate` — 9 arquivos, tabela
      `tesseract_brewstation_yeastbank_strain`, 8 permissões
- [x] `docs/technical/01-*.md` e `docs/manual/01-*.md` preenchidos no
      Addon e na Feature (skill 04)
- [x] 9 testes (`tests/test_phase5_module_manager.py` +
      `tests/test_phase5_yeast_bank.py`) + 31 das fases anteriores =
      40 passando
- [x] Teste manual ponta a ponta via HTTP real (login → create → list →
      detail → update → trash → restore), confirmando CRUD funcional

### 3 bugs reais encontrados só ao migrar o primeiro Addon de verdade

1. **Prefixo de tabela só se aplicava no `generate` (CLI), não em todo
   boot.** Um `python run.py start` normal reimporta `model/
   yeast_strain.py` com o nome curto (`strain`), sem prefixo — porque
   nada além do CrudGen aplicava `apply_table_prefix()`. Corrigido: o
   `ModuleManager.register_module()` agora aplica o prefixo também,
   de forma idempotente, em todo registro de módulo — esse é o
   comportamento real que a skill 02 sempre pediu ("no momento do
   registro"), a Fase 4 tinha feito um atalho que não sobrevivia a um
   reboot.
2. **Mesmo problema com a sincronização de permissão** — só rodava no
   `generate`, então um banco novo (ex.: o de teste) nunca recebia as
   7+1 permissões de `yeast_strains`. Corrigido: `ModuleManager` agora
   enfileira a sincronização durante o registro e a executa em
   `sync_all_permissions()`, chamado **depois** de
   `create_all_pending_tables()` (a sincronização precisa que
   `tesseract_permission`/`tesseract_role` já existam — ordem importa).
3. **Colisão de nome de tabela entre o smoke-test da Fase 5a e o
   `YeastStrain` real** — o teste de `ModuleManager` usava
   `__tablename__ = "strain"` (mesmo nome curto do model real) no seu
   model fictício; como a metadata do SQLAlchemy é global por processo,
   os dois competiam pela mesma tabela quando a suíte completa rodava
   junto. Corrigido renomeando o model de teste.

### Decisões registradas — escopo desta fatia

- [ ] Migradas apenas `YeastStrain` nesta Fase 5. As 7 tabelas restantes
      de `yeast_bank` (`YeastBankItem`, `YeastStarterLog`,
      `YeastStorageDevice`, `YeastStorageReading`, `YeastBankConfig`,
      `YeastCellCountHistory`, `YeastBankEvent`) ficam para a "Fase 5b"
      — mesma Feature, mais entidades, sem trabalho de arquitetura novo
      (o pipeline já está provado).
- [ ] Templates HTML gerados continuam MVP (Bootstrap puro) — Nice
      Admin real entra quando a tela for de fato usada.
- [ ] Ação de negócio `yeast_strains.recalculate_viability` tem só a
      permissão sincronizada — a lógica de cálculo de viabilidade em si
      (presente no BrewStation original) não foi portada ainda.

## Fase 5b — Resto do `yeast_bank` (concluída)

- [x] 7 entidades restantes portadas: `YeastStorageDevice`,
      `YeastStorageReading`, `YeastBankItem`, `YeastStarterLog`,
      `YeastCellCountHistory`, `YeastBankEvent`, `YeastBankConfig`
- [x] CRUD gerado para todas via `core.crudgen.generator.generate()`
      (chamado diretamente, não pelo `run.py generate` — ver nota abaixo)
- [x] FK entre tabelas da mesma Feature confirmada funcionando,
      inclusive em cadeia (`strain -> bank_item -> starter_log`,
      `device -> reading`) — testado e validado **antes** de migrar
      tudo, não só depois
- [x] Todos os 8 nomes de tabela de `yeast_bank` confirmados dentro do
      limite de 55 caracteres (skill 02) — o maior tem 50
      (`tesseract_brewstation_yeastbank_cell_count_history`)
- [x] `FeatureYeastBank.register_models()`/`register_routes()`
      atualizados para as 8 entidades
- [x] 6 testes novos (`tests/test_phase5b_yeast_bank_full.py`) — tabelas,
      permissões, cadeia de FK via HTTP real, soft-delete em entidade nova
- [x] Teste manual ponta a ponta confirmando a cadeia completa via HTTP
      (strain → device → bank_item com serialização aninhada → starter_log)

### Nota técnica: por que não usei `run.py generate` para as 7 entidades

O comando `generate` da CLI importa o arquivo de model via
`importlib.util.spec_from_file_location` com um nome de módulo
próprio, criando uma classe Python **separada** da que o pacote real
(`addons.addon_brewstation...`) usa — isso colide quando o model já
existe dentro do pacote (duas classes "YeastBankItem" distintas
competindo pela mesma tabela). Usei um script único, descartado depois,
que importa os models pelo caminho real do pacote e chama
`generate()` diretamente. Registrado aqui para não se perder: o
comando `generate` da CLI é o caminho certo para gerar uma entidade
**nova**, mas para portar entidades que **já vivem dentro do pacote**
(como esta migração em lote), chamar `generate()` direto é mais seguro.

## Fase 6 — Demais Features Brew

- [x] `feature_device_manager` — 4 entidades (`DeviceFunction`,
      `DeviceMetadata`, `DeviceActor`, `EmulatedDevice`), descartado
      `model/exemplo.py` (placeholder do BrewStation original)
- [x] `feature_mash_control` — 12 entidades, escopo **CRUD apenas**
      (decisão tomada: motor de controle em tempo real — PID,
      automação contínua, scheduler de processo — fora desta fase,
      precisa de job runner/background que o Tesseract não tem ainda)
- [x] `integ_bfather` — **fora desta fase**, decisão anterior mantida:
      precisa de reescrita, não migração, fica para conversa dedicada
- [x] 12 testes novos (`tests/test_phase6a_device_manager.py` +
      `tests/test_phase6b_mash_control.py`) + 47 das fases anteriores
      = 59 passando
- [x] Teste manual ponta a ponta via HTTP confirmando: cadeia
      function→device→actor→emulated_device (device_manager) e
      cadeia plant→vessel→mapping (FK cross-Feature pra device_manager)
      + recipe→session→step→log/alarm (mash_control)

### Decisão de arquitetura: PK Integer + `external_id` UUID

Conflito real entre o BrewStation original (PK UUID em
`DeviceMetadata`/`DeviceActor`) e a skill 02 (`id` sempre Integer).
Resolvido com os dois: `id` Integer interno (todas as FKs internas
usam ele) + `external_id` String(36) UUID, gerado automaticamente,
para uso externo (broker MQTT, etc.). Documentado na skill 02 como
padrão formal, não só uma decisão pontual.

### 3 bugs/lacunas reais encontrados só ao migrar Features com mais
### entidades e FK entre Features do mesmo Addon

1. **FK cross-Feature quebrava** (`BrewPlantMapping.device_function_id`
   → `DeviceFunction`) porque o `ModuleManager` prefixava Feature por
   Feature — quando chegava em `mash_control`, `device_manager` já
   tinha renomeado `function`, e a string da FK não encontrava mais a
   tabela pelo nome curto. **Corrigido**: `register_module()` agora
   importa TODOS os models de TODAS as Features do Addon primeiro, e
   só depois aplica qualquer prefixo (ver `core/module_manager.py`).
2. **Nome curto de tabela colidindo entre Features-irmãs**:
   `YeastStorageDevice` (yeast_bank) e `DeviceMetadata`
   (device_manager) usavam o mesmo nome curto `device`. Como a
   correção do bug 1 agora importa tudo antes de prefixar, os dois
   competiam pelo mesmo nome na metadata global ao mesmo tempo.
   **Corrigido**: `YeastStorageDevice` renomeado para `storage_device`.
   **Nova regra documentada na skill 02**: nome curto de tabela deve
   ser único em todo o Addon, não só dentro da Feature.
3. **Mesmo padrão se repetiu com `MashRecipe`** colidindo com o
   `_SmoketestRecipe` de um teste da Fase 5a (`tests/
   test_phase5_module_manager.py`) — corrigido renomeando o model de
   teste.

### Bug do BrewStation original corrigido na migração

`EmulatedDevice.functions_config` usava `default={}` (dict mutável
compartilhado entre todas as instâncias sem valor explícito) —
trocado por `default=lambda: {}`.

### Clarificação de skill registrada

Skill 02: FK entre **duas Features do mesmo Addon** é permitida (só
FK entre Addons diferentes é proibida) — não estava explícito antes
desta fase.

## Ajuste transversal — Páginas HTML de Core + reset de senha

Disparado por um "Not Found" real ao acessar a raiz do app implantado
— confirmando que não existia nenhuma rota HTML de Core (só API até
aqui).

- [x] `templates/core/base_no_login.html` / `base.html` / `login.html`
      / `home.html` — usando os assets do Nice Admin já em `static/`
- [x] **Bug real corrigido, afetava TODA tela HTML já gerada pelo
      CrudGen desde a Fase 4**: `render_template()` nos controllers
      gerados usava o caminho completo
      (`addons/.../templates/{plural}/manage.html`), mas
      `{% extends "core/base.html" %}` só resolve se a raiz de busca
      do Jinja for a mesma para os dois — e isso nunca foi verdade,
      porque o `ChoiceLoader` (`core/template_loader.py`, construído
      na Fase 1) nunca foi de fato conectado ao app. Corrigido:
      - `core/crudgen/generator.py` agora usa caminho relativo curto
        (`{plural}/manage.html`) em vez do caminho completo
      - `ModuleManager` descobre automaticamente a pasta `templates/`
        de cada Addon/Feature (via localização do arquivo `.py`,
        sem precisar de metadado extra) e monta o `ChoiceLoader` de
        verdade (`apply_template_loader()`)
      - As 24 entidades já geradas foram regeneradas com
        `--overwrite` para aplicar a correção (hooks preservados)
- [x] `app.root_path` corrigido para Flask encontrar `templates/` na
      raiz do projeto (`template_folder` explícito) — mesma classe de
      bug já vista com `instance_path` (Fase 1) e `app.root_path` no
      `generate` (Fase 4)
- [x] Menu lateral (`sidebar`) e cards da home **dinâmicos**, vindos
      do catálogo de Transações (Fase 7a) — não hardcoded
- [x] `flask reset-password --username admin --password admin123
      [--reactivate]` — caminho de recuperação para o admin "se
      trancar para fora" (senha perdida, ou autodesativação
      acidental — ver Fase 2). `--reactivate` também resolve o caso
      de auto-desativação documentado em
      `test_autodesativacao_invalida_a_propria_sessao`
- [x] **Validado**: todas as "regras iniciais" (`init-admin`,
      `ensure_default_system_config`, `sync_model_permissions`,
      `sync_transaction`, `apply_table_prefix`) já são idempotentes —
      checagem confirmada por código E por teste, não só por
      inspeção. Nenhuma rodou em duplicidade nos testes realizados.
- [x] `core/auth.py`: 401 JSON só para rotas `/api/*`; páginas HTML
      sem login redirecionam para `/login` (antes redirecionava
      sempre como API, mesmo para navegador)
- [x] 66 testes passando (suite completa, incluindo Fase 7a)
- [x] Teste manual via HTTP simulando navegador: `/login` renderiza,
      `/` sem sessão redireciona, `/` com sessão mostra home com
      sidebar, `/brewstation/yeast-strains/` (tela CRUD real) renderiza
      sem erro de template

## Fase 7 — `addon_builder` (Designer)

### Fase 7a — Catálogo de Transações (concluída)

- [x] `model/core/transaction.py` (`tesseract_transaction`) — adaptado
      de `transactions/catalog.py` + `models/transaction.py`
      (DEVStationFlask)
- [x] **Decisão de arquitetura**: sem `min_profile` (tier separado
      USER/DEVELOPER/ADMIN do original) — usa `permission_required`
      resolvido por `User.has_permission()` real. Sem o conceito de
      "Plugin" do DEVStationFlask (descoberta de pasta própria,
      ativação separada) — redundante com o `ModuleManager` que o
      Tesseract já tem.
- [x] `ModuleBase.get_transactions()`/`FeatureBase.get_transactions()`
      — qualquer Addon/Feature/Plugin contribui transações, mesmo
      padrão "código lidera, banco segue" das Permissions
      (`core/transactions_sync.py`)
- [x] `core/transactions_catalog.py` — catálogo de Core (`TX_HOME`,
      `TX_ADMIN_USERS`), seedado no boot; descartadas entradas do
      original que dependem de peças não migradas (`DS_ODATA`,
      `DS_BUILD` — Fase 8+)
- [x] 4 transações reais contribuídas pelas Features já existentes
      (`TX_YEAST_BANK`, `TX_DEVICE_MANAGER`, `TX_MASH_RECIPES`,
      `TX_BREW_SESSIONS`)
- [x] `GET /api/core/transactions/` — lista filtrada por permissão real
- [x] 8 testes (`tests/test_phase7a_transactions.py`) + 59 das fases
      anteriores = 67 passando
- [x] Teste manual via HTTP confirmando filtro real: admin vê 6
      transações, usuário sem nenhuma permissão vê só `TX_HOME`,
      usuário com `yeast_strains.list` vê `TX_YEAST_BANK` mas não
      `TX_DEVICE_MANAGER`

### Fase 7b — Motor de regras (pendente)

- [ ] Validação/visibilidade/cálculo (`rules/rule_types.py` do
      DEVStationFlask) — ainda não iniciado

### Fase 7c — Designer visual drag-and-drop (pendente)

- [ ] Maior peça, precisa de JS/canvas no frontend — ainda não iniciado

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
- [x] **Respondido**: SQLite em dev/test, Postgres obrigatório em
      produção (`TESSERACT_ENV`) — implementado desde a Fase 1
      (`core/config.py`)
EOF
