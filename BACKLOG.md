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

## Ajuste transversal — Feedback de UI/UX real (prints), 3 bugs e 3 entregas

Disparado por prints reais do Christopher comparando tema claro/escuro
e apontando navegação confusa.

### Bugs reais encontrados

1. **Toggle do sidebar nunca funcionava**: `static/js/web.js` (bundle
   do Nice Admin) já tinha o handler do `.toggle-sidebar-btn`
   (`body.classList.toggle('toggle-sidebar')`) e o CSS já tinha as
   regras — mas `base.html` **nunca incluía esse arquivo**. Corrigido.
2. **`web.js` quebrava a si mesmo em qualquer página**: `tinymce.init()`
   era chamado sem nenhuma guarda condicional — como o TinyMCE nunca é
   carregado nas nossas páginas, isso lançava `ReferenceError` e
   interrompia o resto do script, **inclusive a inicialização de
   DataTables**, que vem depois no mesmo arquivo. Corrigido com guarda
   `typeof tinymce !== 'undefined'` (mesmo padrão já usado pros blocos
   de Quill no mesmo arquivo).
3. **Tema escuro nunca aplicava nenhuma regra real**: `style_dark.css`
   usa majoritariamente o seletor `html[data-theme="dark"]` (129
   ocorrências) — `base.html` aplicava a classe `theme-dark` no
   `<body>`, que não bate com **nenhuma** regra do arquivo. O efeito
   visual escuro que aparecia nos prints era na verdade o **dark mode
   forçado do próprio navegador** (Chrome/Android), não o nosso CSS —
   por isso ficava inconsistente (cards brancas, texto cinza
   ilegível). Corrigido: `data-theme` no `<html>` (convenção
   dominante do arquivo real) + `<meta name="color-scheme">` travando
   o navegador a respeitar nossa escolha em vez de "ajudar" por fora.
   `.text-muted` também não tinha nenhuma cobertura no CSS escuro —
   adicionada.

### Entregas

- [x] **Submenus colapsáveis de verdade**: sidebar usava só
  `<li class="nav-heading">` (texto solto, sem interação) — trocado
  pelo padrão nativo `.nav-content`/`data-bs-toggle="collapse"` do
  próprio Nice Admin (já estilizado, nunca usado). Cada grupo
  (Admin/BrewStation/...) agora é um submenu de verdade.
- [x] **`/admin/transactions/`** — "área pra digitar as transações":
  criar transação manual (não vem de nenhum código), editar,
  ativar/desativar. **Decisão registrada**: transação vinda do código
  (`is_standard`/`source_module` de Addon) só permite ativar/desativar
  aqui — `sync_transaction()` sobrescreve label/rota/ícone a cada
  boot, então permitir edição completa daria a falsa impressão de
  persistir.
- [x] **`docs/technical/07-catalogo-de-transacoes.md`** — gerado por
  `python run.py transactions-doc`, a partir do banco real (única
  fonte que inclui também as transações manuais, não só o hardcoded
  no código). 13 transações reais documentadas nesta entrega.
- [x] 16 testes (`tests/test_ui_navigation_fixes.py`) + 159 das fases
      anteriores = 175 passando
- [x] **Resolvido**: causa real do alinhamento do botão "Novo"
      isolada — `users_manage.html` tinha um
      `<h5 class="card-title">Novo usuário</h5>` solto, duplicando o
      texto do botão e empurrando ele pra baixo. Único caso assim em
      todo o projeto (confirmado comparando as outras 5 telas de admin
      e o padrão mestre do CrudGen). Corrigido removendo a linha.

## Ajuste transversal — Smart-list completo nas telas administrativas

Disparado pela mesma rodada de validação: as 24 entidades geradas pelo
CrudGen têm export/filtro/colunas desde a rodada de "smart-list
completo", mas as 6 telas administrativas (Usuários, Roles,
Transações, Regras de Campo, OData, Designer) nunca passaram por essa
atualização — não são geradas pelo CrudGen (models de Core são
escritos à mão de propósito, skill 02), então ficaram de fora.

- [x] `core/admin_list_helpers.py` — `paginate()`,
      `export_csv_response()`, `export_xlsx_response()`. Extrai só a
      parte que de fato repetia entre as 6 telas (paginação e export);
      o filtro de busca continua específico de cada uma (campos
      diferentes pra buscar em cada tela).
- [x] `templates/core/admin/_list_toolbar.html` — parcial reutilizável
      (busca + botões de export + contador + paginação), incluído
      pelas 6 telas via `{% include ... with context %}` em vez de
      repetir o markup 6 vezes à mão.
- [x] **Decisão registrada**: sem "colunas configuráveis por usuário"
      nessas 6 telas — diferente de uma entidade de domínio (que pode
      ter dezenas de campos), cada tela administrativa já mostra um
      número pequeno e fixo de colunas relevantes; configurar isso não
      traria valor real.
- [x] Aplicado em Usuários, Roles, Transações, Regras de Campo,
      Conexões OData e Designer (lista de páginas) — busca textual,
      export CSV/Excel, paginação.
- [x] 19 testes (`tests/test_admin_smart_list_parity.py`) + 185 das
      fases anteriores = 204 passando
- [x] Teste manual via HTTP confirmando as 6 telas: busca filtra de
      verdade, export CSV/Excel contém dados reais e respeita o
      filtro ativo, paginação aparece quando há mais de uma página

## Fase 7a — Catálogo de Transações (concluída)

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

## Fase 7b — Motor de regras (concluída)

- [x] `core/rules_catalog.py` — catálogo completo (17 regras, 3 grupos:
      Validação/Visibilidade/Cálculo) adaptado de `rules/rule_types.py`
      (DEVStationFlask)
- [x] **Decisão de escopo**: só o grupo **Validação** ganhou motor real
      nesta fase. Visibilidade e Cálculo referenciam IDs de componente
      arbitrários (`comp_1`, `comp_2`...) que só fazem sentido dentro
      de um canvas — ficam catalogados, prontos para o Designer (Fase
      7c), mas sem nenhuma engine consumindo eles ainda. Cada regra
      tem `connected: True/False` marcando isso explicitamente.
- [x] `model/core/field_rule.py` (`tesseract_field_rule`) — anexa uma
      regra do catálogo a um campo de qualquer entidade (`entity_key`
      + `field_name`, nunca FK — mesmo princípio de
      `tesseract_user_list_preference`)
- [x] `static/js/rule_engine.js` — motor de validação client-side real
      (required, minLength, maxLength, email, cpf, cnpj, onlyNumbers,
      minValue, maxValue, validDate), incluindo CPF/CNPJ com dígito
      verificador de verdade (não regex solta)
- [x] `/admin/field-rules/` — tela de gestão (criar, ativar/desativar,
      remover), com os 3 grupos do catálogo no select, indicando quais
      têm efeito real
- [x] Conectado ao CrudGen: `manage.html`/`detail.html` (criação e
      edição) renderizam `data-rules` automaticamente nos campos com
      regra ativa, motor JS incluído em toda tela gerada — aplicado
      nas 24 entidades (regeneradas)
- [x] 16 testes (`tests/test_phase7b_rules_engine.py`) + 117 das fases
      anteriores = 133 passando
- [x] Teste manual via HTTP confirmando o `data-rules` real renderizado
      no campo (`[{"js_function": "minLength", "params": {...}}]`)
      depois de anexar a regra pela tela

## Fase 7c — Designer visual drag-and-drop (concluída)

- [x] **Decisão de escopo**: 6 tipos de componente nesta fase
      (`heading`, `label`, `textbox`, `button`, `image`, `divider`) —
      sem `datagrid`/`pagination`/`groupbox` ainda, que dependem de
      binding OData mais elaborado (a Fase 8 ficou read-only de
      propósito). Revisitar quando houver caso de uso real.
- [x] `model/core/designer_page.py` (`tesseract_designer_page`) +
      `model/core/designer_component.py`
      (`tesseract_designer_component`) — portados quase 1:1 de
      `models/page.py`/`models/component.py` (DEVStationFlask), sem
      `project_id` (Tesseract não tem conceito de "Projeto" de
      Designer — uma página é uma tela navegável de Core, como
      qualquer outra)
- [x] `/admin/designer/` — lista de páginas, criar, excluir (cascata
      remove componentes), publicar/despublicar
- [x] `/admin/designer/<id>/edit` — **editor de canvas real**: arrastar
      (mousedown/mousemove/mouseup), redimensionar (alça no canto),
      paleta de componentes, painel de propriedades editável — tudo em
      JS vanilla, sem framework de frontend, persistindo a cada
      solta/edição via `fetch()`
- [x] `/designer/<slug>` — tela de execução (runtime), só acessível se
      `is_published=True`; respeita `permission_required` da página
      (testado: usuário sem a permissão recebe 403)
- [x] **A peça que fecha o ciclo da Fase 7b**: regras de Validação
      anexadas a um `textbox` do Designer (`DesignerComponent.rules`)
      aparecem renderizadas como `data-rules` na tela de execução,
      consumidas pelo mesmo `rule_engine.js` da Fase 7b — sem o
      Designer, esse motor não tinha nenhum componente real (com `id`
      de verdade) pra apontar `source_id`/`target_id`
- [x] 14 testes (`tests/test_phase7c_designer.py`) + 145 das fases
      anteriores = 159 passando
- [x] Teste manual via HTTP cobrindo o fluxo completo: criar página →
      adicionar 3 componentes → mover/redimensionar (simulando o JS) →
      editar propriedades → anexar regra de validação → tentar acessar
      sem publicar (404) → publicar → acessar e confirmar HTML real
      renderizado, com `data-rules` presente → excluir componente
- [ ] **Fora de escopo, registrado para o futuro**: Visibilidade e
      Cálculo (grupos do catálogo da Fase 7b) continuam catalogados
      sem motor — agora TÊM um alvo real (`DesignerComponent.id`), mas
      o `rule_engine.js` só implementa as funções de Validação; as
      funções de Visibilidade/Cálculo (`visibleIf`, `calculate`, etc.)
      ainda não existem no motor JS

## Fase 8 — OData / Screen Generator (escopo recortado — concluído)

- [x] **Decisão de escopo (histórica — na época da Fase 8, o Designer
      ainda não existia)**: `odata/screen_generator.py` (DEVStationFlask)
      gera `Page`/`Component` — pressupunha o modelo de dados do Designer
      (Fase 7c), que não existia ainda quando esta fase foi entregue.
      Construir isso na ocasião teria criado infraestrutura órfã (mesmo
      erro já corrigido com `form_modal.html`). Escopo recortado pra:
      conexão + descoberta de metadata + navegador de dados read-only.
      **Atualização**: o Designer (Fase 7c) já existe agora —
      `screen_generator.py` pode ser revisitado como trabalho futuro,
      gerando `DesignerPage`/`DesignerComponent` data-bound a partir de
      metadata OData.
- [x] `model/core/odata_connection.py` (`tesseract_odata_connection`) —
      adaptado de `models/odata_connection.py`, sem `project_id` (Tesseract
      não tem conceito de "Projeto" de Designer ainda)
- [x] `core/odata/connection_manager.py` — `ODataConnectionManager`
      portado quase 1:1 de `odata/connection_manager.py`. **Achado**:
      não depende de nenhuma lib externa — `S2MOdataPy` mencionado no
      código original é só um FORMATO de JSON reconhecido pelo parser,
      não uma biblioteca a instalar. Só `urllib`/`json`/`xml` da stdlib.
      Cadeia de descoberta de `$metadata` (JSON e XML/EDMX), cache de 5
      minutos, `query()`/`patch()`.
- [x] `/admin/odata/` — gestão de conexões (criar, testar, remover)
- [x] `/admin/odata/<id>/entities` — entidades descobertas
- [x] `/admin/odata/<id>/browse/<entity>` — navegador de dados
      **read-only**, com busca textual (`$filter contains`) e paginação
      (`$top`/`$skip`/`$count`), reaproveitando o visual do smart-list-lite
- [x] **Testado de ponta a ponta com servidor OData real** (mock local via
      `http.server` da stdlib, simulando descoberta de `$metadata.json`
      e consulta de dados) — não só mockado em memória
- [x] 12 testes (`tests/test_phase8_odata.py`) + 133 das fases
      anteriores = 145 passando
- [ ] **Fora de escopo, registrado para quando a Fase 7c existir**:
      `screen_generator.py` (geração de página completa a partir de
      metadata OData, com componentes data-bound)

## Fase 9 — Promoção de `feature_device_manager` a Addon + base para MQTT (em andamento)

- [x] **Fase G — Correção arquitetural encontrada ao formalizar a
      skill 05 (2026-06-29): motor de automação passa a usar o
      EventBus real do Core.** A primeira versão do motor de
      automação (Fase E, bullet abaixo) usava um mecanismo de
      callback paralelo próprio
      (`device_service.on_any_change`/`_on_any_change_callbacks`),
      criado sem verificar se o projeto já tinha uma solução —
      tinha: `core/event_bus.py`, que o próprio módulo documenta como
      "o único canal permitido de comunicação entre Addons
      diferentes" (skill 02). Corrigido:
      `device_service._publish_value_changed_event()` agora publica
      `device_manager.actor.value_changed` via `event_bus.publish()`;
      `automation_engine.register()` usa `event_bus.subscribe()`.
      Removido todo o mecanismo paralelo. **Lição registrada como
      regra de ouro na skill 05** (seção 6): verificar
      `core/event_bus.py` antes de criar qualquer pub/sub novo.
      269/269 mantido (refatoração transparente para os testes —
      nenhum teste chamava o mecanismo antigo diretamente).
