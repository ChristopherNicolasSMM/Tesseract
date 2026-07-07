# 06 — Manutenção e Expansão (Sistema)

## Como adicionar um campo a um model existente

Checklist completo — **arquivos que precisam de atenção**, não só o
model (a parte que mais causa esquecimento é o "resto" além do
`model/`, já que o CrudGen só regenera automaticamente o que ele
próprio gerou):

1. **`model/<entidade>.py`** (Addon/Feature) ou `model/core/*.py`
   (Core) — adicionar a coluna. Se o campo é obrigatório, também
   anotar `@required("<campo>", message="...")` no topo da classe
   (skill 03 — mensagem de validação do formulário gerado).
2. **Regenerar via CrudGen** (opcional — só necessário se quiser que
   o CrudGen re-detecte a anotação nova para telas/rotas; a maioria
   das telas geradas neste projeto já é genérica o bastante — lista
   de campos via `__table__.columns` em runtime — para funcionar sem
   regenerar, ver nota "Quando NÃO é preciso regenerar" abaixo):
   ```
   python run.py generate --model <caminho/model.py> --addon <nome> [--feature <nome>] --overwrite
   ```
   `*_hooks.py` **nunca** é sobrescrito, mesmo com `--overwrite`.
3. **Migration** (sempre que a tabela já existe em algum banco com
   dado real — ver bloco de migration mais abaixo). Ambiente novo
   (`db.create_all()` do zero) não precisa disso.
4. **`to_dict()` do model**, se a entidade tiver um método manual
   (nem todo model tem — ver o próprio arquivo) — campo novo não
   aparece em resposta de API/JSON sem isso.
5. **Ripple effect nos testes**: toda instanciação direta do model em
   `tests/*.py` (`Entidade(...)` fora de fixture) que passar a violar
   uma constraint nova (`nullable=False`, `unique=True`) precisa ser
   atualizada — grep por `NomeDaClasse(` em `tests/` antes de
   considerar a mudança concluída, não só rodar a suíte e esperar
   falha apontar o caminho.
6. **Qualquer service que já construía a entidade manualmente** (fora
   do fluxo genérico de formulário) — ex.: um `*_autocreate_service.py`
   ou hook de controller que faz `Entidade(campo=...)` direto — precisa
   decidir um valor (ou resolver via lookup/seed) para o campo novo,
   senão quebra em runtime assim que o campo for `nullable=False`.
7. **Docs técnicos**: `docs/technical/04-modelo-de-dados.md` da escala
   certa (Addon/Feature) — adicionar a coluna no diagrama `erDiagram`
   e, se o campo tiver alguma regra de negócio não óbvia, uma linha na
   tabela de descrição logo abaixo do diagrama.
8. **Checklist de manifesto** (skill 03, item de `i18n/pt_BR.json`) —
   só relevante se o campo novo tiver `@label(...)` explícito e o
   CrudGen for rodado com `--overwrite`; nesse caso confirmar que a
   chave nova foi extraída para o arquivo de tradução.

### Quando NÃO é preciso regenerar

Os módulos deste projeto que seguem o padrão "controller genérico"
(lista de campos editáveis derivada de `Entidade.__table__.columns`
em runtime, ver `addons/addon_estoque/root/controller/materials.py`
como referência) **não precisam** do passo 2 acima — a tela de
listagem/formulário já reflete a coluna nova automaticamente no
próximo boot, sem regenerar nada. Isso cobre a maioria dos CRUDs
simples deste projeto (Material e os lookups de `addon_estoque`, por
exemplo). Regenerar continua sendo necessário só se o controller for
do tipo mais antigo (campos hardcoded a partir da anotação, não
introspecção de `__table__`) — checar o controller da entidade
específica antes de assumir um caminho ou outro.

### Migration (quando a tabela já existe com dado real)

```
python run.py db migrate -m "descrição da mudança"
python run.py db upgrade
```

`db.create_all()` (chamado todo boot) nunca faz `ALTER TABLE` — só
cria tabela nova. Esquecer este passo é a causa nº 1 de
`OperationalError: no such column` em produção. Atenção: coluna com
`default=` no SQLAlchemy aplica o valor padrão no INSERT mesmo se
`None` for passado explicitamente no construtor — só fica `None`
de fato após um UPDATE separado (comportamento do SQLAlchemy, não
bug do Tesseract).

