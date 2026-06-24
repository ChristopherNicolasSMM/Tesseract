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
- [x] **Esclarecido (não é mais um pendente)**: o padrão `pbo_*`/`pai_*`
      em si está implementado e funcionando desde a Fase 4 (todo
      `service.py` gerado tem `_hook("pbo_apply_fields")`/
      `_hook("pai_apply_fields")`, com `*_hooks.py` real, nunca
      sobrescrito). O item original previa "aplicar no `users.py`
      gerado quando o CrudGen existir" — **essa premissa estava errada
      desde a Fase 2**: `User` é Core e nunca passa pelo CrudGen (já
      documentado no próprio cabeçalho de
      `api/routes/core/admin/users.py`), então não existe nem vai
      existir um `users.py` gerado. Se `admin_users.py`/`admin_roles.py`
      (código de Core escrito à mão) precisarem de um ponto de
      customização equivalente no futuro, será um mecanismo próprio,
      não o `pbo_*`/`pai_*` do CrudGen.
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
- [x] **Decisão registrada — divergência deliberada do PyTeca**: o
      `service.py` gerado usa soft-delete `is_deleted`/`deleted_at`
      (skill 02), não o workflow de `Status` Enum com
      draft/publish/trash do PyTeca original. Filtros `@choices`/
      `distinct_values()` e autosave de rascunho **não foram portados**
      — decisão mantida; o que existe hoje de filtro/paginação é o
      smart-list-lite (ver ajuste transversal correspondente), escopo
      ainda menor que o `@choices` completo do PyTeca.
- [x] **Resolvido na Fase 5**: a aplicação do prefixo só na GERAÇÃO
      (CrudGen) não sobrevivia a um reboot normal do app — exatamente o
      caso que este item previa "revisitar". Corrigido movendo a
      aplicação para `ModuleManager.register_module()`, que é onde a
      skill 02 sempre disse que deveria estar. Ver Fase 5, "3 bugs
      reais encontrados".
- [x] **Superado**: o `form_modal.html` mencionado aqui foi **removido**
      na rodada de validação de cliques — estava órfão (nunca incluído
      em nenhum template). O formulário de criação/edição hoje é
      embutido e funcional em `manage.html`/`detail.html`, com filtro e
      paginação (smart-list-lite). Visual completo do Nice Admin (mais
      do que os componentes Bootstrap básicos já usados) continua não
      refinado.

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

- [x] **Concluído na Fase 5b**: migradas apenas `YeastStrain` nesta
      Fase 5 originalmente; as 7 tabelas restantes de `yeast_bank`
      (`YeastBankItem`, `YeastStarterLog`, `YeastStorageDevice`,
      `YeastStorageReading`, `YeastBankConfig`, `YeastCellCountHistory`,
      `YeastBankEvent`) foram migradas na "Fase 5b" (seção abaixo) —
      mesma Feature, mais entidades, sem trabalho de arquitetura novo,
      como previsto.
- [x] **Superado**: templates HTML MVP (Bootstrap puro) foram
      substituídos por formulários funcionais com filtro/paginação
      (smart-list-lite) na rodada de validação de cliques — ver ajuste
      transversal correspondente. Visual completo do Nice Admin
      continua não refinado.