- [x] **Sistema de Tasks portado do PyTeca (infraestrutura geral do
      Core, decisão de 2026-06-29 — antes da Fase E do
      device_manager)**: `ScheduledTask`/`TaskLog`/`MessageQueue`
      (`model/core/`), `services/core/task_service.py` (primeiro
      service do Core no Tesseract — controllers antes faziam acesso a
      banco inline), `core/task_registry.py` (ponto de extensão para
      Addons registrarem funções `python_call` — ex.: futuro
      `device_manager.mqtt_reconnect`), monitor em
      `/admin/tasks` (cards, gráfico 7 dias, abas Tarefas/Fila/Logs).
      **Gap do PyTeca corrigido no porte**: a aba Logs do template
      original carregava sempre todos os logs, sem filtro — adicionado
      filtro por task (botão "Ver Logs" por linha) e busca textual
      livre (`?q=`), conforme pedido. **Bônus que vem junto**: conecta
      finalmente o job de `cleanup_old_snapshots()` que
      `core/versioning.py` já esperava desde a Fase 1 ("pensado para
      job futuro, não cria scheduler aqui"). Scheduler real
      (APScheduler) é opt-in via `TASK_SCHEDULER_ENABLED=true`, nunca
      em `TESTING` (mesmo padrão do cliente MQTT). `croniter` opcional
      (sem ele, só intervalo em minutos funciona). Migration
      `9c4f1e8a3b27` (3 tabelas novas). 14 testes novos
      (`tests/test_phase9e_task_system.py`). 199/199 passando.
- [x] **Primeira task real registrada**: `mqtt_client_service.reconnect(app)`
      (stop+start, remonta o LWT do zero) exposta como
      `device_manager.mqtt_reconnect` via `core.task_registry.register_task()`,
      chamado em `AddonDeviceManager.register_routes()` — registro só em
      memória (TASK_REGISTRY), nenhuma `ScheduledTask` é criada
      automaticamente no banco (decisão: o operador cria a instância
      real pela UI do monitor quando quiser, escolhendo esse target —
      evitar decidir agendamento/aprovação sem ser pedido). 2 testes
      novos. 250/250 passando.
- [x] **Documento de arquitetura**: `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`
      — decisões fechadas (sigla `dvm`, API mínima `get_value`/`set_value`/
      `on_change`, MQTT dentro do próprio Addon — Opção A, tabelas
      `Device`/`Sensor`/`Actuator` novas, MQTT-only na v1, logging em 3
      camadas, fail-safe via LWT), modelagem detalhada e fluxos Mermaid.
- [x] **Bloqueador real encontrado e resolvido**: `feature_mash_control`
      tinha 4 FKs diretas para `DeviceFunction` (`automation_rule.py` x2,
      `dashboard_widget.py`, `brew_plant_mapping.py`) — legítimas como FK
      cross-Feature mesmo Addon (skill 02), mas viram FK cross-Addon
      proibida ao promover. Removidas e substituídas por referência
      fraca (`*_function_name`, chave de negócio única de
      `DeviceFunction`) + service público novo
      `addons/addon_device_manager/root/services/device_function_lookup.py`
      (não gerado pelo CrudGen, ponto de extensão estável).
- [x] Promoção estrutural completa: `addons/addon_brewstation/features/feature_device_manager/`
      → `addons/addon_device_manager/` (estrutura `root/`, skill 01),
      `addon.json` próprio (`table_prefix: "dvm"`), classe
      `AddonDeviceManager`. `feature_mash_control/feature.json` agora
      declara `"requires": ["device_manager"]`.
- [x] Rotas renomeadas: `/brewstation/device-*` e `/api/brewstation/device-*`
      → `/device-manager/device-*` e `/api/device-manager/device-*`
      (decisão explícita — skill 00, rota segue o módulo dono).
- [x] **Bug real de Core encontrado e corrigido** (não previsto, bloqueava
      qualquer Addon top-level com `root/templates/` próprio):
      `ModuleManager._template_dir_for()` não checava o layout
      `root/templates/` (só `templates/` direto, padrão de Feature); e
      `discover_and_register_addons()` nunca registrava o módulo
      dinamicamente importado em `sys.modules`, então `mod.__file__`
      nunca resolvia para a instância do Addon. As duas causas
      corrigidas em `core/module_manager.py`.
- [x] Migration Alembic (`migrations/versions/4a8524f00549_*.py`): rename
      das 4 tabelas (`tesseract_brewstation_dvm_*` → `tesseract_dvm_*`)
      + backfill das 3 colunas de referência fraca + `downgrade()`
      simétrico.
- [x] Suíte de testes atualizada e validada: 175/175 passando
      (`test_phase6a_device_manager.py`, `test_phase6b_mash_control.py`,
      `test_smart_list_completo.py` ajustados para o novo esquema/rotas).
- [x] **Fase B do plano (modelagem fina) — revisada e concluída**:
      decisão final foi **estender `DeviceActor`** (2 colunas novas:
      `failsafe_value` String(50) nullable, `is_risk` Boolean default
      `false`) em vez de criar tabelas `Device`/`Sensor`/`Actuator`
      novas — `DeviceMetadata`/`DeviceActor`/`DeviceFunction` (Fase 6)
      já cobriam o problema de forma mais madura que o desenho inicial 
      do documento de arquitetura (`actor_type` por porta já resolve
      "device com múltiplas portas mistas"). `mqtt_config`/
      `hardware_mapping` ficam dentro do `config_json` que `DeviceActor`
      já tinha — sem coluna nova. Migration `7b3e9c1a2d4f`. Documento de
      arquitetura (`docs/skills/05-*.md`, seção 4) reescrito refletindo
      a decisão; desenho original preservado como histórico em
      `<details>`. 176/176 testes passando (1 teste novo cobrindo os
      campos).
- [x] **Fase A do plano de execução — concluída.** Adendo à skill 01:
      seção `logs/` adicionada à estrutura padrão de Addon. Adendo à
      skill 03: seção `logging` (e subcampos) adicionada ao schema de
      `addon.json`, mais item no checklist de validação. **Divergência
      real encontrada e corrigida**: `docs/skills/01-*.md` dizia `core/`
      em vez de `root/` para a subpasta interna de um Addon — desde o
      primeiro commit do projeto, não uma regressão desta sessão.
      Confirmado com Christopher que `root/` é o correto (já em uso
      desde a Fase 9); skill corrigida.
- [x] **Fase D do plano (parcial) — `device_service.py` +
      `mqtt_client_service.py` implementados.**
      `device_service.py`: API pública `get_value`/`set_value`/
      `on_change`, cache em `DeviceActor.config_json["runtime"]`,
      resolução por `external_id` ou `name`. `mqtt_client_service.py`:
      cliente `paho-mqtt` (v2 callback API), `start()`/`stop()`
      idempotentes, início opt-in via `MQTT_ENABLED=true` no
      `app_factory.py` (nunca em `TESTING`).
      **Correção de protocolo encontrada e aplicada**: MQTT só permite
      um LWT (Last Will and Testament) por conexão de cliente — o
      desenho original do documento de arquitetura ("LWT por atuador")
      estava tecnicamente incorreto. Corrigido para LWT único agregado
      (`build_lwt_payload()`), publicado no `status_topic`, com payload
      JSON listando todos os `DeviceActor` com `is_risk=true`; quem
      aplica o fail-safe de fato é o lado hardware
      (`tesseract-device-bridge`) assinando esse tópico, não o broker
      republicando N comandos sozinho. Diagramas da seção 5
      (`docs/skills/05-*.md`) corrigidos. **Spec do bridge (conversa
      separada) precisa ser atualizada com essa correção antes da
      Fase F.**
      9 testes novos (`tests/test_phase9d_device_service_mqtt.py`),
      sem depender de broker real. 185/185 passando.
- [x] **Fase D — itens restantes fechados (2026-06-29).**
      `addon.json` real ganhou a seção `logging` (`addons/addon_device_manager/addon.json`)
      e `env_keys` do MQTT (faltavam, apesar do `mqtt_client_service.py`
      já existir). `integration_logger.py` (novo): `RotatingFileHandler`
      escopado a um logger nomeado (`addon_device_manager.integration`,
      `propagate=False`) — não conflita com a regra do
      `core/logging_config.py` ("nenhum módulo cria seu próprio
      `basicConfig()`") porque não toca no root logger, só adiciona um
      handler a um logger específico. Eventos de rotina
      (`set_value`/`update_from_mqtt`) vão só pro arquivo local;
      **validação de faixa** (`DeviceFunction.min_value`/`max_value`)
      implementada em `device_service._validate_range()` — `set_value`
      **rejeita** valor fora de faixa (comando inseguro nunca é
      aplicado); `update_from_mqtt` **aceita mas loga erro global**
      (leitura de sensor é dado observado, não comando — esconder uma
      leitura anômala seria pior que registrá-la). 9 testes novos
      (`tests/test_phase9g_validacao_faixa_e_log.py`). 269/269 passando.
      **Fase D agora 100% concluída.**
- [x] **Fase E — Opção 1 (motor de automação reativo) concluída.**
      `AutomationRule` agora avalia de fato: a cada
      `device_service.update_from_mqtt`/`set_value`, dispara
      `on_any_change` global → `automation_engine._on_device_value_changed`
      (`feature_mash_control/services/automation_engine.py`) → busca
      regras por `sensor_function_name` → avalia `condition_operator`/
      `condition_value` (respeitando `cooldown_seconds`) → se
      verdadeiro, resolve o ator via novo
      `device_service.find_actor_external_id_by_function_name()` e
      chama `set_value()` → grava `AutomationRuleLog`. Suporta as 4
      ações (`ON`/`OFF`/`SET_VALUE`/`TOGGLE`). Sem polling/scheduler —
      100% reativo ao que já chega via MQTT.
      **Correção de fronteira durante a implementação**: a primeira
      versão passava o objeto `DeviceActor` inteiro pro callback do
      `mash_control`, que navegava `actor.function.name` — violava a
      própria regra que o módulo documentava (nunca ORM de outro
      Addon, nem de leitura). Corrigido: `device_service` agora
      resolve o `function_name` internamente e entrega só a string ao
      callback (`on_any_change(function_name, value)`).
      10 testes novos (`tests/test_phase9f_automation_engine.py`),
      cobrindo as 4 ações, cooldown, regra inativa, valor não-numérico,
      function de ator inexistente (log de falha) e múltiplas regras
      no mesmo sensor. 260/260 passando.
- [x] **Fase G concluída (2026-06-29).** `docs/technical/01–06` e
      `docs/manual/01–04` do `addon_device_manager` reescritos por
      completo (estavam herdados de quando era Feature — nomes de
      tabela errados, "FK cross-Feature" onde hoje é referência
      fraca, coluna fictícia `current_temperature_c` que nunca
      existiu no model real, nada de MQTT/automação/tasks). Criados
      `02-diagrama-c4.md` e `03-fluxos.md` (faltavam por completo) e
      `i18n/pt_BR.json` (primeiro arquivo de tradução do projeto,
      skill 00). Skill 05 formalizada — deixou de ser "proposta em
      discussão", passa a ter o mesmo peso normativo das skills 00–04.
- [ ] **Pendente — Fase F**: validação ponta a ponta com bridge MQTT
      real (spec separada: `tesseract-device-bridge`, repositório
      próprio — atualizar com a correção do LWT agregado antes de
      iniciar).


---

## Ajuste transversal — Submenu agrupado por Feature + 20 páginas órfãs

Disparado pela análise de navegação: 20 telas de CRUD completo e
funcional (geradas pelo CrudGen, com export/filtro/paginação) não
tinham **nenhuma** entrada no catálogo de Transações — só acessíveis
digitando a URL direto. Causa: cada Feature só contribuía 1-2
transações "representante", nunca uma por entidade.

- [x] `feature_yeast_bank.get_transactions()` — completo, 9 entradas
      (era 2), grupo trocado de `"BrewStation"` genérico para
      `"Banco de Levedura"`
- [x] `feature_mash_control.get_transactions()` — completo, 12
      entradas (era 2), grupo `"Controle de Mostura"`
- [x] `addon_device_manager.get_transactions()` — completo, 4 entradas
      (era 1), grupo `"Dispositivos IoT"` (era `"Device Manager"`)
- [x] **Resultado**: cada Feature/Addon agora é o próprio submenu
      colapsável (mecanismo já existia desde a correção do toggle —
      só faltava o `group` ser granular o suficiente). Não foi preciso
      mudar schema nem JS.
- [x] **Achado lateral corrigido**: `TX_HOME` (grupo `"Core"`, rota
      `/`) duplicava o link "Início", que já existe fixo, fora do loop
      de grupos, em `base.html`. Grupo `"Core"` agora é pulado no loop
      da sidebar e dos cards da home — `TX_HOME` continua existindo só
      pra aparecer em `/admin/transactions/`.
- [x] 30 testes (`tests/test_menu_grouped_by_feature.py`) + 204 das
      fases anteriores = 234 passando
- [x] Teste manual via HTTP confirmando: as 20 rotas órfãs aparecem na
      home e na sidebar, os 3 grupos novos aparecem como seção, nenhum
      "Início" duplicado

## Skill 09 — Auto-Descoberta de Módulos (pkgutil)

- [x] `core/module_discovery.py`, `register_models()`/`register_routes()`/
      `get_transactions()` deixam de ser `@abstractmethod` em
      `ModuleBase`/`AddonBase`/`FeatureBase`, ganham default via
      auto-descoberta escopada por módulo. `@menu_icon` nova em
      `annotations/`. 5 testes novos (`tests/test_module_discovery.py`).
      312/312 passando, zero regressão confirmada nos 3 módulos reais
      (todos sobrescrevem os 3 métodos manualmente, continuam intocados).

- [ ] **Pendente, opcional — migração dos módulos reais para o caminho
      automático** (`addon_brewstation` núcleo, `feature_yeast_bank`,
      `feature_mash_control`, `addon_device_manager`): removeria o
      boilerplate manual de `register_models`/`register_routes`/
      `get_transactions` nesses 4 arquivos.
      **Achado ao investigar**: não é troca neutra — o `group` usado
      hoje no `get_transactions()` manual é curado em PT-BR
      (`"Banco de Levedura"`, `"Controle de Mostura"`,
      `"Dispositivos IoT"`), enquanto o `label` do manifesto de cada um
      está em inglês (`"Yeast Bank"`, `"Mash Control"`,
      `"Device Manager"`) — a auto-descoberta usa `module.label` como
      `group`, então migrar hoje trocaria o menu pro nome em inglês,
      violando a skill 00 (labels visíveis sempre PT-BR). Duas saídas
      possíveis, nenhuma decidida ainda:
      1. Traduzir o `label` desses manifestos para PT-BR antes de
         migrar (checar antes se `label` é usado em algum outro lugar
         da UI de admin, pra não quebrar nada ali).
      2. Estender a skill 09 com anotação `@menu_group("...")` por
         model, pra sobrepor o `group` default sem depender do
         `label` do manifesto.
      Bloqueado até essa decisão ser tomada — não iniciar a migração
      sem resolver isso primeiro.



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

## Documentação — manuais de manutenção/expansão (concluída)

- [x] `docs/technical/06-manutencao-e-expansao.md` (sistema): seção
      "Como adicionar um campo a um model existente" expandida em
      checklist completo (model, regenerar via CrudGen quando
      necessário, migration, `to_dict()`, ripple effect em testes,
      services que constroem a entidade manualmente, docs) + nota de
      quando NÃO é preciso regenerar (controllers genéricos por
      introspecção de `__table__`, caso da maioria dos CRUDs deste
      projeto).
- [x] `docs/technical/06-manutencao-e-expansao.md` (sistema): seção
      nova "Como criar uma nova entidade (do zero) via CrudGen" —
      passo a passo completo (model anotado → `generate` →
      registrar em `register_models()`/`register_routes()` →
      transação de menu opcional → testes → docs), usando a criação
      real de `Fabricante`/`Origem`/`TipoProduto`/`Categoria`
      (`addon_estoque`, sessão anterior) como exemplo concreto.
- [x] `addons/addon_estoque/docs/technical/06-manutencao-e-expansao.md`
      criado (não existia) — aponta pro doc de sistema acima e
      registra os itens de expansão futura abaixo.

## `addon_estoque` — expansão cadastral futura (planejado, não iniciado)

Registrado nesta sessão a pedido do Christopher — **documentação
apenas, nenhum model/schema decidido ainda**. Retomar seguindo o
mesmo processo desta sessão (decisão estruturada antes de qualquer
código — ver `addons/addon_estoque/docs/technical/06-manutencao-e-expansao.md`).

- [ ] Mais campos em `Fabricante` (hoje só `nome`) — quais campos,
      não decidido.
- [ ] Cadastro de Fornecedores — em aberto se é entidade dentro de
      `addon_estoque` ou Addon novo (`addon_compras`).
- [ ] Sistema de Compras — escopo não definido (pedido, cotação,
      recebimento, vínculo com `Movimentacao`). Provável candidato a
      Addon novo, não decidido.

## Skill 10 — revisão (menu hierárquico): EXECUTADA (2026-07-07)

Retomada do item de backlog "`Transaction.parent_manually_set`" de
sessão anterior — investigação no código real levou a resultado
diferente do esperado, e os 3 achados novos foram implementados na
sequência (mesma sessão, autorização explícita — ordem "5,4,2,1,3",
item 4). Ver `docs/skills/10-menu-hierarquico.md`, seção 9, para o
detalhe completo de cada item abaixo.

- [x] **Achado**: `parent_manually_set` está **obsoleto** — o problema
      que motivou a proposta já não existe na implementação real
      (`admin_transactions.py` bloqueia por completo edição de
      estrutura em transação code-sourced, não precisa de flag pra
      "pular no sync"). Não implementado (decisão de não fazer).
- [x] **[EXECUTADO]** Bug real do accordion corrigido: `data-bs-parent`
      fixo em `#sidebar-nav` em toda profundidade da árvore do menu
      (`templates/core/base.html`, macro `render_menu_nodes`) — abrir
      um nó em qualquer nível fechava nós abertos em qualquer outro
      lugar da árvore. Fix: macro ganhou parâmetro
      `parent_container_id`, passado como `'node-' ~ tx.code` na
      recursão.
- [x] **[EXECUTADO]** Catálogos manuais de Feature de `addon_brewstation`
      estavam flat (`parent_code: None` nas 5 Features, sem grupo
      Addon-pai) — `TX_GROUP_BREWSTATION` novo em
      `AddonBrewstation.get_transactions()`, 5 Features apontando pra
      ele. Escopo só `addon_brewstation` (único Addon com mais de uma
      Feature hoje).
- [x] **[EXECUTADO]** `core.menu.icon_max_depth` (`system_config`, int,
      default `-1` = sem corte) — a partir do nível N, item renderiza
      sem ícone (só texto). Lido via `SystemConfig.get()` direto no
      `context_processor`, sem seed row obrigatória.

**Conflito real encontrado e resolvido**: `tests/test_menu_grouped_by_feature.py`
tinha um teste (`test_nao_existe_mais_grupo_brewstation_generico`)
afirmando o oposto do item de `TX_GROUP_BREWSTATION` acima — de uma
fase anterior à árvore `parent_id`, quando "BrewStation" genérico
duplicava transações por Feature (sem hierarquia real disponível pra
ter as duas coisas). Com `parent_id`, o dilema não existe mais — teste
atualizado pra afirmar a invariante nova (existe exatamente uma pasta
"BrewStation", e é a raiz).

Validado: suíte completa (37 arquivos, 453 testes) passando, incluindo
4 testes novos em `test_menu_hierarquico.py` cobrindo os 3 itens.

## Item (d) — `material_id` não resolvido na exibição — REVISADO (ver skill 11)

**Superado pela investigação de continuidade abaixo** — o desenho
original desta seção (hook `resolve_display_value` manual por
entidade, 6 arquivos-conjunto editados à mão, sem tocar o gerador) foi
**substituído** depois de investigar o `ChristopherNicolasSMM/PyTeca`
real e achar que o Tesseract já tem metade do mecanismo portado
(`@display_field`) e nunca usado. Decisão nova, mais próxima do
padrão PyTeca e generalizada via CrudGen: ver
`docs/skills/11-referencia-fraca-e-display-field.md` (skill nova,
mesmo peso normativo das demais).

Resumo da mudança de rumo (detalhe completo na skill 11):
- Em vez de hook manual por entidade, duas anotações novas resolvem
  isso de forma genérica e automática via gerador: `@display_field`
  (já existia, nunca usada) no model **alvo** (`Material`), e
  `@weak_ref` (nova) no model **que tem** a referência fraca
  (`Malte.material_id`, etc.), apontando pra função de resolução
  (`material_lookup.get_material`).
- `core/crudgen/generator.py` passa a gerar a resolução
  automaticamente pra qualquer entidade com `@weak_ref` — não é mais
  trabalho manual repetido nas 6 entidades, e entidades futuras já
  nascem cobertas.
- Escopo ampliado nesta revisão: também portar `/api/options/<table>`
  (combo de busca assíncrono, formato Select2) — troca o `<input>`
  de texto puro por um campo de busca com nome, mantendo o id
  persistido no submit. Dependência em aberto: **Select2 não está
  nos assets estáticos do projeto hoje** (`static/`, herdados do Nice
  Admin) — precisa vendorizar ou usar alternativa mais leve, decisão
  ainda não tomada (ver skill 11, seção 4).
- Ainda pendente de implementação — esta rodada continua sendo só
  decisão/documentação.

## Skill 11 — EXECUTADA (2026-07-07)

Implementação autorizada e concluída — sem desvio do desenho
documentado. Detalhe completo em
`docs/skills/11-referencia-fraca-e-display-field.md`.

- [x] `@display_field`/`@weak_ref` em `annotations/__init__.py`
      (`get_weak_refs()` novo, mesma convenção de `get_choices_fields()`).
- [x] `Material` ganha `@display_field("nome")`; `material_lookup.get_material()`
      enriquecido com a chave `"display"`.
- [x] `@weak_ref("material_id", resolver=..., options="materials")`
      aplicado nas 6 entidades identificadas (`Malte`, `Lupulo`,
      `Levedura`, `ItemEnvase`, `RecipeIngredient`, `IngredientMapping`).
- [x] `core/crudgen/generator.py` (templates `controller.py.j2`,
      `manage.html.j2`, `detail.html.j2`) gera a resolução
      automaticamente pra qualquer entidade com `@weak_ref` — não é
      mais trabalho manual repetido.
- [x] `/api/options/<plural>` implementado (`api/routes/core/options_routes.py`)
      — decisão de implementação: **vanilla JS** (`static/js/weak_ref_combo.js`),
      não Select2 — resolve a pendência em aberto da skill 11 §6 (o
      projeto não tinha Select2/jQuery nos assets; vendorizar uma lib
      nova só pra isto não se justificava). Endpoint já devolve o
      formato de resposta nativo do Select2 — se o projeto adotar a
      lib por outro motivo no futuro, só trocar o JS consumidor.
- [x] 11 testes novos (`tests/test_weak_ref_display_field.py`) — 434 + 11
      novos + 2 do item Material (sessão anterior) passando, nenhuma
      regressão nos 37 arquivos de teste.

**[CORRIGIDO em 2026-07-07, sessão seguinte]** Bug real encontrado na
execução da skill 11, não relacionado à decisão em si: `python run.py
generate --model ... --overwrite` falhava com `NoForeignKeysError` ao
regenerar uma entidade que tem `relationship()` real pra outra tabela
do mesmo Addon/Feature já prefixada (`ItemEnvase.envase`,
`RecipeIngredient.recipe`) — o CLI recarregava o arquivo do model
isoladamente via `importlib.util.spec_from_file_location`
(`core/cli.py`, `generate_cmd`), fora do processo normal de boot que
aplica o prefixo de tabela; a `ForeignKey("envase.id")` declarada no
código-fonte (nome curto, sem prefixo) não encontrava mais nenhuma
tabela chamada literalmente `envase` na metadata nesse ponto, porque o
boot da mesma sessão CLI já tinha renomeado a tabela real pra
`tesseract_brewstation_envase` antes de chegar ali.

**Correção**: `generate_cmd` passa a reimportar o model pelo caminho
de pacote real (dotted path, `importlib.import_module`) em vez de
recarregar o arquivo isolado — reaproveita a MESMA classe já mapeada
corretamente pelo boot normal (`register_models()`), evitando a
duplicação de definição de tabela por completo. Fallback pro
carregamento isolado antigo mantido só para o caso raro de o arquivo
ainda não ser membro de um pacote importável (pasta sem `__init__.py`).
Validado regenerando `ItemEnvase`/`RecipeIngredient` de verdade — zero
diff em relação ao patch manual aplicado na sessão anterior (prova de
que a correção produz exatamente o mesmo resultado que o gerador
deveria ter produzido desde o início). 3 testes de regressão novos em
`tests/test_crudgen_cli_generate_relationship_bug.py`, exercitando o
comando real via `app.test_cli_runner()` (a lacuna de cobertura que
permitiu esse bug passar despercebido — `test_phase4_crudgen.py`
testa só a função `generate()` direto, nunca o carregamento via CLI).

## Item (c) — Receita: adjuntos + água (`WaterProfile`) — EXECUTADO

Escopo já vinha "CONFIRMADO como amplo" de sessão anterior a esta;
esta rodada verificou os detalhes contra a **API real do BrewFather**
(busca externa, não assumido de memória) e fechou 2 decisões que
faltavam. Nada implementado ainda — só decisão/schema.

**Confirmado sem conflito contra a API real**:
- `miscs[].type` tem exatamente os valores já assumidos: `Water
  Agent`, `Fining`, `Spice`, `Herb`, `Flavor`, `Other`. Mapeamento:
  `Water Agent` → `tipo_ingrediente="agua_agente"`; os outros 5 →
  `"adjunto"`.
- Objeto `water` da API tem exatamente os campos já assumidos:
  `calcium`, `magnesium`, `sodium`, `chloride`, `sulfate`,
  `bicarbonate` (todos em ppm), `ph` (0–14). Bate 1:1 com o schema já
  decidido pra `WaterProfile` (calcio/magnesio/sodio/cloreto/sulfato/
  bicarbonato/ph).
- `RecipeIngredient.tipo_ingrediente` já aceita qualquer string livre
  (sem enum/constraint — `@choices` é só filtro de UI) — os dois
  valores novos não exigem migração de schema, só popular dado novo.

**Achado nesta rodada, não coberto pela decisão original**: `miscs[].use`
(equivalente ao `etapa`/timing) tem 7 valores reais confirmados —
`Mash, Sparge, Boil, Flameout, Primary, Secondary, Bottling`.
`RecipeIngredient.etapa` só cobre 3 (`mostura`/`fervura`/`fermentacao`)
e o `_USE_PARA_ETAPA` existente (`sync_service.py`) não tinha entrada
pra `sparge` nem `bottling`.

**Decidido**:
- `sparge` → conta como `"mostura"` (mesmo estágio de lauter, sem
  etapa nova).
- `bottling` → **não mapeado por agora** — cai no fallback já
  existente do código (`_USE_PARA_ETAPA.get(..., valor_bruto)`), vira
  `etapa="Bottling"` (string bruta do BrewFather, não traduzida) em
  vez de forçar em uma das 3 etapas existentes. Preservado pra
  granularidade futura, sem criar etapa nova agora (opção "criar
  etapa envase" foi considerada e descartada nesta rodada).
- Precisa também de entradas novas em `_USE_PARA_ETAPA` pra `primary`/
  `secondary` → `"fermentacao"` (miscs usam esses valores; o dict
  hoje só tem a chave `"fermentation"`, que vem de outro contexto).

**Schema `WaterProfile` (fechado, sem mudança em relação à sessão
anterior)**: tabela nova em `feature_mash_control` — `recipe_id` FK
(mesmo Addon, skill 02), `contexto` (`source`/`target`/`mash`/
`sparge`/`total`), `calcio`/`magnesio`/`sodio`/`cloreto`/`sulfato`/
`bicarbonato` (float, ppm), `ph` (float), `UniqueConstraint(recipe_id,
contexto)`. Segue o mesmo padrão de `MashStep`/`FermentationStep`
(FK real pra `MashRecipe`, mesmo Addon).

**Pendente de verificação em tempo de implementação** (não bloqueia a
decisão, mas fica registrado): a estrutura exata de aninhamento do
objeto `water` dentro do JSON de receita (`recipe.water.source` vs.
`recipe.water.mash` vs. um único objeto plano) não foi confirmada
byte a byte contra uma resposta real da API — os nomes de campo de
íon foram confirmados via documentação, a estrutura de contexto
(source/target/mash/sparge/total) é inferida da documentação do Water
Calculator (que discute os 5 conceitos separadamente) e deve ser
validada contra uma resposta real na hora de escrever o parser.

**[EXECUTADO em 2026-07-07, sessão seguinte]** — implementado como
decidido:
- `WaterProfile` novo (`feature_mash_control`, CrudGen real —
  tabela `tesseract_brewstation_mashctrl_water_profile`, 43 chars,
  dentro do limite de 55 da skill 02), registrado em
  `register_models()`/`register_routes()` + transação de menu
  `TX_WATER_PROFILES`.
- `brewfather_client.py`: `_normalizar_ingredientes` ganha o loop de
  `miscs[]` (`Water Agent` → `agua_agente`, os outros 5 tipos →
  `adjunto`; `use` mapeado via `_MISC_USE_PARA_ETAPA` com as decisões
  fechadas — sparge→mostura, primary/secondary→fermentacao, bottling
  sem mapear). `_normalizar_water_profiles` novo — **parser defensivo**
  por causa da pendência registrada (estrutura de aninhamento não
  confirmada byte a byte): aceita tanto `water` aninhado por contexto
  quanto objeto plano (tratado como contexto `total`); contexto sem
  nenhum valor é ignorado.
- `sync_service.py`: `_USE_PARA_ETAPA` ganha sparge/primary/secondary;
  `_importar_receita` grava `WaterProfile` direto (sem de-para, mesmo
  padrão de `MashStep`/`FermentationStep`).
- `ingredient_autocreate_service.py`: prefixos de SKU novos
  (`ADJUNTO-`/`AGUA-`) e categoria pros 2 tipos novos.
- **Nota sobre a variante do bug do CLI**: gerar um model NOVO com
  `relationship()` real exige registrá-lo em `register_models()`
  **antes** de rodar `python run.py generate` — a correção anterior do
  CLI (dotted path) cobre regenerar model já registrado; pra model
  novo, o registro prévio é o que faz o boot importar a classe na
  ordem certa (FK resolvida antes do prefixo). Sequência correta:
  model → registrar em feature.py → generate.
- 6 testes novos (mock atualizado com miscs + water_profiles; parser
  real do client testado contra formato bruto da API incluindo os 6
  tipos e 7 uses; unique(recipe_id, contexto); SKU com prefixos
  novos). 2 testes de contagem existentes atualizados (3→5
  ingredientes no mock; 17→18 transações no grupo Mash Control).
- Suíte completa (38 arquivos) passando, zero regressão real.

## Item (b) — Tela de Logs (admin): filtro por hora + cor por nível — EXECUTADO

Investigação em `core/log_admin_service.py` / `controller/core/admin_logs.py`
/ `templates/core/admin/logs_detail.html`: hoje é dump de texto cru
num `<pre>`, sem parsing, sem filtro, sem cor nenhuma.

**Achados que viabilizam o pedido sem mudança de schema**:
- Formato de linha do arquivo já é parseável — `core/logging_config.py`
  grava `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`,
  timestamp completo (`YYYY-MM-DD HH:MM:SS`). Regex simples extrai
  data/hora/nível/logger/mensagem.
- **Ressalva real**: tracebacks multi-linha (exceção não tratada, ver
  `core/request_error_logging.py`) não seguem esse formato nas linhas
  de continuação — o parser precisa tratar linha sem timestamp como
  continuação da mensagem da linha anterior, não como registro novo
  sem nível.
- Mapeamento de cor já existe semanticamente em `_LEVEL_COLORS`
  (`core/logging_config.py`, hoje só ANSI pra terminal) e bate 1:1 com
  as CSS vars que o tema já define (light e dark):
  `DEBUG→--color-info`, `INFO→--color-success`,
  `WARNING→--color-warning`, `ERROR`/`CRITICAL→--color-danger`.

**Decidido**:
- "Filtro por hora" = **intervalo de data/hora explícito** (`desde`/
  `até`, inputs `datetime-local` do HTML5) — não é "hora do dia"
  (ex.: só 14h–15h ignorando data) nem um atalho de "últimas N horas".
- Cor por nível = **só os defaults do tema** (CSS vars já existentes)
  nesta rodada. `logging.ui.color.*` via `system_config` (pedido
  original) **fica fora do escopo desta rodada** — decisão explícita
  de não fazer agora, não esquecimento. Revisitar se surgir pedido
  real de customização.

**Detalhe de design que não estava no pedido original, decidido por
consequência direta da investigação**: `LogAdminService.read_content()`
hoje só lê as últimas 1000 linhas do arquivo (tail). Quando um filtro
de `desde`/`até` for aplicado, a leitura precisa ignorar esse limite
de 1000 e varrer o arquivo inteiro — senão um filtro pra uma janela de
tempo mais antiga que as últimas 1000 linhas simplesmente não acha
nada, silenciosamente. Sem filtro ativo, o comportamento atual (tail
1000) continua valendo.

Nenhum arquivo tocado ainda — esta rodada foi só decisão. Pendente de
autorização explícita pra implementar.

**[EXECUTADO em 2026-07-07, sessão seguinte]** — implementado exatamente
como decidido, sem desvio:
- `core/log_admin_service.py`: `_parse_lines()` novo (regex sobre o
  formato de linha real, linha de continuação anexada à mensagem
  anterior). `read_content()` ganha `desde`/`ate` — sem filtro,
  comportamento antigo (tail `max_lines`); com filtro, varre o arquivo
  inteiro e ignora `max_lines`.
- `controller/core/admin_logs.py`: `view()` lê `desde`/`ate` da
  querystring (`datetime-local` do HTML5).
- `templates/core/admin/logs_detail.html`: formulário de filtro +
  linhas coloridas por nível (`.log-level-*`, CSS novo em
  `components.css` reaproveitando as vars do tema
  `--color-info/success/warning/danger`, light e dark).
- 6 testes novos em `tests/test_logging_admin.py` — parsing,
  continuação de traceback, filtro ignorando `max_lines`, filtro sem
  correspondência, cor renderizada na tela, filtro via querystring.
- Suíte completa: 38 arquivos, 460 testes, zero regressão.

## Item (e) — Manual de de-para do BrewFather — CONCLUÍDO

`addons/addon_brewstation/features/feature_brew_father/docs/technical/06-manutencao-e-expansao.md`
criado (não existia): visão prática do fluxo de-para (onde cada passo
mora no código real, complementando o diagrama de sequência já
existente em `feature_mash_control/docs/technical/03-fluxos.md`, sem
duplicar), como o autocreate resolve os campos obrigatórios de
`Material`, e checklist prático de "como adicionar um campo novo
importado do BrewFather" (mesmo caminho que o item (c) — adjuntos/água
— vai seguir quando for implementado).

**Achado durante a escrita**: `docs/technical/01-visao-geral.md` e
`04-modelo-de-dados.md` desta Feature estavam desatualizados —
diziam "`sync_service.py`/`BrewFatherSync` ainda não implementado",
quando já estavam implementados há sessões. Corrigido nesta rodada
(pequeno, cirúrgico — não reescrita completa).

## Fechamento do CrudGen (skill 12) — EXECUTADO

Retomada da conversa sobre anotações/referência fraca/combobox — 3
decisões fechadas e implementadas na mesma sessão. Detalhe completo em
`docs/skills/12-crudgen-referencia-completa.md`.

- [x] `@required`/`@max_length`/`@min_length`/`@min_value` ligadas a
      algo real: HTML5 nativo (`required`/`maxlength`/`minlength`/
      `min` + badge `*` no label) em `manage.html.j2`/`detail.html.j2`,
      e seed de `FieldRule` (create-only, nunca sobrescreve depois —
      mesmo espírito de hook) usando o `rule_id` que já existia em
      `core/rules_catalog.py` (nenhum `rule_id` novo inventado).
- [x] `--only templates` implementado (`core/crudgen/generator.py` +
      `core/cli.py`) — regenera só `manage.html`/`detail.html`, exige
      `--overwrite` junto (erro claro se faltar).
- [x] Migração pro caminho de auto-descoberta (skill 09):
      `register_models()`/`register_routes()` de `feature_yeast_bank`,
      `feature_mash_control`, `addon_device_manager` migrados.
      `get_transactions()` mantido manual em todo módulo (decisão
      confirmada — automático perderia hierarquia/descrição/ícone
      curados e mudaria códigos `TX_` referenciados por 3 arquivos de
      teste). Achado real: 2 dos 3 módulos tinham efeito colateral em
      `register_routes()` além de registrar Blueprint (EventBus,
      TASK_REGISTRY) — preservados explicitamente, só o loop mecânico
      de registro de Blueprint foi trocado por `discover_blueprints()`.
- [x] `docs/skills/12-crudgen-referencia-completa.md`: catálogo de
      anotações atualizado (validações deixaram de ser vestigiais),
      guia de uso detalhado de cada anotação com exemplo, argumentos
      de geração completos (`--only` incluso).

**Não resolvido, fora do escopo desta rodada**: `@listview`/`@form`/
`Column`/`Filter`/`Group` continuam sem consumidor — não fizeram
parte do pedido. `@max_value` não existe (só `min_value`) — catálogo
de regras já tem `max_valor` pronto, falta só a anotação.

Testes novos: 6 em `tests/test_phase4_crudgen.py` (FieldRule semeada
com os valores certos, create-only não duplica nem sobrescreve
customização, HTML5+badge no HTML gerado, `--only templates` escreve
só 2 arquivos, erro claro sem `--overwrite`, erro claro com valor
inválido) + 2 em `tests/test_crudgen_cli_generate_relationship_bug.py`
(mesmo via CLI real). Suíte completa: 38 arquivos, todos passando.

## Documentação de excelência do CrudGen (skill 13) — CONCLUÍDA

`docs/skills/13-crudgen-guia-operacional.md` — companheiro prático da
skill 12. Cobre exatamente os 4 pontos pedidos: fluxo de objetos,
hooks antes/depois, pontos de manutenção, como incluir campos.

**Achado central, investigado a fundo no código real antes de
escrever**: hooks de lifecycle "antes/depois de qualquer método" são
mais restritos do que o nome sugere — só existem 2
(`pbo_apply_fields`/`pai_apply_fields`), só ao redor de
`_apply_fields()` no Service, usado só por `create()`/`update()`. Não
existe hook de lifecycle em `list()`/`get_by_id()`/`trash()`/
`restore()`/`delete_permanent()`, nem em nenhum ponto do Controller ou
das Rotas API — nesses lugares, `*_hooks.py` serve só pra adicionar
rota nova (extensão por adição), não pra interceptar o fluxo existente
(extensão por interceptação). Documentado com o contrato exato de
cada hook (quando roda, parâmetros, o que o retorno faz) e como
distinguir create de update dentro do hook (`obj.id is None`).

**Segundo achado**: a tela de lista (`manage()`, caminho Web) **não
passa pelo `Service.list()`** — monta a query direto no controller.
`Service.list()` só é usado pelo caminho API. Quem for customizar
busca/filtro da lista precisa saber que a lógica mora no controller
(`_apply_filters()`), não no Service.

Sem mudança de código — só documentação, conforme pedido.

## Cobertura de documentação do "resto do sistema" — 2 itens concluídos

Retomada da pergunta "já temos documentação completa, incluindo o
resto do sistema?" — levantamento real mostrou 2 gaps concretos,
priorizados pelo Christopher (itens 1 e 3 de uma lista de 4):

- [x] **`docs/manual/` dos 4 módulos que estavam zerados**
      (`addon_estoque`, `feature_brew_father`, `feature_envase`,
      `feature_ingredientes`) — 16 arquivos novos (4 cada), seguindo
      o padrão já estabelecido nos módulos que já tinham (tom direto,
      sem jargão de arquitetura, exemplos com nome de botão/tela real
      conferido no HTML — não inventado). `docs/technical/` já estava
      completo nos 8 módulos antes desta rodada, só `docs/manual/`
      tinha o gap.
- [x] **Skill 14 (EventBus)** — convenção de nome de evento e
      contrato de payload, formalizando o que já estava em uso (2
      pares publisher/subscriber reais: `core.module.activated`,
      `device_manager.actor.value_changed`). 2 achados de manutenção
      registrados como `[ABERTO]`, não resolvidos nesta rodada (não é
      documentação, seria mudança de código): nome de evento
      duplicado como string literal em publisher e subscriber (risco
      de deriva silenciosa se um lado for renomeado sem o outro);
      docstring desatualizada em `register_example_listener()` que já
      deveria ter sido removida segundo seu próprio comentário.

**Ainda pendente, não priorizado nesta rodada** (itens 2 e 4 da lista
original): `i18n/pt_BR.json` zerado em 7 dos 8 módulos; motor de
regras (Fase 7b) só com Validação implementada; Designer visual (Fase
7c) e OData Screen Generator (Fase 8) não iniciados.

Sem mudança de código — só documentação.

## Bugs de OData (Fase 8): CORRIGIDO — Skill 06 adenda (Playground v2): DOCUMENTADO (pendente implementação)

Uso real de duas ferramentas de admin (Conexões OData e API/SQL
Playground) revelou 2 bugs concretos e 1 gap de capacidade, todos
diagnosticados no código real antes de decidir a correção.

**Bugs de OData (`core/odata/connection_manager.py`,
`controller/core/admin_odata.py`) — [x] CORRIGIDO:**
- [x] **Descoberta de `$metadata`** (`_discover_and_fetch_metadata`):
      quando `base_url` cadastrada já é a própria URL de `$metadata`
      (em vez da raiz do serviço), o código concatenava sufixos em
      cima dela (`.../$metadata/$metadata.json`) e sempre dava 404.
      Corrigido com `_strip_metadata_suffix()` — se `base_url` bate
      com um sufixo de metadata conhecido, tenta ela mesma crua
      primeiro (`accept="auto"`) e usa a raiz "descascada" pro
      restante da cadeia (fallback).
- [x] **Browse usando `EntityType.Name` em vez de `EntitySet.Name`**:
      para servidores OData EDMX reais, a URL de coleção é o nome do
      `EntitySet` (plural, ex. `Products`), não o `EntityType` (ex.
      `Product`). Corrigido com `_extract_entity_set_map_xml()` /
      `_extract_entity_set_map_json()`, lendo `EntityContainer/
      EntitySet` (XML e EDMX-JSON) e usando `EntitySet.Name` como
      nome de rota; `EntityType.Name` guardado à parte em
      `entity_type_name` (usado como `label`).
- [x] **Nova coluna `entity_route_overrides`** (JSON, nullable) em
      `tesseract_odata_connection`, migration `a1c7f92e5b04` — para o
      formato customizado "S2MOdataPy" (sem `EntityContainer`):
      `query()` tenta o nome declarado, se 404 tenta uma pluralização
      heurística simples (`_pluralize_guess`: `y→ies`,
      `s/x/z/ch/sh→+es`, senão `+s`) e persiste o que funcionou via
      `_persist_route_override()`; tela "Ver entidades" ganha campo
      editável por entidade (`set_entity_route_override`, rota POST
      `/admin/odata/<id>/entities/override`) para corrigir
      manualmente se a heurística errar.

Testes: `tests/test_odata_bugfixes.py` (5 novos, cobrindo os 3 pontos
acima + override manual via service e via tela) — suíte completa
479/479 passando (12 pré-existentes de `test_phase8_odata.py`
continuam passando sem alteração). Migration validada isoladamente
(upgrade adiciona a coluna, downgrade remove) — o `flask db upgrade`
completo do zero falha por um bug pré-existente **não relacionado**
(coluna duplicada em `tesseract_brewstation_mashctrl_rule`,
confirmado reproduzindo no HEAD anterior a este patch), registrado
aqui como novo achado para investigar depois, fora do escopo desta
correção.

**Skill 06 adenda — Playground v2** (texto já escrito em
`docs/skills/06-model-builder-e-playground.md`, seção 8) —
[x] **EXECUTADO (Patch D)**: Auth dedicada (`bearer`/`basic`/`api_key`,
`_auth_headers_for()`), Query Params estruturados (`params_json` +
`_build_query_params()` — resolve a causa raiz de um 404 que parecia
falha de autenticação, ver skill 06 §8.0), cookie jar por usuário
(`tesseract_playground_cookie_jar`, `_load_cookie_jar()`/
`_save_cookie_jar()`) e pastas em árvore N-níveis
(`tesseract_playground_folder`, `list_folder_tree()`) com arquivar
(`set_archived()`) separado de apagar (`delete_request()`, DELETE
físico). Migration `b2d8a04f6c17` — 2 tabelas novas + 5 colunas em
`tesseract_playground_request`. Nenhuma permissão RBAC nova (reaproveita
`playground_requests.execute`, confirmado). `execute_http_request()`
passou a usar `requests.Session()` em vez de `requests.request()`
avulso — os 2 testes antigos que mockavam a chamada HTTP foram
atualizados para o novo ponto de mock (`requests.Session.request`),
sem mudança de comportamento esperado.

Achado durante a implementação, não previsto na skill: os models novos
(`PlaygroundFolder`/`PlaygroundCookieJar`) precisam ser importados
explicitamente em `core/app_factory.py` (mesmo padrão já usado pra
`playground_request`) — sem isso, `PlaygroundRequest.folder_id`
(FK pra uma tabela cujo model nunca foi importado) quebra
`db.create_all()` em qualquer teste/boot que não passe pelo controller
do Playground primeiro. Corrigido junto neste patch.

Confirmado (mesma causa já registrada acima, não é bug novo): rodar
`flask db upgrade` do zero segue exigindo o contorno de isolar
`ModuleManager.create_all_pending_tables()` pra validar uma migration
nova sem o `db.create_all()` do boot "adiantar" a criação da tabela —
mesmo comportamento já visto na migration de OData. Migration
`b2d8a04f6c17` validada isoladamente (upgrade cria as 2 tabelas + 5
colunas; downgrade remove tudo de volta). No caminho, a primeira
versão da migration também tinha um bug próprio, sem relação com esse
achado: `batch_alter_table` no SQLite exige nome explícito de
constraint pra Foreign Key — `add_column` com `ForeignKey` inline
falhava; corrigido com `batch_op.create_foreign_key(...)` nomeado
separado do `add_column`.

Testes: `tests/test_playground_v2.py` (19 casos novos — auth por tipo,
params habilitados/desabilitados, cookie jar persistindo entre
chamadas, pastas/subpastas, bloqueio de apagar pasta não-vazia, mover
requisição, arquivar/desarquivar, apagar definitivo, rotas web) +
`tests/test_playground.py` (pré-existentes, 2 com mock atualizado).
Suíte completa do projeto: 498/498 passando.

## Achados reais de uso do patch anterior — 3 correções: CORRIGIDO

Depois de aplicar o patch do Playground v2, uso real revelou 3
problemas — um bloqueante (banco quebrado sem apagar), dois de UX
(campo livre em vez de select).

### 1. `db.create_all()` vencendo a corrida do Alembic em qualquer migration que crie tabela — CORRIGIDO

**Confirmado bloqueando de verdade** (não só "banco vazio do zero",
como o achado anterior já registrado): reproduzi o cenário exato —
banco já existente, migration `a1c7f92e5b04` aplicada, aplica o patch
do Playground v2 (código com os models novos) e roda `flask db
upgrade` → `OperationalError: table tesseract_playground_folder
already exists`. Causa: `ModuleManager.create_all_pending_tables()`
chama `db.create_all()` em TODO boot do app, inclusive quando o boot é
disparado pelo próprio comando `flask db upgrade` — `db.create_all()`
cria a tabela nova (já com o shape final, refletindo o model
atualizado) antes do Alembic ter a chance, e o `CREATE TABLE`/`ADD
COLUMN` da migration falha como duplicado.

**Correção**: `core/module_manager.py` — nova função
`_running_under_flask_db_command()` (checa `sys.argv[1] == "db"`,
cobre tanto `flask db ...` quanto `python run.py db ...`, mesmo
`FlaskGroup`). `create_all_pending_tables()` pula o `db.create_all()`
quando essa checagem é verdadeira — nesse contexto o Alembic é quem
manda no schema. Fora de comando `db`, comportamento idêntico ao de
antes (nenhuma regressão).

**Validado**: reproduzido o cenário real (banco no estado exato de
antes do patch do Playground v2, via `git worktree` no commit
correspondente) e confirmado que `flask db upgrade` agora migra limpo
até `b2d8a04f6c17`, sem precisar apagar o banco. Suíte completa
510/510 (8 testes novos em `tests/test_phase5_module_manager.py`).

**Nota**: isso não muda a situação já registrada de `flask db upgrade`
100% do zero (banco totalmente vazio) — essa combinação depende também
do bug pré-existente e não relacionado da migration de
`mash_control_rule` (coluna duplicada), que continua fora do escopo
desta correção.

### 2 e 3. Addon/Feature em texto livre no Model Builder e na ponte do Playground — CORRIGIDO

Achado: digitar o nome errado de um addon/feature (typo, ou um nome
que nunca existiu) falhava silenciosamente mais adiante no fluxo, sem
nenhuma UI mostrando quais nomes existem de fato — nas duas telas que
criam `ModelDefinition` (Model Builder direto, e a ponte "Usar
resposta como base de campos" do Playground).

**Correção**: nova função `list_existing_addons(project_root)`
(`services/core/model_builder_service.py`) — escaneia
`addons/addon_*/addon.json` + `features/feature_*/feature.json` em
disco (não depende do Addon estar ativo) e devolve
`[{"name","label","features":[...]}, ...]`.

- **Model Builder** (`templates/core/admin/model_builder_manage.html`):
  Addon/Feature viram `<select>` (populados com a lista real) para o
  escopo "Addon/Feature já existente" — continuam campo de texto (novo
  nome) só quando o escopo é "Addon novo"/"Feature nova". Cascata via
  JS: mudar o Addon selecionado repopula o `<select>` de Feature a
  partir do `data-features` embutido na `<option>`.
- **Ponte do Playground** (`templates/core/admin/playground.html`,
  formulário "Usar resposta como base de campos"): mesma ideia, mais
  simples (só existente, sem os escopos "novo") — `<select>` de
  Addon/Feature com a mesma cascata via JS (`.pg-bridge-*`).

Fluxo de geração da tabela em si não mudou — confirmado que o formato
de 2 etapas (Playground cria rascunho → revisão/edição de campos no
Model Builder → botão "Gerar") já cobre o pedido, só faltava o select
funcionar.

Testes: 6 novos em `tests/test_model_builder.py`
(`list_existing_addons` com/sem features, pasta sem manifesto, pasta
`addons/` inexistente, `<select>` presente na tela) + 1 novo em
`tests/test_playground_v2.py` (selects da ponte presentes na tela).

## Achado avulso — configuração de nível máximo de ícone no menu sem UI: CORRIGIDO

`core.menu.icon_max_depth` (skill 10 §5.2) já existia e funcionava
(`templates/core/base.html`, testado desde a skill 10) — mas só era
alterável direto no banco (`system_config`), sem nenhum controle na
tela `/admin/menu-settings`. Adicionado `<select>` na tela ("Sempre" /
"Só até o nível N", N de 0 a 5), com getter/setter novos em
`services/core/menu_preference_service.py`
(`get_global_icon_max_depth()`/`set_global_defaults(icon_max_depth=)`)
seguindo exatamente o mesmo padrão já usado por
`default_sidebar_collapsed`. 2 testes novos em
`tests/test_menu_hierarquico.py` (select presente na tela; salvar pela
tela reflete de fato na sidebar).

Suíte completa do projeto após os 3 achados: **510/510 passando**.

## Auditoria e atualização completa da documentação (skill 04): CONCLUÍDA

Verificação de toda a documentação existente (Sistema + 3 Addons + 5
Features) contra o estado real do código, seguida de atualização —
sem nenhuma mudança de código, só `.md`.

**Gaps estruturais corrigidos** (arquivo obrigatório da skill 04
ausente):
- `feature_ingredientes/docs/technical/06-manutencao-e-expansao.md` —
  criado (não existia).
- `feature_envase/docs/technical/06-manutencao-e-expansao.md` —
  criado (não existia).

**Inconsistências factuais corrigidas** (doc dizia uma coisa, código
fazia outra):
- `feature_mash_control`: manual afirmava que a automação "ainda não
  está disponível" — na verdade já está ativa e reativa via EventBus
  desde a Fase E da skill 05. Corrigido no manual (4 arquivos) e no
  técnico (`06-manutencao-e-expansao.md` também dizia "sem scheduler
  ainda", desatualizado desde que o sistema de Tasks/`APScheduler`
  entrou).
- `feature_mash_control/06-manutencao-e-expansao.md`: citava
  `feature_device_manager` (nome antigo, Feature que não existe mais)
  em vez de `addon_device_manager`, e não mencionava a dependência de
  `estoque` que o `feature.json` real já declara.
- ER de `feature_mash_control` (`04-modelo-de-dados.md`): só
  detalhava 8 das 18 entidades reais — `plant_vessel`, `plant_mapping`,
  `session_log`, `session_alarm`, `layout`, `widget`, `rule_log`,
  `water_profile`, `fermentation_step`, `mash_step` estavam ausentes
  do diagrama. Reescrito com as 18.
- Contagem de entidades desatualizada em `addon_brewstation` (C4 e
  `04-modelo-de-dados.md`): `feature_mash_control` citada como 15,
  real é 18; `feature_brew_father` citada como "0 tabela própria",
  real é 1 (`BrewFatherSync`).
- 4 notas de pendência falsas ("`docs/manual/` ainda não escrito")
  em `addon_estoque`, `feature_ingredientes`, `feature_envase`,
  `feature_brew_father` — o manual já existia (e em bom estado) nos 4
  casos; a nota só não tinha sido atualizada.

**Sistema (`docs/`) — desatualizado havia várias skills** (não
mencionava Playground v2, Model Builder, Menu hierárquico/skill 10,
EventBus/skill 14, auto-descoberta/skill 09, logging admin/skill 08,
referência fraca/skill 11): os 7 técnicos e os 4 manuais foram
reescritos/expandidos pra cobrir tudo isso — C4 (Contexto/Container)
com as caixas de `addon_estoque`/`addon_device_manager`/MQTT/bridge,
9 sequências novas em `03-fluxos.md`, ER com as tabelas
`tesseract_model_definition`/`tesseract_model_field_definition`/
`tesseract_playground_*`/`tesseract_user_menu_preference`/
`tesseract_scheduled_task`/`tesseract_task_log`/
`tesseract_message_queue` que faltavam, 7 casos de uso novos (UC13-19)
com 2 diagramas, e novas linhas na tabela de erros conhecidos
(incluindo o achado do `db.create_all()` vs Alembic desta mesma
sessão).

**Manuais reescritos com conteúdo real** (eram esqueleto, 5-8 linhas):
Sistema (4 arquivos), `addon_brewstation` (4, corrigindo referências
a `feature_device_manager`), `feature_yeast_bank` (4),
`feature_mash_control` (4, ver correção factual acima).
`feature_ingredientes`/`feature_envase`/`feature_brew_father` já
estavam bons — não reescritos, só a pendência falsa corrigida.
`addon_device_manager`/`addon_estoque` já estavam em bom estado
(técnico e manual) — só ajustes pontuais.

**Diagramas novos adicionados** onde ajudavam e não existiam: 2 no
Sistema (fluxo do menu hierárquico, fluxo de sensor→EventBus), 1 em
`addon_estoque` (movimentação→saldo), 1 em `05-casos-de-uso.md` do
Sistema pro fluxo do Model Builder.

**Gap não coberto por esta rodada** (fora de escopo — é código, não
doc): `i18n/pt_BR.json` ainda ausente em `addon_brewstation` (Addon +
5 Features) e `addon_estoque` — já registrado, mantido como está.

34 arquivos alterados, 2 criados, nenhum código tocado.

## Model Builder — editar campo, preview e guia de anotações: CORRIGIDO

Uso real revelou 3 gaps na tela de detalhe (`/admin/model-builder/<id>`):
campos (inclusive os inferidos pela ponte do Playground, skill 06 §5)
não tinham opção de editar depois de criados, e faltava uma forma de
visualizar o `model.py` resultante antes de gerar de verdade (like o
PyTeca tinha).

- **Editar campo**: `services/core/model_builder_service.py::
  update_field()` (mesma validação de FK de `add_field`, sem
  duplicar a regra da skill 02) + rota `POST /<id>/fields/<field_id>/
  edit`. Tela: botão "editar" por linha (inclusive campos vindos da
  inferência do Playground) que pré-preenche o mesmo formulário de
  "adicionar campo" com TODAS as opções (antes só existiam via
  "adicionar" — nome/tipo/label chegavam da inferência, mas nullable/
  unique/max_length/FK/listview/form ficavam sempre no default, sem
  como ajustar).
- **Preview do Model**: `services/core/model_builder_service.py::
  preview_model_source()` — reaproveita exatamente a mesma renderização
  de `model.py.j2` usada por `generate()`, sem escrever nada em disco.
  Aparece na tela de detalhe, atualizado a cada campo adicionado/
  editado/removido (reload da página já reflete — sincronização
  visual→texto).
- **Guia de Anotações**: painel de referência (colapsável) na própria
  tela, cobrindo as 12 anotações de `annotations/__init__.py`
  (`@label`/`@plural`/`@display_field`/`@weak_ref`/`@required`/
  `@max_length`/`@min_length`/`@min_value`/`@choices`/`@listview`/
  `@form`/`@permission`/`@menu_icon`), pra quem preferir editar o
  `model.py` gerado direto em texto.

**Decisão registrada** (conversa 2026-07-09): texto→visual (reverse-parse
do `model.py` editado à mão de volta pros campos da tela) fica pra
depois — risco de ambiguidade em Python fora do padrão esperado, e o
Model Builder já deixa claro que não faz esse reverse-parse hoje (nota
na própria tela). Só visual→texto (preview) foi implementado nesta
rodada.

Testes: 7 novos em `tests/test_model_builder.py` (editar valores/
ordem preservada, campo inexistente, FK inválida rejeitada, preview
reflete campos atuais, preview muda ao editar, rota HTTP de editar,
tela mostra preview + guia). Suíte completa: 517/517 passando.

## Model Builder: reposicionar campos (drag-and-drop) + tipo JSON com sub-campos: CONCLUÍDO

Dois achados reais de uso, sobre a tela `/admin/model-builder/<id>`:

### 1. Reposicionar campos (arrastar e soltar)

`order_index` já existia (`ModelFieldDefinition.order_index`,
`ModelDefinition.fields` já ordenado por ele) — só faltava a
interação. `services/core/model_builder_service.py::reorder_fields()`
novo + rota `POST /admin/model-builder/<id>/fields/reorder` (JSON, sem
redirect — chamada via `fetch()`). Template: linhas da tabela de
campos viram `draggable="true"`, drag-and-drop nativo (sem
biblioteca), persiste a nova ordem a cada solto.

### 2. Sub-campos aninhados (tipo JSON) — retorno de API não é mais perdido

Causa raiz: `_infer_field_type()` (`playground_service.py`) tratava
qualquer objeto ou array aninhado num JSON de resposta como `string`
— literalmente tentava guardar `str({...})`, perdendo a estrutura.
Decisão registrada (confirmada em conversa): sub-campos são **metadado
de documentação**, nunca viram sub-tabela relacional de verdade (isso
seria um projeto à parte — migration própria, FK, CRUD separado).

- `model/core/model_field_definition.py`: `ModelFieldType.JSON` (→
  `db.JSON`) + coluna `json_schema` (migration `c3f9b15e7a82`) —
  `[{"name", "type", "children": [...]}]`, 2 níveis (sub-campo +
  filho do sub-campo).
- `services/core/playground_service.py`: `_infer_field_type()` agora
  detecta `dict`/`list` e retorna `json`; `_infer_json_schema()` novo
  infere os sub-campos automaticamente a partir da amostra (cap de
  profundidade em 2 níveis, evita árvore infinita em JSON muito
  aninhado); `infer_fields_from_json()` repassa o schema inferido.
- `core/crudgen/templates/model.py.j2` +
  `_field_template_context()`/`_render_json_schema_summary()`: preview
  e geração real mostram um comentário acima da coluna JSON com o
  formato esperado.
- `templates/core/admin/model_builder_detail.html`: editor de
  sub-campos (nome + tipo + "tem filhos?", recursivo até 2 níveis),
  visível só quando o tipo do campo é `json`; pré-preenchido ao editar
  um campo já existente (inclusive os que vieram da inferência do
  Playground).

Testes: 7 casos novos (`add_field`/`update_field` com `json_schema`,
preview com o comentário, `reorder_fields` via service e via rota web,
inferência de objeto/array aninhado, cap de profundidade). Suíte
completa do projeto: **525/525 passando**. Migration validada
isoladamente (upgrade adiciona a coluna, downgrade remove).

## `flask db upgrade` do zero absoluto falhando: CORRIGIDO (era o bug "pré-existente" já registrado múltiplas vezes)

O bug que vínhamos documentando como "pré-existente, fora de escopo"
(coluna duplicada em `tesseract_brewstation_mashctrl_rule`) voltou a
aparecer bloqueando de verdade — Christopher reportou dois erros em
sequência: `no such column: tesseract_model_field_definition.json_schema`
(banco sem a migration mais recente aplicada) e, ao tentar `flask db
upgrade` pra corrigir isso, `duplicate column name:
sensor_function_name` numa migration bem mais antiga
(`4a8524f00549`). Dessa vez foi resolvido de verdade, em vez de
adiado.

**Causa raiz completa**: `db.create_all()` roda em todo boot do app
(necessário — é o que cria tabela de Addon, que não passa por
Alembic). Isso inclui o **primeiro boot de qualquer pessoa**, antes
mesmo dela rodar `flask db upgrade` pela primeira vez. Nesse primeiro
boot, `db.create_all()` já cria o schema inteiro na forma **atual**
(refletindo os models de hoje — já com `json_schema`, já com
`sensor_function_name`, sem a coluna `group` antiga, etc.). Quando a
pessoa então roda `flask db upgrade`, o Alembic tenta replay de **toda
a cadeia histórica** de migrations, cada uma pressupondo transformar
um schema antigo que, nesse cenário, nunca existiu de verdade — daí
"duplicate column"/"already exists" em cascata, migration após
migration.

Esse **não é um caso raro** — é o caminho padrão de qualquer pessoa
que clona o projeto e roda `python run.py start` (ou qualquer boot
normal) antes de `flask db upgrade`.

**Correção**: auditadas as 12 migrations da cadeia inteira
(`091f87025ce4` até `c3f9b15e7a82`) — 9 delas tinham `add_column`/
`create_table`/`rename_table`/`create_unique_constraint` sem checagem
de existência:
- `4a8524f00549`, `7b3e9c1a2d4f`, `9c4f1e8a3b27`, `c2a7e5f19b04`,
  `d8b1f4a6c930`, `f4c8a2d61b73`, `3a91c7de5f42`, `8e2f6b1a94dc`
  (todas anteriores a este patch) + `a1c7f92e5b04`, `b2d8a04f6c17`,
  `c3f9b15e7a82` (escritas em sessões anteriores desta mesma
  conversa — o mesmo erro que eu já tinha cometido antes, sem
  perceber que era sistêmico).
- Cada uma ganhou `_table_exists()`/`_column_exists()`/
  `_fk_exists()`/`_unique_constraint_exists()` (padrão já usado em
  `4a8524f00549` desde a Fase 9, agora generalizado) — se a
  tabela/coluna já existe (porque `db.create_all()` já criou), o passo
  vira no-op em vez de tentar recriar.
- Achado um segundo bug real, independente, em `d8b1f4a6c930`:
  `op.create_unique_constraint(...)` fora de `batch_alter_table` nunca
  funcionaria no SQLite ("No support for ALTER of constraints") —
  corrigido envolvendo em modo batch.
- `3a91c7de5f42` (menu hierárquico) é a mais delicada — faz migração
  de **dado**, não só schema (lê a coluna `group` antiga pra criar
  nós-pasta). Guardada por inteiro: se `parent_id` já existe (schema
  já na forma atual), a migration inteira vira no-op — não há `group`
  legado pra migrar nesse cenário, porque essa coluna nunca existiu.

**Validado fim-a-fim**: banco criado do zero absoluto via
`db.create_all()` com o código atual (sem nenhum stamp, sem nenhuma
migration aplicada — reproduzindo o cenário real do Christopher) +
`flask db upgrade` real (subprocess, não atalho) → passa pelas 12
migrations sem nenhum erro, chega limpo em `c3f9b15e7a82`. Downgrade
completo (`c3f9b15e7a82` → `091f87025ce4`) também testado, sem erro.

Teste de regressão novo: `tests/test_migrations_idempotent.py` (2
casos, via `subprocess` chamando `flask db upgrade`/`downgrade` de
verdade — não um atalho) garante que isso nunca mais regride
silenciosamente. Suíte completa do projeto: **525/525 passando**
(inalterada — só arquivos de migration foram tocados, mais os 2 testes
novos).

**Ainda em aberto**: nenhum. Este era o último item pendente da
categoria "bug de infraestrutura do `flask db upgrade`" registrada
nas rodadas anteriores.

## Model Builder: tabela filha de verdade (relacionamento 1:1/1:N) + árvore na tela: CONCLUÍDO

Evolução do "tipo json com sub-campos" (patch anterior): decisão
confirmada em conversa — objeto/array-de-objeto aninhado numa resposta
de API deve virar uma **tabela filha de verdade** (Model independente,
FK real, CRUD próprio), não só metadado de documentação. `json` continua
existindo só para array de valores simples (sem objeto) — não tem
"sub-campo" nomeado nesse caso, então não faz sentido virar tabela.

### Modelo de dados

- `ModelDefinition`: `parent_model_definition_id` (FK pra si mesma),
  `parent_fk_column_name`, `parent_relation_label`,
  `parent_relation_type` (`one_to_one`/`one_to_many`). Migration
  `d4e0a26f9c31`.
- `ModelFieldDefinition`: `field_type="table"` novo +
  `child_model_definition_id` (aponta pro `ModelDefinition` filho).
  Campo tipo `table` nunca vira coluna real no pai — é metadado de
  relação.
- **Cap de 1 nível** (decisão confirmada em conversa): a ferramenta só
  cria tabela filha em quem ainda não é filho de ninguém —
  `add_table_field()` rejeita explicitamente tentar criar neto.

### Geração — 3 passadas obrigatórias (2 bugs reais encontrados e corrigidos no caminho)

Christopher pediu explicitamente pra não mexer no CrudGen em si — a
tabela filha gera normal, com o pipeline inteiro (Service/Controller/
Routes/Templates + hooks), e por cima disso entra só 1 peça nova: um
`db.relationship()` no `model.py` do pai (`model.py.j2` ganhou um
bloco condicional) + uma seção "master-detail" injetada (splice de
string, não Jinja) no `detail.html` já escrito pelo CrudGen — 2
templates novos (`master_detail_section_one_to_one.html.j2` /
`_one_to_many.html.j2`), no mesmo estilo `@@token@@` do resto do
CrudGen (achado real: o CrudGen usa substituição de string simples
pros templates HTML, não Jinja de verdade em tempo de geração — model.py.j2
é a exceção, renderizado por Jinja de propósito pelo Model Builder).

Dois bugs reais de ordem de execução, achados só ao gerar de verdade
(pai + filho juntos):

1. **SQLAlchemy resolve o nome da classe do `relationship()` cedo
   demais.** `db.relationship("Filho", ...)` guarda só a string até a
   configuração do mapper — que dispara na primeira query/objeto ORM
   tocado (ex.: `snapshot_if_needed`, dentro do próprio pipeline do
   CrudGen do pai). Se o filho ainda não tinha sido *importado*
   nesse momento, falha (`InvalidRequestError: failed to locate a
   name`). Corrigido: `generate()` agora faz 3 passadas separadas —
   **1) escreve** todos os `.py` (pai + filhos) em disco, **2) importa**
   todos, **3) só então** toca o banco (snapshot + pipeline) pra
   qualquer um. Nenhuma escrita/import pode ficar misturada com
   toque de banco no meio.