Se o campo novo for `nullable=False` numa tabela com linhas
existentes, a migration precisa de um valor de backfill explícito
(não dá pra rodar `upgrade` direto com `NOT NULL` sem default contra
dado existente) — decidir esse valor é uma decisão de arquitetura
antes de escrever a migration, não um detalhe técnico a resolver na
hora (ver exemplo real: a ampliação de `Material` em `addon_estoque`
resolveu isso com registros seed — "A definir"/"Insumo" — em vez de
valor fixo hardcoded; ver
`addons/addon_estoque/docs/technical/04-modelo-de-dados.md`).

## Como criar uma nova entidade (do zero) via CrudGen

Diferente de adicionar campo a algo que já existe — aqui o objetivo é
uma tabela nova inteira, com tela de listagem/formulário/API geradas
automaticamente. Passo a passo real (mesmo fluxo usado para criar os
lookups `Fabricante`/`Origem`/`TipoProduto`/`Categoria` de
`addon_estoque` nesta sessão — ver
`addons/addon_estoque/docs/technical/04-modelo-de-dados.md`):

1. **Escrever o model anotado** em `addons/addon_x/root/model/<entidade>.py`
   (núcleo do Addon) ou `.../features/feature_y/model/<entidade>.py`
   (dentro de uma Feature). Mínimo obrigatório (skill 02): `id`
   (Integer PK), `is_deleted`/`deleted_at`, `created_at`/`updated_at`.
   Anotações mínimas (skill 00/03): `@label(...)`, `@plural(...)`, e
   `@required(...)`/`@max_length(...)` para cada campo com regra.
   `__tablename__` é o nome **curto**, sem prefixo — o CrudGen aplica
   o prefixo tri-nível (skill 02) no registro, não no arquivo.
2. **Rodar o generate**:
   ```
   python run.py generate --model <caminho/model.py> --addon <nome> [--feature <nome>]
   ```
   Isso cria, a partir do model: `services/<entidade>_service.py` +
   `_service_hooks.py`, `controller/<entidades>.py` + `_hooks.py`,
   `api/routes/<entidades>_routes.py` + `_routes_hooks.py`,
   `templates/<entidades>/manage.html` + `detail.html`. Os `_hooks.py`
   nascem vazios/mínimos — é onde customização futura entra sem tocar
   no que foi gerado.
3. **Registrar no `addon.py`/`feature.py`**: adicionar a classe em
   `register_models()` (lista de models) e os blueprints novos
   (`<entidade>_bp`, `<entidade>_api_bp`) em `register_routes()`. Sem
   este passo o CrudGen gera os arquivos mas o módulo não sobe as
   rotas nem cria a tabela no boot.