- [x] **Resolvido**: motor de viabilidade portado fielmente de
      `plugin_yeast_bank/api/routes/yeast_bank_routes.py` (BrewStation
      original) — `compute_estimated_viability()` (modelo linear e
      exponencial) e `best_viability_reference_for_item()` (prioridade:
      histórico real > histórico estimado > starter > valor inicial da
      cepa, todos excluindo registros contaminados).

      **Correção de design encontrada ao portar**: a ação original
      opera em **lote sobre `YeastBankItem`** (todos os itens do
      banco), usando os parâmetros de modelo da `YeastStrain`
      relacionada — nunca foi uma ação "por cepa". A permissão
      `recalculate_viability` (Camada 2) estava registrada em
      `YeastStrain` desde a Fase 5 por engano; movida para
      `YeastBankItem`. A permissão antiga
      (`yeast_strains.recalculate_viability`) fica órfã em bancos já
      existentes — sem limpeza automática (mesma lacuna já registrada
      em "Como adicionar/remover" no `docs/technical/06-*`); pode ser
      removida manualmente pela tela de Roles se desejado.

      `services/viability_engine.py` (Feature, não Core — é lógica de
      domínio) + tela `/brewstation/yeast-bank-tools/recalculate-viability`
      (ação em lote com resultado por item, não um CRUD comum) +
      transação navegável `TX_YEAST_BANK_RECALC_VIABILITY`.

      **Achado lateral**: coluna com `default=` no SQLAlchemy aplica o
      valor padrão no INSERT mesmo se `None` for passado explicitamente
      no construtor — só fica `None` de fato após um UPDATE separado.
      Não é bug, é comportamento padrão do SQLAlchemy; só vale ter em
      mente ao testar/depurar campos com default.

      13 testes (`tests/test_viability_engine.py`): cálculo linear e
      exponencial, piso/teto, prioridade de referência, exclusão de
      contaminados, skip de descartados, permissão no lugar certo,
      fluxo completo via HTTP.

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

## Ajuste transversal — Telas de Admin de Usuários

Disparado pela validação de páginas/cliques (item anterior) — a API
de usuários (Fase 2) nunca tinha ganhado tela; `TX_ADMIN_USERS`
apontava literalmente pra URL da API JSON.

- [x] `controller/core/admin_users.py` — reaproveita
      `_validate_payload`/`_apply_payload` da API existente, em vez de
      duplicar a validação
- [x] `templates/core/admin/users_manage.html` /
      `users_detail.html` — criar, editar, atribuir Role, resetar
      senha, ativar/desativar
- [x] **Corrigido**: `TX_ADMIN_USERS.route` apontava para
      `/api/admin/users` (JSON) — agora aponta para `/admin/users`
      (tela). Propagado automaticamente no próximo boot via
      `sync_transaction()` (idempotente, já existia)
- [x] Atribuição de Role pela tela — RBAC não tinha nenhuma UI até
      aqui, só a API
- [x] Reset de senha pelo admin direto na tela (mais rápido que o
      `flask reset-password` quando já está logado)
- [x] **Autodesativação bloqueada na tela** (não na API) — evita o
      admin se trancar fora sem entender por quê
      (`UserMixin.is_authenticated == self.is_active`, Fase 2)
- [x] 9 testes novos (`tests/test_admin_users_pages.py`) + 66 das
      fases anteriores = 75 passando
- [x] Teste manual via HTTP cobrindo os 7 passos: abrir tela → criar →
      editar → atribuir role → resetar senha → login com senha nova →
      desativar outro usuário → autodesativação bloqueada

## Ajuste transversal — Tema, Perfil, Roles/Permissions, Versionamento, Smart-list-lite

Rodada grande, disparada por um pedido consolidado: gestão de
Roles/Permissions, versionamento (igual ao PyTeca), telas ainda
faltantes (perfil + tema claro/escuro), formulário de criação
recolhido por padrão, e filtro/paginação nas listas (smart-list
simplificada, inspirada no componente `smart_list` do PyTeca).

### Tema (claro/escuro) + Perfil

- [x] `User.theme` (`"light"`/`"dark"`, default `"light"`) — adaptado
      do `modo_escuro` (boolean) do PyTeca/BrewStation, como string pra
      deixar espaço a um 3º modo futuro sem nova migration
- [x] `POST /api/auth/update-theme` + toggle no menu do usuário (header)
      e na própria tela de perfil
- [x] `style_dark.css` (já presente nos assets) carregado
      condicionalmente; classe `theme-dark` no `<body>`
- [x] `/perfil/` — editar dados próprios, trocar a própria senha
      (exige senha atual correta), ver Roles atribuídos

### Roles / Permissions

- [x] `/admin/roles/` — criar Role (único ponto onde Role nasce livre,
      diferente de Permission), editar, excluir (bloqueado se algum
      usuário ainda tiver o Role)
- [x] `/admin/roles/<id>` — associação de Permission a Role, agrupadas
      por módulo (prefixo antes do primeiro ponto do nome) num
      accordion, já que passam de 100 com as 24 entidades existentes