2. **Prefixo de tabela também precisa ser aplicado pra todos antes de
   qualquer um tocar o banco.** Mesma classe de bug: a FK do filho já
   aponta pro nome final PREFIXADO do pai (previsto por
   `_predict_full_table_name()`), mas o prefixo em si só era aplicado
   dentro do pipeline do CrudGen do próprio pai — se a configuração do
   mapper disparasse antes disso (o que acontece), o pai ainda estava
   com `__tablename__` curto e o SQLAlchemy não achava a FK
   (`NoForeignKeysError`). Corrigido: nova "passada 2.5" aplica
   `apply_table_prefix()` em todos antes da passada 3.

### Tela — árvore recursiva

`templates/core/admin/model_builder_detail.html` reescrito com uma
macro Jinja recursiva (`fields_block`) — mesma estrutura de tabela +
formulário pra pai e pra cada filho, indentado, com o próprio
arrastar-e-soltar (`order_index` já era por `model_definition_id`,
só faltava escopar o JS por bloco — antes era 1 conjunto global de
IDs, agora cada bloco tem IDs próprios sufixados por
`model_definition_id`, e o JS itera `.mb-fields-block` /
`.js-fields-tbody` individualmente). `/admin/model-builder/` (lista)
agora só mostra rascunhos de topo (`parent_model_definition_id IS
NULL`) — filhos só aparecem dentro da árvore do pai.