4. **Transação de menu (opcional, mas usual)**: adicionar uma entrada
   em `get_transactions()` (ver seção "Como adicionar uma transação
   navegável" acima) apontando pra rota gerada, se a entidade deve
   aparecer no menu/launcher.
5. **Rodar a suíte de testes** e adicionar cobertura nova pra entidade
   (mínimo: criação, unicidade de campo `unique=True` se houver, e
   qualquer regra de negócio específica).
6. **Docs técnicos**: adicionar a entidade no diagrama `erDiagram` de
   `docs/technical/04-modelo-de-dados.md` da escala certa, e uma linha
   na tabela de descrição de tabelas.

### Lookup simples vs. entidade completa

Para lookups simples (só `id` + `nome` único, sem regra de negócio
própria — ex.: `Fabricante`/`Origem`/`TipoProduto`/`Categoria` de
`addon_estoque`), os passos acima bastam sem nenhuma customização de
`_hooks.py`. Para entidade com regra de negócio real (cálculo,
validação cross-campo, efeito colateral em outra tabela), a lógica
entra no `_service_hooks.py`/`_routes_hooks.py` gerados no passo 2 —
nunca no arquivo gerado, que pode ser sobrescrito num `--overwrite`
futuro.

## Como adicionar uma nova Feature a um Addon existente

1. `addons/addon_x/features/feature_y/feature.json` com
   `table_prefix_suffix` único **em todo o Addon** (não só na Feature
   — nomes curtos competem no mesmo namespace antes do prefixo).
2. `feature.py` com `__module__ = "FeatureY"`, herdando `FeatureBase`.
3. Implementar `register_models()` e, se quiser navegação,
   `get_transactions()` (ver skill 00, "Transação").
4. Adicionar a Feature em `AddonX.get_features()`.
5. Escrever o model anotado, rodar `generate`.
6. Preencher `docs/technical/01-*.md` e `docs/manual/01-*.md`.

## Como adicionar uma transação navegável (menu)

Duas formas:
- **Pelo código**: implementar `get_transactions()` em qualquer
  `ModuleBase`/`FeatureBase` — sincronizado automaticamente pelo
  `ModuleManager` no boot. Editar label/rota depois só pelo código —
  a tela sobrescreve a cada boot.
- **Pela tela**: `/admin/transactions/` → "Nova transação manual" —
  totalmente editável e excluível depois, nunca sobrescrita por
  nenhum código.

## Como anexar uma regra de validação a um campo

`/admin/field-rules/` → escolher `entity_key` (o `plural` da entidade,
mesmo valor usado nas rotas geradas) + `field_name` + regra do
catálogo (grupo Validação — os outros dois grupos, Visibilidade e
Cálculo, ainda não têm motor JS, ver seção abaixo). Funciona tanto em
telas geradas pelo CrudGen quanto em `textbox`es do Designer.

## Como montar uma página visual sem usar o CrudGen

`/admin/designer/` → criar página → arrastar componentes da paleta →
posicionar/redimensionar (mouse) → editar propriedades no painel
lateral → publicar. Útil para dashboards e telas que não mapeiam 1:1
pra uma entidade de banco. Tipos de componente disponíveis hoje:
`heading`, `label`, `textbox`, `button`, `image`, `divider`.

## Como expandir o motor de regras (Visibilidade/Cálculo)

`core/rules_catalog.py` já tem o catálogo completo dos 3 grupos
(Validação/Visibilidade/Cálculo), mas `static/js/rule_engine.js` só
implementa as funções de Validação. Para conectar Visibilidade
(`visibleIf`/`hiddenIf`/`enabledIf`) ou Cálculo
(`calculate`/`sum`/`linkProgress`/`statusMap`/`format`):

1. Implementar a função correspondente em `rule_engine.js` (mesmo
   padrão das funções de Validação: recebe `el, params`, mas essas
   precisam também resolver `source_id`/`target_id` para outros
   elementos do DOM — usar `document.getElementById('comp-' + id)`,
   já que o Designer usa esse padrão de id).
2. Não precisa de nenhuma mudança de schema — `DesignerComponent.rules`
   já aceita qualquer `js_function` do catálogo, só ignora
   silenciosamente as que o motor não implementa ainda.

## Como integrar um servidor OData externo

`/admin/odata/` → criar conexão → testar → navegar dados. Para ir além
do navegador read-only (gerar uma tela editável a partir da metadata),
seria necessário portar `screen_generator.py` (DEVStationFlask) —
agora possível, já que o Designer (`DesignerPage`/`DesignerComponent`)
existe; não foi feito ainda porque não havia pedido real até esta
versão.

## Como depreciar/remover uma Feature ou Addon sem deixar tabela órfã

Ainda não há rotina automatizada. Hoje significa:
1. Migration manual de `DROP TABLE` (`flask db revision` + editar à
   mão, já que não há autogenerate seguro pra remoção de dados).
2. Remover a pasta do Addon/Feature do disco.
3. Remover a entrada de `tesseract_module_state` (se existir).
4. Permissions/Transactions associadas ficam órfãs — sem limpeza
   automática ainda (Transaction pode ser desativada manualmente pela
   tela; Permission nunca tem UI de remoção, por design).

## Pontos de extensão conhecidos

- **`EventBus`** (`core/event_bus.py`) — pub/sub em memória, síncrono,
  sem persistência. É o **único canal permitido** de comunicação
  entre Addons diferentes (skill 02 — nunca FK/ORM direto cross-Addon).
  Sempre ativo (sem gate de opt-in, ao contrário do cliente MQTT do
  `addon_device_manager` ou do scheduler de Tasks — ver
  `core/app_factory.py`), porque não envolve rede nem broker externo,
  só um dicionário `{evento: [handlers]}` dentro do mesmo processo
  Python. Um handler com erro nunca derruba o publicador nem os
  demais handlers do mesmo evento (try/except por handler).

  **Convenção de nome de evento** (skill 00): namespace por ponto,
  presente do indicativo no domínio + passado na ação — ex.
  `device_manager.actor.value_changed`.

  **Eventos reais em uso hoje** (todo uso novo deve ser adicionado a
  esta tabela):

  | Evento | Publicado por | Assinado por | Propósito |
  |---|---|---|---|
  | `core.module.activated` | `core/module_manager.py`, a cada Addon/Feature ativado | `register_example_listener()` (`core/event_bus.py`) | Listener de demonstração desde a Fase 1 — prova que a infraestrutura funciona; nunca foi removido, sem lógica de negócio real |
  | `device_manager.actor.value_changed` | `addons/addon_device_manager/root/services/device_service.py`, a cada `set_value()`/`update_from_mqtt()` | `addons/addon_brewstation/features/feature_mash_control/services/automation_engine.py` | Dispara o motor de automação reativo (`AutomationRule` sensor→condição→ação) — ver `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`, seção 6, para o histórico completo (inclui uma correção real: a primeira versão desse motor criou um mecanismo de callback paralelo por engano, sem checar que o EventBus já resolvia) |

  **Antes de criar um pub/sub novo, callback global, ou registro em
  memória para comunicação cross-Addon**: verificar primeiro se
  `event_bus.publish()`/`.subscribe()` já resolve — é a regra de ouro
  registrada após o incidente acima.
- **Hooks** (`*_hooks.py`) — customização sem editar código gerado.
- **`core/versioning.py`/`snapshot_service.py`** — qualquer escrita de
  arquivo pode ser versionada, não só pelo CrudGen.
- **`get_transactions()`** — qualquer módulo contribui itens de menu.
- **Migrations (Alembic)** — `migrations/` na raiz, baseline já
  stampada; só precisa de `db migrate`/`db upgrade` daqui pra frente.
- **`core/rules_catalog.py`** — catálogo de regras pronto para mais
  funções JS (Visibilidade/Cálculo).
- **`DesignerComponent.rules`** — qualquer regra do catálogo pode ser
  anexada, mesmo as ainda sem motor (fica catalogada, sem efeito).
- **`@display_field`/`@weak_ref`** (skill nova —
  `docs/skills/11-referencia-fraca-e-display-field.md`) — anotações
  pra resolver campo de referência fraca (skill 02, ex.: `material_id`
  sem FK real) num nome legível na tela de listagem/detalhe gerada e
  num combo de busca (`/api/options/<table>`), sem tocar schema.
  `@display_field` no model alvo (o que É referenciado), `@weak_ref`
  no model que TEM a referência — `core/crudgen/generator.py` resolve
  automaticamente a partir das duas anotações, para qualquer entidade
  nova, não só as 6 identificadas na revisão que motivou a skill.

## Erros conhecidos e como resolver

| Erro | Causa | Solução |
|---|---|---|
| `OperationalError: no such column` | Coluna nova num model com tabela já existente, sem migration | `python run.py db migrate && db upgrade` |
| `Table 'X' is already defined` | Dois models (testes ou Features diferentes) usando o mesmo `__tablename__` curto | Renomear um deles — nome curto deve ser único em todo o Addon |
| `Foreign key... could not find table` | FK cross-Feature resolvida antes de todos os models serem importados | Não deveria mais ocorrer — `ModuleManager` importa tudo antes de prefixar; se ocorrer, é regressão nesse mecanismo |
| `TemplateNotFound` numa tela de Addon | `ChoiceLoader` não incluiu a pasta `templates/` daquela Feature | Confirmar que `apply_template_loader()` roda depois de `discover_and_register_addons()` |
| Tema escuro não aplica nenhuma regra visual | Classe/atributo no `<body>`/`<html>` não bate com o seletor real do `style_dark.css` | Confirmar `html[data-theme="dark"]` — é a convenção dominante do arquivo (129 ocorrências) |
| Toggle do sidebar não funciona | `static/js/web.js` não incluído na página | Confirmar `<script src=".../js/web.js">` em `base.html` |
| Edição de uma Transaction não persiste | Transação vem do código (`is_standard`/`source_module` de Addon) — `sync_transaction()` sobrescreve a cada boot | Editar o `get_transactions()`/`transactions_catalog.py` correspondente, não a tela |