- [x] Reforça o princípio "código lidera, banco segue" (skill 00/03):
      Permission nunca é criada pela UI, só lida e associada

### Versionamento (confirmado com o PyTeca — faltava a tela, não o backend)

- [x] **Achado**: o PyTeca tinha um `SnapshotService` completo (list_files,
      get_history, get_content, diff unificado, restore) em
      `services/core/admin/snapshot_service.py` — schema pronto desde
      a Fase 3 daqui, mas **nenhuma API/tela o consumia nem lá nem
      aqui**. Portado quase 1:1 para `core/snapshot_service.py`.
- [x] `/admin/versioning/` — lista de arquivos com histórico, busca por
      caminho
- [x] `/admin/versioning/history` — histórico completo de um arquivo,
      diff unificado entre duas versões selecionadas, restauração
      (grava no disco + cria novo snapshot com `origin=RESTORE`,
      nunca silenciosa)

### Smart-list-lite (CrudGen)

- [x] **"Novo registro" agora recolhido por padrão**, expande só ao
      clicar no botão "+" — aplicado no `manage.html.j2` (afeta as 24
      entidades já geradas, regeneradas com `--overwrite`) e na tela
      de admin de usuários
- [x] Filtro de busca (`?q=`) no campo de resumo + paginação
      server-side (`?page=`) — versão simplificada do `smart_list` do
      PyTeca (escopo: busca + paginação; **fora do escopo**: export
      Excel/CSV/PDF, configuração de colunas com drag-and-drop, layout
      salvo por usuário — registrado como decisão, não esquecimento)
- [x] Contador de registros visível na lista

### Testes e validação

- [x] 17 testes novos
      (`tests/test_theme_profile_roles_versioning.py`) + 75 das fases
      anteriores = 92 passando
- [x] Teste manual via HTTP cobrindo: alternância de tema persistindo
      no `<body>`, edição de perfil, troca de senha com validação de
      senha atual, criação de Role + associação de Permission +
      bloqueio de exclusão com usuário atribuído, diff real
      (`-linha`/`+linha`) e restauração gravando no disco de verdade

### Decisões registradas — fora do escopo desta rodada (resolvidas depois)

- [x] **Resolvido (CSV + Excel; PDF deixado de fora)**: Export das
      listas — botões na tela, respeitam filtro/busca ativos, nunca
      incluem registros na lixeira. `openpyxl` adicionado ao
      `requirements.txt`. PDF não implementado nesta rodada — exportar
      tabela tabular pra PDF tem menos valor prático que CSV/Excel
      (que abrem direto em planilha); revisitar se houver pedido real.
- [x] **Resolvido (mostrar/ocultar; reordenar por drag-and-drop
      deixado de fora)**: Configuração de colunas — checkbox por
      campo, salvo por usuário+lista
      (`tesseract_user_list_preference`, tabela nova, sem migration
      necessária). Lista volta ao padrão (só o campo de resumo) se o
      usuário nunca configurou. Ordem das colunas selecionadas segue a
      ordem de declaração no model — reordenar via drag-and-drop
      precisaria de JS adicional, fica para quando houver pedido real.
- [x] **Resolvido**: Filtros tipados — campos `Boolean` viram `<select>`
      Todos/Sim/Não automaticamente (introspecção de coluna); campos
      anotados com `@choices` (existia desde a Fase 4, nunca tinha sido
      conectado a nada) viram `<select>` com valores distintos do
      banco. Aplicado em `DeviceFunction.category`, `YeastStrain.status`,
      `BrewSession.status`, `BrewSessionAlarm.severity`.

### Bug real encontrado ao validar filtro booleano

`service.py.j2` (`_apply_fields`) fazia `setattr(obj, key, value)`
direto com a string crua do formulário HTML — **qualquer coluna
`Boolean` editada via tela sempre falhava** com
`TypeError: Not a boolean value: 'true'`. Nunca tinha aparecido porque
todo teste anterior usava a API JSON (que já manda o tipo certo), não
um formulário HTML de verdade votando booleano. Corrigido com
`_coerce_value()` — converte string vinda de formulário pra
bool/int/float conforme o tipo real da coluna, antes do `setattr`.
Afeta as 24 entidades (regeneradas).