### Inferência (ponte do Playground)

`_infer_field_type()`: dict → `table` (1:1); array de objetos →
`table` (1:N); array de valores simples → `json` (inalterado).
`create_model_definition_from_playground()` agora cria o Model filho
de verdade (via `add_table_field()`) com os campos dele já inferidos
da amostra, em vez de só documentar a forma.

Testes: 21 casos novos em `tests/test_model_builder.py` (inferência,
regras de cap/validação, geração real ponta a ponta com filho —
FK real, `relationship`, master-detail injetado, 1:1 com
`uselist=False`/`unique=True`, listagem só de topo, árvore na tela).
2 testes de `tests/test_playground.py` ajustados (`project_root` novo
parâmetro obrigatório). Suíte completa do projeto: **544/544
passando**. Migration validada isoladamente (upgrade adiciona as
colunas, downgrade remove).

## Reorganização de menu — BrewStation (Controle de Mostura + De-Para de Ingredientes): CONCLUÍDO

Reorganização puramente de menu (`parent_code` em `get_transactions()`),
decidida em conversa — nenhuma tabela, model, rota ou arquivo de
funcionalidade mudou de lugar. Motivação: "Controle de Mostura" tinha
18 páginas soltas no mesmo nível (o dobro do segundo maior grupo do
BrewStation), sem nenhuma sub-organização.

**Antes**: Controle de Mostura com 18 itens flat, incluindo o De-Para
de Ingredientes (mais relacionado a "Ingredientes" do que a "Mostura").

**Depois**:
```
Controle de Mostura
├── Receitas (6): Receitas de Brassagem, Ingredientes de Receita,
│   Passos de Mostura, Etapas de Fermentação, Perfis de Água,
│   Histórico de Receitas
├── Planta & Sessão
│   ├── Plantas de Brassagem, Vasilhames, Mapeamentos de Planta
│   └── Sessões / Batches (4): Sessões de Brassagem, Passos da Sessão,
│       Logs da Sessão, Alarmes da Sessão
├── Automação (2): Regras de Automação, Histórico de Regras
└── Dashboard (2): Layouts de Dashboard, Widgets de Dashboard —
    continuam declaradas (o CRUD é real), mas SAEM do menu por ação
    manual em /admin/transactions/ (is_active=False) — não por código,
    porque sync_transaction() nunca mexe em is_active de propósito
    (skill 10, controle é só via UI). Ver "Pendências" abaixo.

Ingredientes (4): Maltes, Lúpulos, Leveduras,
  Mapeamento de Ingredientes (De-Para) ← realocado, model/rota
  continuam em feature_mash_control, só o parent_code mudou
```