## Ajuste transversal — Migrations reais (Flask-Migrate/Alembic) + 2 bugs reais corrigidos

Disparado por um erro real em ambiente do Christopher: `no such
column: tesseract_user.theme`. Causa raiz: `db.create_all()` nunca
altera tabela já existente, só cria a que não existe — exatamente a
lacuna já registrada como pendência desde a Fase 1/6.

### Correção estrutural: Flask-Migrate integrado

- [x] `core/db.py` — `migrate = Migrate()`, `migrate.init_app(app, db)`
- [x] `migrations/` — baseline gerada e commitada (schema completo
      atual, stampada como "já aplicada" — `db.create_all()` continua
      criando tabela de Addon novo no primeiro boot; Alembic só entra
      para ALTER de tabela já existente)
- [x] **Testado de ponta a ponta**: adicionei uma coluna de teste,
      `flask db migrate` detectou exatamente
      `"Detected added column 'tesseract_user.teste_coluna_nova'"` (nada
      mais), `flask db upgrade` aplicou de verdade, confirmado lendo o
      schema real do SQLite. Revertido depois do teste.
- [x] **Fluxo daqui pra frente, sempre que adicionar/alterar coluna de
      um model já existente**:
      ```
      python run.py db migrate -m "descrição da mudança"
      python run.py db upgrade
      ```
      Tabela de Addon **novo** (nunca existiu) continua não precisando
      de migration — `db.create_all()` já resolve.

### 2 outros bugs reais encontrados no mesmo diagnóstico

1. **`run.py` tinha `start()` chamada direto no `if __name__ ==
   "__main__"`**, em vez de `cli()` — alguém (possivelmente ajuste
   manual) trocou isso, e o efeito foi **todos os outros comandos
   pararem de existir** (`init-admin`, `generate`, e agora `db`),
   silenciosamente — só `python run.py start` continuava funcionando,
   `python run.py qualquer-outra-coisa` também "funcionava" (Click
   simplesmente ignorava os argumentos e chamava `start` de qualquer
   jeito, sem erro nenhum). **Corrigido.**
2. **Causa provável do bug 1**: `FlaskGroup` define
   `FLASK_RUN_FROM_CLI=true` em **toda** invocação (não só `flask
   run`), o que faz `app.run()` virar no-op silencioso com um aviso em
   vermelho ("Ignoring a call to 'app.run()'..."). Quem bypassou
   `cli()` provavelmente fez isso pra contornar esse aviso, sem saber
   da causa raiz. **Corrigido de verdade**: `start()` remove
   `FLASK_RUN_FROM_CLI` do ambiente antes de chamar `app.run()` — os
   outros comandos continuam funcionando normalmente.
3. **`requirements.txt` estava em UTF-16`** — efeito de `pip freeze >
   requirements.txt` direto no PowerShell (que grava em UTF-16 por
   padrão). `pip install -r` geralmente tolera isso, mas não é
   portável. Reescrito em UTF-8, mantendo as versões fixadas (boa
   prática) e adicionando `Flask-Migrate`/`alembic`/`Mako`, que
   faltavam.

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

- [x] **Resolvido**: limite de 63 caracteres (Postgres `NAMEDATALEN`)
      incorporado à skill 02 (margem de segurança: máx. 55 caracteres),
      checklist da skill 03 atualizado, e **a checagem roda no código**
      (`core/crudgen/table_prefix.py`, `TableNameTooLongError`) — não é
      só regra escrita, rejeita a geração antes de chegar ao banco.
      Testado (`tests/test_phase4_crudgen.py`).
- [x] **Obsoleto** (a pergunta não se aplica mais): a Fase 6 (Features
      Brew restantes — `mash_control`/`device_manager`) já foi concluída
      *antes* da Fase 7 (`addon_builder`) ter avançado, então a ordem já
      ficou definida na prática, não por uma decisão explícita prévia.
- [x] **Respondido**: SQLite em dev/test, Postgres obrigatório em
      produção (`TESSERACT_ENV`) — implementado desde a Fase 1
      (`core/config.py`)