`addons/addon_brewstation/features/feature_mash_control/feature.py`:
4 grupos novos (`TX_GROUP_MASH_RECIPES`, `TX_GROUP_MASH_PLANT_SESSION`,
`TX_GROUP_MASH_SESSIONS` — filho de `TX_GROUP_MASH_PLANT_SESSION` —,
`TX_GROUP_MASH_AUTOMATION`) + `parent_code` de 16 transações
existentes reapontado (6 pra Receitas, 3 pra Planta&Sessão, 4 pra
Sessões, 2 pra Automação, 1 — o De-Para — pra `TX_GROUP_INGREDIENTES`,
já declarado em `feature_ingredientes/feature.py`, sem precisar tocar
nesse arquivo). `TX_DASHBOARD_LAYOUTS`/`TX_DASHBOARD_WIDGETS` mantidos
como estavam (parent + rota).

**Pendência criada nesta rodada**: "Sistema de dashboard com abas para
os processos" (visual de verdade, hoje só existe o CRUD dos dados cru)
— próximo ajuste. Quando existir, os 2 itens de Dashboard entram como
sub-grupo de `TX_GROUP_MASH_SESSIONS`.

**Ação manual necessária após aplicar este patch** (não é código):
desativar `Layouts de Dashboard`/`Widgets de Dashboard` em
`/admin/transactions/` — o sync nunca faz isso sozinho.

Testes: `tests/test_menu_grouped_by_feature.py` — 1 teste antigo
(contagem fixa de 18) reescrito em 6 testes novos, cobrindo a árvore
inteira (contagem por grupo + o De-Para no lugar novo). Suíte completa
do projeto: **549/549 passando**. Sem migration — `Transaction` já
suporta árvore (skill 10), isso é só dado (via sync no boot), não
schema.

## Dashboard de Brassagem — primeira versão funcional (v1): CONCLUÍDO

Arquitetura consolidada em conversa (mockup de referência com
caldeiras/tubulação) — ponto de encontro entre `addon_device_manager`
e `mash_control`. Decisões fechadas antes de implementar:
1. Sistema **especializado** (evolução de `DashboardLayout`/
   `DashboardWidget`, já existentes), não generalizado dentro do
   Designer genérico (Fase 7c) — mantém os dois mecanismos separados
   por ora.
2. Atualização por **polling** (3s), sem WebSocket/SSE — infra
   inexistente no projeto hoje, fica pra depois se precisar.
3. 7 tipos de widget de uma vez: vasilhame, botão liga/desliga, gauge,
   indicador digital, tubulação, lista de alarmes, gráfico histórico.
4. Gráfico histórico reaproveita `BrewSessionLog` (source="sensor")
   em vez de criar tabela de série temporal nova — só tem dado com
   Sessão de Brassagem ativa.

### O que já existia e foi reaproveitado (achado real ao investigar)

- `DashboardLayout`/`DashboardWidget` já tinham `svg_asset_key`,
  posição livre, `config_json`, referência fraca a `device_function_name`
  — só faltava a renderização.
- `BrewPlant.plant_schema_json` já existia, nunca lido em lugar
  nenhum — virou a fonte das conexões de tubulação.
- `BrewPlantMapping` já era, na prática, o "de-para de sensores"
  (role_key -> device_function_name por vasilhame) — reaproveitado
  integralmente pelo widget tipo "vessel", sem duplicar referência.
- `device_service.get_value()`/`set_value()`/
  `find_actor_external_id_by_function_name()` já prontos — nenhuma
  mudança no `addon_device_manager`.

### Schema novo (aditivo, migration `e5f1a37c8d02`)

- `DashboardWidget.vessel_id` (FK real → `plant_vessel.id`, mesma
  Feature) — só preenchido em widgets tipo "vessel".
- `DashboardLayout.plant_id` (FK real → `plant.id`) — resolve de qual
  planta vêm os vasilhames e as conexões de tubulação do layout.

### Peças novas

- `services/dashboard_reading_logger.py` — listener novo do EventBus
  (`device_manager.actor.value_changed`, mesmo padrão de
  `automation_engine.py`) — grava `BrewSessionLog(source="sensor")`
  só quando há Sessão ativa pra planta daquele sensor, com throttle
  de 30s (evita 1 linha por leitura).
- `services/dashboard_runtime_service.py` — `get_layout_snapshot()`
  (1 chamada só devolve o valor de todos os widgets), `set_widget_value()`
  (aciona atuador — resolve `role_key` pra widgets tipo vessel),
  `get_plant_connections()` (lê `plant_schema_json`, resolve estado
  "fluindo" via o atuador de cada conexão), `get_session_readings()`
  (histórico pro gráfico).
- `controller/dashboard_runtime.py` — blueprint novo, NÃO gerado pelo
  CrudGen (igual em espírito a `automation_engine.py`), auto-descoberto
  (skill 09): `/brewstation/dashboards/` (resolve o layout padrão),
  `/<id>/view` (tela visual), `/<id>/snapshot` (JSON, polling),
  `/widgets/<id>/set-value` (aciona atuador),
  `/sessions/<id>/readings` (dados do gráfico).
- `templates/dashboards/view.html` — canvas com os 7 tipos de widget
  (SVG pra tubulação com animação de fluxo, Chart.js — já vendorizado,
  nenhuma dependência nova — pro histórico), polling a cada 3s.
- `TX_DASHBOARD_VIEW` — nova entrada de menu dentro de
  `TX_GROUP_MASH_SESSIONS`, exatamente onde a reorganização de menu
  anterior já tinha previsto ("Dashboards vai entrar aqui quando o
  sistema de dashboard existir de verdade") — fecha essa pendência.

### Compatibilidade com `tesseract-device-bridge` (confirmado em conversa)

O dashboard é só mais um consumidor de `device_service` (mesma
infraestrutura MQTT que o bridge já usa pro fail-safe/LWT) — não cria
canal de comunicação novo, não muda protocolo, não precisa de nenhum
ajuste no bridge nem no `mqtt_client_service`. Se o Tesseract cair, o
dashboard fica indisponível, mas o bridge continua protegendo a
brassagem sozinho, como já era.

### Limitações conhecidas desta v1 (não são bugs, são escopo)

- Sem editor visual de drag-and-drop pra montar o layout — a posição/
  configuração de cada widget continua editada pelas telas de CRUD já
  existentes (`Layouts de Dashboard`/`Widgets de Dashboard`,
  reativadas — ver nota abaixo). A tela nova (`/view`) é só execução/
  visualização + acionamento de atuador, não é o "DESIGNER DE
  DASHBOARD" do mockup.
- Gráfico histórico só tem dado com Sessão de Brassagem ativa —
  limitação aceita e documentada (decisão da conversa).
- Sem WebSocket/SSE — atualização a cada 3s via polling, não é
  instantâneo.

**Ação manual recomendada**: como `TX_DASHBOARD_LAYOUTS`/
`TX_DASHBOARD_WIDGETS` foram desativados manualmente numa rodada
anterior (is_active=False), talvez valha reativá-los agora que servem
pra configurar os widgets de verdade (não são mais só "CRUD de dado
cru sem uso") — decisão sua, não fiz isso automaticamente (mesmo
motivo de sempre: sync nunca mexe em is_active).

Testes: `tests/test_dashboard_runtime.py` (17 casos novos — logger com/
sem sessão ativa, throttle, snapshot de widget simples e vessel,
acionar atuador direto e via vessel+role_key, conexões de tubulação,
leituras filtradas por função/janela, as 5 rotas web). 1 teste de menu
ajustado (contagem de filhos de Sessões/Batches, +1 pelo Dashboard
novo). Suíte completa do projeto: **566/566 passando**. Migration
validada isoladamente (upgrade adiciona as colunas, downgrade remove).

## Bug de log no Windows (PermissionError/WinError 32 na rotação): CORRIGIDO

Reportado com o traceback real do Windows: `RotatingFileHandler.doRollover()`
falhando com `PermissionError: [WinError 32] O arquivo já está sendo
usado por outro processo` ao tentar renomear `logs/core.log` →
`logs/core.log.1`.

**Causa raiz**: com `debug=True` (padrão de `python run.py start`),
`app.run()` liga o reloader do Werkzeug, que re-executa o processo
inteiro como subprocesso (`WERKZEUG_RUN_MAIN=true` só nesse
subprocesso). O processo original — que vira só "monitor", esperando
mudança de arquivo pra reiniciar — já tinha rodado `create_app()` uma
vez antes do fork, abrindo seu **próprio** handle de `logs/core.log`;
nunca mais escreve nele, mas também nunca libera. Quando o subprocesso
filho (que atende requisição de verdade) atinge o limite de 5 MiB e
tenta rotacionar, o Windows recusa o rename porque o monitor ainda
está com o arquivo aberto. **Unix não tem esse problema** (rename
funciona com o arquivo aberto por outro processo lá) — por isso nunca
apareceu nos meus próprios testes (sandbox Linux).

**Correção**: `core/logging_config.py` ganha `disable_file_handler()`
(fecha e remove qualquer `RotatingFileHandler` do logger raiz).
`run.py` (comando `start`) detecta, antes de chamar `app.run()`, se
este processo é o monitor do reloader (`debug=True` e
`WERKZEUG_RUN_MAIN` ainda não é `"true"`) e chama
`disable_file_handler()` nesse caso — o subprocesso filho (que
recebe `WERKZEUG_RUN_MAIN=true`) mantém o handler normalmente.

Testes: `tests/test_logging_windows_reloader_fix.py` (3 casos —
`disable_file_handler()` remove e fecha o handler, não falha sem
nenhum handler de arquivo, e o console handler sobrevive sozinho
depois). Não dá pra testar a interação real entre dois processos SO
dentro da suíte (é específico do reloader do Werkzeug rodando de
verdade) — a cobertura é da função em si, que é o que importa pra
não regredir. Suíte completa do projeto: **569/569 passando**.

Nenhuma mudança de schema — patch só em `core/logging_config.py` +
`run.py`.

## Matchcode (combo de busca) para os campos de FK/referência do Dashboard + device_manager: CONCLUÍDO

Pedido direto (capturas de tela de `dashboard-widgets`/`dashboard-layouts`
mostrando `Layout Id`/`Vessel Id`/`Plant Id`/`Device Function Name`
como `<input>` de texto cru): trocar por combo de busca, igual já
existia pra `Malte.material_id` etc. (skill 11). Extensão da skill 11,
não mecanismo novo.

### Achado 1 — o combo nunca existiu no formulário de CRIAÇÃO

A skill 11 original só cobria a tela de **edição** (`detail.html.j2`)
e a **listagem** (`manage.html.j2`, coluna) — o formulário de "+ Novo
registro" (inline, no topo do `manage.html.j2`) sempre foi `<input>`
cru pra TODO campo, mesmo os 6 já cobertos por `@weak_ref` desde a
skill 11 original (`Malte`, `Lupulo`, `Levedura`, `ItemEnvase`,
`RecipeIngredient`, `IngredientMapping`). Corrigido de uma vez pra
todo mundo — `manage.html.j2` ganhou o mesmo bloco de combo que
`detail.html.j2` já tinha, mais o `<script src=".../weak_ref_combo.js">`
que faltava lá.

### Achado 2 — `device_function_name` guarda `name`, não `id`

O mecanismo original de `/api/options` sempre devolvia `obj.id` (PK)
como valor do combo — funciona pra `material_id` (guarda
`Material.id`), mas `device_function_name` guarda
`DeviceFunction.name` (string, skill 02 — referência fraca cross-Addon
sempre por nome, nunca id interno). `@weak_ref` ganhou parâmetro
`value_field` opcional (default `None` = comportamento antigo
inalterado): `/api/options/<plural>?value_field=name` devolve a
coluna pedida em vez do `id` — **validada contra as colunas reais do
model alvo** antes de aceitar (nunca expõe atributo arbitrário).
Permite inclusive dois `@weak_ref` diferentes mirando o MESMO alvo com
`value_field` diferente (`DeviceActor.function_id` usa o padrão "id";
`DashboardWidget.device_function_name` usa "name" — sem conflito,
cada combo pede o que precisa).

### Campos cobertos

| Model | Campo | Alvo | `value_field` |
|---|---|---|---|
| `DashboardLayout` | `plant_id` | `BrewPlant` | id (padrão) |
| `DashboardWidget` | `layout_id` | `DashboardLayout` | id (padrão) |
| `DashboardWidget` | `vessel_id` | `BrewPlantVessel` | id (padrão) |
| `DashboardWidget` | `device_function_name` | `DeviceFunction` | **name** |
| `BrewPlantMapping` | `vessel_id` | `BrewPlantVessel` | id (padrão) |
| `BrewPlantMapping` | `device_function_name` | `DeviceFunction` | **name** — literalmente o "de-para de sensores" |
| `DeviceActor` | `device_id` | `DeviceMetadata` | id (padrão) |
| `DeviceActor` | `function_id` | `DeviceFunction` | id (padrão) |

`BrewPlant`/`BrewPlantVessel`/`DashboardLayout`/`DeviceMetadata`/
`DeviceFunction` ganharam `@display_field` (novo). Resolvers novos:
`mash_control_lookups.py` (get_plant/get_vessel/get_layout, mesma
Feature), `device_metadata_lookup.py` (novo arquivo, get_device_metadata),
`device_function_lookup.get_function_by_id` (novo, complementa o
`get_function_by_name` já existente — ambos ganharam a chave
`"display"` obrigatória que faltava em `get_function_by_name`).

**Nota de arquitetura**: `plant_id`/`layout_id`/`vessel_id`/`device_id`/
`function_id` são FK **real** (mesmo Addon/Feature, skill 02 permite).
Reaproveitar `@weak_ref` pra esses casos é deliberado — o combo é só
UI/formulário, não upgrade nem downgrade da constraint de banco; criar
um segundo mecanismo só pra "FK real com combo" duplicaria ~90% do
código já existente.

### Regeneração

4 entidades regeneradas via `python run.py generate --overwrite`
(mesmo precedente da skill 11 original): `DashboardLayout`,
`DashboardWidget`, `BrewPlantMapping`, `DeviceActor`. Como o template
`manage.html.j2` mudou globalmente, as 6 entidades antigas da skill 11
(`Malte`, `Lupulo`, `Levedura`, `ItemEnvase`, `RecipeIngredient`,
`IngredientMapping`) também foram regeneradas — ganham o combo no
formulário de criação de graça (Achado 1 acima), fechando o mesmo gap
pra elas também.

Testes: `tests/test_weak_ref_value_field.py` (18 casos — `value_field`
aceito/validado/inválido cai pro padrão, `display_field` nos 5 alvos,
os resolvers novos com a chave `display`, `@weak_ref` declarado
certo em cada model, combo aparecendo nos 3 formulários de criação
verificados, POST continua persistindo certo). Regressão:
`tests/test_weak_ref_display_field.py` (11 casos, os 6 usos antigos)
sem nenhuma mudança de comportamento. Suíte completa do projeto:
**587/587 passando**. Sem migration — nenhuma coluna nova, só
anotação + regeneração de tela.

## Cadastro Primário — importar devices.yml/recipe.yml do tesseract-device-bridge: CONCLUÍDO

Schema confirmado direto no README real do
[tesseract-device-bridge](https://github.com/ChristopherNicolasSMM/Tesseract-Device-Bridge)
(não inventado a partir só dos 2 arquivos enviados na conversa — o
projeto confirma que é exatamente esse formato). Nova tela
("Cadastro Primário") sobe `devices.yml` (obrigatório) + `recipe.yml`
(opcional) e monta o cadastro inicial completo, sem precisar passar
por nenhuma tela de CRUD na mão.

### Mapeamento

| YAML | Tesseract |
|---|---|
| `devices[]` (cada entrada) | 1 `DeviceFunction` + 1 `DeviceActor` (`addon_device_manager`) — `id` do YAML vira `DeviceFunction.name` (chave estável, skill 02) |
| Todos os `devices[]` juntos | 1 `DeviceMetadata` só (o "bridge" físico — nó único, cada device é uma porta dele) |
| `recipe.vessels[]` | `BrewPlantVessel` — `vessel_type` adivinhado a partir do `id` convencional (`mash`→`mash_tun`, `boil`→`boil_kettle`, etc., cai em `generic` se não reconhecer) |
| `vessel.sensor_device_id`/`heater_device_id` | `BrewPlantMapping` (`role_key="sensor_temp"`/`"actor_heat"`) — o "de-para" já fica pronto |
| bombas distintas usadas nos `steps` de cada vasilhame | `BrewPlantMapping` (`role_key="actor_pump_N"`) |
| bomba do primeiro step do vasilhame seguinte (por `order`) | `BrewPlant.plant_schema_json["connections"]` — tubulação, melhor esforço, editável depois |
| (implícito) | 1 `DashboardLayout` ("Painel de Mostura") + 1 widget tipo `vessel` por vasilhame + 1 widget `alarm_list` |

### Idempotência

Rodar a importação de novo (mesmo arquivo, ou um YAML atualizado com
mais devices) **reaproveita** o que já existe por nome/id em vez de
duplicar — cada passo (Function/Actor/Planta/Vasilhame/Mapeamento/
Layout/Widget) é `find_or_create`. Só o primeiro Layout importado
vira `is_default=True`.

### Peças novas

- `services/bridge_import_service.py` — `parse_devices_yaml()`,
  `parse_recipe_yaml()`, `import_bridge_config()` (orquestrador
  único, transacional). NÃO gerado pelo CrudGen.
- `controller/bridge_import.py` — blueprint novo, auto-descoberto
  (skill 09): `GET/POST /brewstation/bridge-import/`. Aceita upload
  de arquivo OU colar o YAML direto (textarea).
- `templates/bridge_import/form.html` — formulário + resumo do que
  foi criado/reaproveitado, com link direto pro Dashboard gerado.
- `TX_BRIDGE_IMPORT` — nova entrada de menu em `TX_GROUP_MASH_CONTROL`.
- **`PyYAML` — dependência nova** (`requirements.txt`, UTF-16LE
  preservado). Não existia no projeto — só o bridge (repositório
  separado) tinha PyYAML no próprio `requirements.txt` dele.

### Achado real corrigido no caminho

Bug de contabilidade na idempotência: o widget `alarm_list`, quando
já existia numa segunda importação, não era registrado nem em
"criados" nem em "reaproveitados" (ficava invisível no resumo) —
`else` faltando. Achado pelo próprio teste de idempotência, corrigido
antes de fechar.

Testes: `tests/test_bridge_import.py` (14 casos, usando os **arquivos
YAML reais** enviados na conversa como fixture — não simplificados:
sensor 1-Wire compartilhando pino, atuador com `failsafe_value`/
`is_risk`, vasilhame com múltiplas etapas e bombas). 1 teste de menu
ajustado (novo filho direto de Controle de Mostura). Suíte completa
do projeto: **601/601 passando**. Sem migration — nenhuma coluna
nova, só dados.

## Dashboard de Brassagem — editor visual (arrastar, redimensionar, botão direito) + SVG real: CONCLUÍDO

Pesquisado antes de desenhar (a pedido): **CraftBeerPi4** (referência
principal — modo edição trava/destrava, painel de propriedades, SVG
substituível pro vasilhame, tubulação com cor/espessura configuráveis)
e **BrewUno** (mais fechado/hardware-focado, sem documentação de UI
própria relevante). Plano baseado no padrão do CraftBeerPi4, confirmado
em conversa antes de implementar.

### O que foi resolvido

- **Nenhuma coluna nova** — tudo cabe no que já existia
  (`x`/`y`/`width`/`height`/`rotation` do widget, `config_json` livre,
  `plant.plant_schema_json`). Sem migration.
- **Modo Edição** (trava/destrava, como CraftBeerPi) — fora dele, a
  tela continua só leitura+acionamento (como já era). Dentro:
  - **Arrastar** (mousedown+mousemove+mouseup) — salva a posição ao
    soltar.
  - **Redimensionar** (alça no canto inferior direito) — nunca deixa
    colapsar abaixo de 40px (proteção contra drag descuidado).
  - **Botão direito** → menu de contexto: **Configurações** (modal —
    legenda, e campos específicos do tipo: formato do vasilhame,
    papel do sensor de nível, mínimo/máximo do gauge, casas decimais,
    sessão/janela do gráfico, e o **comportamento de acionamento
    manual** — `confirm_before_actuate`, pede confirmação no
    `confirm()` antes de acionar um atuador) e **Remover** (soft-delete).
  - **+ Adicionar Widget** — cria um widget novo (qualquer um dos 6
    tipos) direto pela tela, sem precisar ir na tela de CRUD cru.
  - **Editar Tubulação** — modal com as conexões da Planta
    (de/para/atuador de fluxo/cor/espessura), sobrescreve
    `plant_schema_json` inteiro (lista pequena, não vale granularizar).
- **SVG de verdade pro vasilhame** — troca o `<div>` com gradiente por
  um `<svg>` com silhueta real (caldeira com alças, ou fermentador com
  fundo cônico — escolha por `config_json.svg_shape`), nível de
  líquido animado via `clipPath` (`transition: y .6s`), cor do líquido
  reagindo à temperatura (azul <35°C, laranja 35–75°C, vermelho >75°C).
  Nível decorativo fixo (55%) quando não há `fill_role_key`
  configurado; usa o sensor de verdade quando configurado.

### Peças novas (service + controller)

`services/dashboard_runtime_service.py`: `update_widget_geometry()`,
`update_widget_config()` (merge, nunca substitui `config_json`
inteiro), `create_widget_from_editor()`, `remove_widget_from_editor()`
(soft-delete), `update_plant_connections()`. `controller/
dashboard_runtime.py`: 5 rotas novas (`geometry`/`config`/`widgets`
POST/`widgets/.../delete`/`plant-connections`).

**Achado real corrigido no caminho**: `db` (Flask-SQLAlchemy) nunca
tinha sido importado em `dashboard_runtime_service.py` — as funções
anteriores só liam (via `.query`), não precisavam. As funções novas
gravam (`db.session.commit()`) e quebravam com `NameError` até o
import ser adicionado — pego pelo próprio teste, corrigido antes de
fechar.

Testes: 10 casos novos em `tests/test_dashboard_runtime.py` (geometria
com proteção de colapso, config com merge, criar/remover widget,
tubulação com cor/espessura, validação sem planta, SVG presente na
tela). Suíte completa do projeto: **611/611 passando**. Sem migration.

### Limitações conhecidas desta rodada (escopo, não bug)

- Sem WebSocket/tempo real — igual antes, polling a cada 3s.
- Sem desfazer/refazer (undo/redo) no editor.
- Rotação de widget (`rotation`) tem endpoint pronto, mas sem
  controle visual no editor ainda (só arrastar/redimensionar).

## Editor do Dashboard: botões "Configurações"/"Widget"/"Tubulação" não funcionavam — CORRIGIDO

Bug real reportado: botão direito → "Configurações" não fazia nada;
botões "+ Widget" e "Editar Tubulação" também não respondiam.

**Causa raiz**: o `<script>` da tela estava dentro de `{% block
content %}`, que renderiza **antes** de `bootstrap.bundle.min.js`
carregar (esse `<script>` só entra depois, e `{% block extra_js %}` —
o lugar certo pra script de página, usado por toda outra tela do
projeto — só entra ainda depois disso, logo antes de `</body>`).
`new bootstrap.Modal(...)` estourava `ReferenceError: bootstrap is
not defined` logo no início da execução do script, e como não havia
try/catch, **todo o código depois desse ponto nunca rodava** —
inclusive os `addEventListener` dos botões de Configurações/Adicionar
Widget/Tubulação, todos declarados depois da instanciação dos modais.
Corrigido movendo o bloco inteiro de `<script>`/`<style>` pra dentro
de `{% block extra_js %}`.

**Achado adicional no caminho**: o widget tipo `toggle` (botão liga/
desliga dedicado, diferente dos badges de atuador dentro do
vasilhame) nunca teve clique conectado a nada — só os badges do
vasilhame funcionavam. Corrigido com um listener delegado.

### Acionamento manual configurável (pedido — referência CraftBeerPi4)

Novo campo no modal de Configurações — **"Permitir acionamento
manual"** (`config_json.manual_control_enabled`, default `true` —
preserva o comportamento anterior). Quando desligado: o widget/badge
de atuador vira só leitura (não clicável, ícone de cadeado, tooltip
explicando) — protege um atuador que já está sob controle da
automação de ser acionado sem querer pela tela. Aplica-se a
`vessel` (por role de atuador) e `toggle`.

Testes: 3 casos novos (`tests/test_dashboard_runtime.py`) — um deles
é **teste de regressão específico pro bug de ordem de script**
(confirma que o `<script>` da dashboard sempre vem depois do
`bootstrap.bundle.min.js` no HTML renderizado, pra isso nunca mais
quebrar silenciosamente). Suíte completa do projeto: **614/614
passando**. Sem migration.

### Pendência registrada nesta conversa (fora de escopo desta rodada)

"Melhorar o fluxo de navegação entre as telas e selecionar receita
para o mash" — pedido em aberto, ainda não desenhado. Precisa de
conversa própria antes de implementar (qual fluxo exato: seleção de
receita ao criar uma Sessão de Brassagem? navegação
Dashboard↔Sessões↔Receitas?).

## Editor de Tubulação: "Atuador de fluxo" agora é select (não texto livre): CONCLUÍDO

Achado real: o campo digitava o nome da Function na mão, sem
nenhuma validação — mesmo padrão de referência fraca já resolvido
antes (skill 11) pra outros campos, só que este ficou de fora quando
o editor de tubulação foi construído. Corrigido: `dashboard_runtime.
view()` carrega as `DeviceFunction` com `category="actuator"` e passa
pro template; o editor de tubulação monta um `<select>` com elas.
Bônus: o valor salvo agora é pré-preenchido corretamente ao reabrir
o editor (antes não era, mesmo sendo texto livre).

Teste novo: 1 caso. Suíte completa do projeto: **615/615 passando**.
Sem migration.

## Timeline única de receita (RecipeStep) + alertas + "Importar Receita para Brassar": CONCLUÍDO

Arquitetura desenhada em conversa (várias rodadas de confirmação) —
substitui `MashStep` por `RecipeStep`, unificando Mostura + Fervura +
Alerta numa timeline só (Fermentação fica de fora por decisão —
processo separado, não usa caldeira).

### Modelo novo: `RecipeStep`

`step_type` (`mash`/`boil`/`fervura` — fervura não tinha modelo
próprio antes desta conversa) + `trigger_minutes_remaining`/
`parent_step_id` (só `alert` — equivalente ao `hop_alarms` do
tesseract-device-bridge, "dispara X min antes do fim da etapa-pai")
+ `source` (`manual`/`auto_hop`) + `source_recipe_ingredient_id`.

### Lupulagem cria alerta sozinha ("toda lupulagem cria alertas")

`recipe_timeline_service.sync_hop_alerts()` varre `RecipeIngredient`
(`tipo_ingrediente="lupulo"`, `etapa="fervura"`,
`tempo_adicao_min` preenchido — reaproveita campo que já existia,
mesmo significado do `hop_alarms.minutes_remaining` do bridge) e
cria/atualiza o `RecipeStep` de alerta correspondente sozinho.
Idempotente por `source_recipe_ingredient_id` — nunca duplica, nunca
toca em alerta manual, remove (soft-delete) se o ingrediente sumiu.

### Migration com migração de dado real (validada com dado de verdade)

`f7a4c916e830`: cria `recipe_step`, **copia os dados de `mash_step`**
(`step_type="mash"`) e remove a tabela antiga — testado de verdade
com registro real inserido antes (não só schema vazio), upgrade e
downgrade confirmados preservando o dado exato. `BrewSessionStep`
ganha `trigger_at_seconds` (tempo absoluto pro disparo) e
`alarm_fired` (evita disparar 2x).

### Fluxo "Importar Receita para Brassar"

Escolhe uma `MashRecipe` já cadastrada → timeline sincronizada
automaticamente (lúpulo) e editável (arrastar pra reordenar, editar
via modal simples, adicionar/remover etapa) → **Gerar Sessão**:
copia (snapshot, nunca referência viva — mesmo padrão de
`RecipeHistory`) cada `RecipeStep` pra `BrewSessionStep`, calculando
`trigger_at_seconds` de cada alerta a partir do tempo acumulado das
etapas de processo anteriores. `status` escolhido na hora
(`draft`=temporário/revisável, `active`=real/começa agora) —
reaproveita o campo que já existia em `BrewSession`, sem coluna nova.

### Disparo automático + ajuste vira histórico

`check_and_fire_alerts()` reaproveita o polling de 3s que o Dashboard
já fazia — a cada snapshot, verifica `BrewSessionStep` tipo alerta
vencido (`trigger_at_seconds` <= tempo decorrido, `alarm_fired=False`)
e gera o `BrewSessionAlarm` sozinho. `adjust_session_step()` — editar
um valor de passo durante a sessão ativa grava em `BrewSessionLog`
(`source="user"`, já existia o conceito, só não era usado ainda) em
vez de só sobrescrever — dá o histórico de ajuste do lote pedido em
conversa, sem tabela nova.

### Limpeza — MashStep removido de vez (decisão confirmada em conversa)

Model + CRUD gerado (`mash_steps_routes.py`/`controller/mash_steps.py`/
`mash_step_service.py`/templates) removidos. Achado real no caminho:
`feature_brew_father/services/sync_service.py` importava `MashStep`
diretamente (cross-Feature dentro do mesmo Addon, permitido pela
skill 02) — corrigido pra `RecipeStep(step_type="mash", ...)`, senão
o boot inteiro quebrava (`ModuleNotFoundError`). `mash_recipes/
detail.html` (seção "Rampas de Mostura") atualizado pra mostrar a
timeline completa (mostura+fervura+alerta) com link direto pra tela
nova. Menu: `TX_MASH_STEPS` → `TX_RECIPE_STEPS` (CRUD cru) +
`TX_RECIPE_TIMELINE` novo (a tela de verdade).

Testes: `tests/test_recipe_timeline.py` (25 casos — sync de lúpulo em
todas as variações, CRUD/reorder, geração de sessão com cálculo de
`trigger_at_seconds` conferido matematicamente, disparo automático
idempotente, ajuste vira log, rotas web). 1 teste em
`test_feature_brew_father.py` corrigido (`MashStep` → `RecipeStep`).
1 teste de menu ajustado. Suíte completa do projeto: **639/639
passando**. Migration validada com **dado real** migrado (não só
schema vazio) + downgrade restaurando o dado exato + cenário de banco
do zero absoluto (14 migrations em sequência, sem erro).

## Navegação entre Dashboard, Timeline de Receita e Sessão: CONCLUÍDO

Dois relatos reais depois de aplicar a timeline: "não consigo desenhar
a tubulação" e "não encontrei onde carregar a receita" — nenhum dos
dois era bug de código, os dois eram falta de caminho óbvio na tela.

**Tubulação**: o botão só aparece se o Layout tiver uma Planta
associada (`plant_id`) — layouts criados antes dessa coluna existir
ficam sem isso. Adicionado um aviso visível no próprio Dashboard
quando `layout.plant_id` está vazio, com link direto pra
Configurações do layout (onde `plant_id` já é um combo de busca,
skill 11).

**"Onde carregar a receita"**: a tela existia (`TX_RECIPE_TIMELINE`),
mas ficava 4 níveis fundo no menu (BrewStation → Controle de Mostura
→ Receitas → "Importar Receita para Brassar") — fácil de nunca achar.
Adicionado link direto **no topo do próprio Dashboard** (não depende
mais de navegar a árvore do menu), e navegação de volta nos dois
sentidos: Timeline ↔ Dashboard, Sessão gerada ↔ Dashboard.

Testes: 3 casos novos (link presente, aviso aparece sem Planta, aviso
some com Planta). Suíte completa do projeto: **643/643 passando**.
Sem migration — só templates.

## Widget de alarmes: timeline (disparado + agendado), não só log reativo: CONCLUÍDO

Achado real relatado: "ao importar sessão de receita ainda não
apareceu nos alertas". Causa: o widget `alarm_list` só mostrava
`BrewSessionAlarm` (já disparado) — uma Sessão recém-gerada como
"Rascunho" (opção padrão do formulário, sem `started_at`) ou uma
Sessão "Ativa" mas ainda longe do tempo do alerta não mostrava **nada**,
mesmo com a timeline certa por trás. Parecia bug, era ausência da
parte "agendado/próximo" — o widget só era reativo, não "dashboard"
de verdade.

**Corrigido**: `_get_active_alarms()` agora devolve duas listas —
`fired` (`BrewSessionAlarm`, como antes) e `upcoming`
(`BrewSessionStep` tipo `alert` ainda não disparado):
- Sessão **rascunho** (sem `started_at`): mostra os alertas agendados
  com rótulo "agendado" (sem contagem regressiva — o relógio ainda
  não está rodando).
- Sessão **ativa**: contagem regressiva de verdade
  (`trigger_at_seconds - segundos decorridos`).
- Sem sessão "active", cai pro rascunho mais recente da planta (não
  fica esperando alguém "ativar" pra mostrar alguma coisa).

Testes: 5 casos novos (`tests/test_dashboard_runtime.py`) — rascunho
mostra agendado sem contagem, ativa mostra contagem regressiva
correta, alerta já disparado não aparece em `upcoming` de novo, sem
sessão nenhuma devolve listas vazias sem erro, JS renderiza os dois
grupos. Suíte completa do projeto: **648/648 passando**. Sem
migration — só lógica de leitura.

### Pendências registradas nesta conversa (fora de escopo desta rodada — "vamos focar no dashboard")

- Auditoria de campos que ainda são `<input>` de id cru em vez de
  combo de busca (skill 11) em outras telas do addon (não só as já
  cobertas: Dashboard/device_manager).
- Consolidar as telas de Planta (Vasilhames, Mapeamentos, etc.) numa
  página só com abas — a maioria dos cervejeiros caseiros só tem 1
  Planta, hoje isso fica espalhado em várias telas de CRUD separadas.
- Carga inicial/onboarding pra usuário novo do sistema (fora do fluxo
  já existente de importar `devices.yml`/`recipe.yml` do bridge).

## Ajustes reportados após o Card de Etapa (self-loop, rampa, selects): CONCLUÍDO

Três achados reais reportados em uso, mais um quarto encontrado na
investigação:

**1. `BrewSession.status` (e campos parecidos) sem select box.** Causa
raiz: `@choices` (annotations) é só pra filtro de lista (`SELECT
DISTINCT`), nunca existiu suporte do CrudGen a campo de opção FIXA
(enum) virar `<select>` — em nenhuma tela, de nenhuma entidade. Só
`status` foi corrigido nesta rodada (`brew_sessions/detail.html`,
select manual com os 5 valores do model). **Registrado como
prioridade alta**: o CrudGen precisa ganhar uma annotation nova
(`@enum_field` ou similar) que gere `<select>` tanto pra criação
quanto edição, aplicada a todo campo de opção fixa do sistema
(`BrewSessionStep.status`, `RecipeStep.step_type`, `DeviceActor.
actor_type`, etc.) — e, junto disso, garantir que toda referência
fraca (`@weak_ref`, skill 11) também sempre vire combo, nunca `<input>`
de id cru. Sem isso não há validação de dado na entrada — hoje dá pra
digitar qualquer string num campo de status ou colar um id que não
existe numa referência fraca. Marcado pelo usuário como a maior falha
do sistema hoje.

**2. Tubulação self-loop (ex.: recirculação mostura → mostura) não
dava pra desenhar.** Causa raiz: âncora padrão (centro-base →
centro-topo) desenha a linha inteira **atrás do próprio widget**
(z-index do widget é maior que o da camada SVG) — ficava inclicável,
sem jeito de criar o primeiro waypoint. Corrigido: (a) camada SVG
levanta o z-index acima dos widgets enquanto uma tubulação está
selecionada; (b) conexão nova com origem == destino já nasce com uma
alcinha padrão pra fora do vasilhame (âncoras nas laterais + 1
waypoint automático), em vez de reta escondida.

**3. Sem mudança visual / sem rampa no Card de Etapa.** Dois problemas:
(a) `step_card` é widget novo, não aparece sozinho em dashboard já
existente — precisa ser adicionado via "+ Widget" (não é bug, só
onboarding). (b) achado real mais sério: `duration_seconds` só
gravava o hold, `ramp_time_min` da receita nunca virava dado na
sessão — mesmo com o widget, não tinha o que mostrar. Corrigido:
`BrewSessionStep.ramp_seconds` novo (migration com guard,
`generate_session_from_recipe`/`resync_session_steps` passam a
gravar), `get_step_card_data()` calcula fase (rampa vs. hold) e
progresso de cada uma separado. UI: duas barras (rampa some quando
termina, hold assume — decisão da conversa), contagem regressiva
mm:ss, e botão "Voltar" novo (`go_back_step()`) — inspirado num
painel de referência anexado na conversa (prev/next sempre visíveis
durante a operação). Reativa a etapa anterior reiniciando o timer
dela; não reconstrói o tempo exato já gasto antes.

**4. Achado extra na investigação**: modal "+ Widget" do editor visual
tinha "Nome da Function do dispositivo" como texto livre, mesmo
`device_function_name` já sendo `@weak_ref` no model (a tela de CRUD
separada `/dashboard-widgets/<id>` já usa combo corretamente). Só o
formulário próprio do editor visual (não gerado pelo CrudGen) estava
sem — virou `<select>` alimentado por `DeviceFunction`.

Testes: suíte completa rodada após as mudanças. Migration
`ramp_seconds` validada com dado real (upgrade → insere → downgrade →
confirma sobrevivência → upgrade → confirma volta), mesmo processo já
usado pra `source_recipe_step_id`.
