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
Cálculo, ainda não têm motor JS, ver seção abaixo). Funciona em telas
geradas pelo CrudGen, que já renderizam `data-rules` a partir da regra
cadastrada; numa página customizada escrita à mão, o mesmo campo só
valida se o `<input>` levar `data-rules` manualmente (`rule_engine.js`
não sabe de onde veio o HTML).

## Como criar uma página customizada (Fase 12 — sem canvas)

`/admin/designer/` → criar página → editor de HTML (`content_html`) →
publicar. Não existe mais canvas/paleta/árvore de componentes — o
construtor visual foi removido (skill 16, cabeçalho, tem o porquê).
Útil para dashboards e telas que não mapeiam 1:1 pra uma entidade de
banco.

Ponto de partida: `/freestyle/` (Fase 13, skill 18) — telas de
referência **vivas**, testadas, cobrindo esqueleto mínimo, abas,
consumo de dado e galeria de componentes do NiceAdmin. Copie o HTML de
lá; não comece do zero.

## Como uma página customizada chama uma Ação de Dado (Fase 10)

Não existe mais painel de evento no editor — a chamada é JavaScript
direto na página, contra o endpoint server-side:

```js
fetch('/admin/designer/data-action/<id>/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ params: { '$filter': "status eq 'ativo'" } }),
}).then(r => r.json()).then(dado => { /* dado.result.value */ });
```

`static/js/freestyle/freestyle-tesseract-data.js` (`window.
TesseractData`) encapsula isso — `TesseractData.acaoDeDado(id, corpo)`
— junto dos outros dois caminhos de dado (API REST do CrudGen,
`/api/options/`) e do `esc()` contra XSS. Copie o arquivo em vez de
reescrever `fetch`/tratamento de erro do zero. Contratos completos e
os 7 erros comuns estão na skill 17.

**Regra de ouro desta peça**: toda Ação que toca dado/API roda
*sempre* no servidor (`POST /admin/designer/data-action/<id>/execute`)
— nunca client-side, porque a `ODataConnection` por trás pode
envolver credencial (`auth_value`). A página só manda qual
`DesignerDataAction` disparar e, se for `update`, a `key`/`payload`.

## Como expor uma nova entidade no provedor OData local (Fase 10)

Adicionar `@odata_expose("<entity_name>", permission_required="<opcional>")`
no model (`annotations/__init__.py`, mesmo padrão de `@permission`).
Opt-in por entidade, de propósito — sem a anotação, a entidade nunca
aparece em `/api/odata-provider/$metadata.json`, mesmo com o Addon
ativo (decisão registrada em BACKLOG.md, Fase 10). `entity_name` vira
o nome usado numa `DesignerDataAction.entity_name` — não precisa ser
igual ao `__tablename__`. Metadata é montada ao vivo
(`core/odata_provider/metadata.py`), sem cache — qualquer mudança de
model aparece no próximo request.

## Como substituir uma tela do CrudGen por uma página do Designer (Fase 10)

Editor da `DesignerPage` → painel "Configurações da página" →
`replaces_entity_key` (o **plural** da entidade — mesmo formato de
`FieldRule.entity_key`, ex. `yeast_strains`, nunca o singular) +
`replaces_view=manage` + marcar "Substituir no menu" → Salvar/
Publicar. `core/designer_menu_override.py` troca só o item de
**menu** (`Transaction.route`); a rota original do CrudGen nunca é
removida, continua acessível direto pra debug. Reverter (desmarcar o
checkbox, despublicar, ou apagar a página) restaura o item de menu
original sozinho — o resolver sempre reconstrói do zero a partir do
catálogo de código antes de reaplicar overrides, nunca "lembra"
estado antigo.

`replaces_view=detail` só existe no schema por enquanto — uma tela de
detalhe nunca vira item de menu por conta própria (é acessada por
link dentro do "manage"), então não há Transaction pra trocar; fica
pronta pra quando um mecanismo de override de link "ver detalhe"
existir.

## Como expandir o motor de regras (Visibilidade/Cálculo)

`core/rules_catalog.py` já tem o catálogo completo dos 3 grupos
(Validação/Visibilidade/Cálculo), mas `static/js/rule_engine.js` só
implementa as funções de Validação. Para conectar Visibilidade
(`visibleIf`/`hiddenIf`/`enabledIf`) ou Cálculo
(`calculate`/`sum`/`linkProgress`/`statusMap`/`format`):

1. Implementar a função correspondente em `rule_engine.js` (mesmo
   padrão das funções de Validação: recebe `el, params`).
2. `source_id`/`target_id` resolvendo outro elemento do DOM
   pressupõe uma convenção estável de id — o padrão `comp-<id>` era
   específico do canvas do Designer (Fase 7c-11), removido na Fase
   12. Numa página customizada escrita à mão (ou num template do
   CrudGen), a convenção de id/seletor é responsabilidade de quem
   escreve o HTML; a função em `rule_engine.js` recebe o que for
   passado em `params`, não presume mais um formato fixo.
3. `FieldRule` (`entity_key`/`field_name`) continua sendo onde a
   regra fica cadastrada — nenhuma mudança de schema —, mas só produz
   efeito em elemento que leve `data-rules` no HTML (automático em
   tela gerada pelo CrudGen; manual em página customizada).

## Como integrar um servidor OData externo

`/admin/odata/` → criar conexão → testar → navegar dados. Ir além do
navegador read-only significaria gerar uma tela editável a partir da
metadata — `screen_generator.py` (DEVStationFlask) foi cogitado
enquanto o Designer tinha canvas (Fase 7c-11), mas a Fase 12 removeu o
canvas e a ideia de "gerar a árvore de componentes automaticamente"
deixou de fazer sentido sem árvore. O caminho hoje é o dev escrever a
tela à mão, com `/freestyle/consumption` (Fase 13, skill 18) como
referência do consumo — não portar o `screen_generator.py`.

O Tesseract também é, desde a Fase 10, **provedor** OData da própria
base (não só consumidor) — ver "Como expor uma nova entidade no
provedor OData local", acima. `ODataConnectionManager` (o mesmo
consumidor desta seção) detecta sozinho quando a conexão é local
(`ODataConnection.is_local`) e pula o HTTP, chamando
`core/odata_provider/service.py` direto — mesmo contrato de
`query()`/`patch()`/`fetch_metadata()`, sem round-trip de rede.

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
- **`core/odata_provider/registry.py`** (Fase 10) — varre
  `db.Model.registry.mappers` procurando `@odata_expose`; funciona
  pra qualquer model de qualquer Addon/Feature/Core, sem precisar
  saber a origem.
- **`static/js/freestyle/freestyle-tesseract-data.js`** (Fase 13) —
  helper de acesso a dado pronto pra copiar em qualquer página nova
  (`TesseractData.rest`/`.acaoDeDado`/`.opcoes`/`.esc`).
- **`@display_field`/`@weak_ref`** (skill nova —
  `docs/skills/11-referencia-fraca-e-display-field.md`) — anotações
  pra resolver campo de referência fraca (skill 02, ex.: `material_id`
  sem FK real) num nome legível na tela de listagem/detalhe gerada e
  num combo de busca (`/api/options/<table>`), sem tocar schema.
  `@display_field` no model alvo (o que É referenciado), `@weak_ref`
  no model que TEM a referência — `core/crudgen/generator.py` resolve
  automaticamente a partir das duas anotações, para qualquer entidade
  nova, não só as 6 identificadas na revisão que motivou a skill.

## Como adicionar uma pasta/organização nova ao Playground

Pastas (`tesseract_playground_folder`) são só uma árvore
auto-referenciada — criar uma nova via `services/core/
playground_service.py::create_folder()` (ou pela tela). Não precisa de
migration nem model novo pra isso; só usa o que já existe. Apagar uma
pasta exige que ela esteja vazia (skill 06 §8.2) — mover ou apagar o
conteúdo antes.

## Como adicionar um novo tipo de Auth ao Playground

`PlaygroundAuthType` (`model/core/playground_request.py`) tem hoje
`none`/`bearer`/`basic`/`api_key`. Pra adicionar um tipo novo (ex.:
OAuth2 com refresh token):

1. Adicionar a constante em `PlaygroundAuthType`.
2. Adicionar o `if` correspondente em
   `_auth_headers_for()` (`services/core/playground_service.py`) —
   monta o header derivado a partir de `auth_config`.
3. Adicionar os campos de formulário na tela (`playground.html`) e o
   `if` de leitura em `_build_auth_config()`
   (`controller/core/playground.py`).

`auth_config` é sempre um JSON livre por tipo — não precisa de
migration pra tipo novo, só pra campo novo em `PlaygroundRequest` em
si (isso sim exige `db migrate`).

## Como o menu hierárquico resolve ordem/colapso/ícone (skill 10 + adenda)

Três camadas, nessa ordem de prioridade: preferência pessoal
(`tesseract_user_menu_preference`) → padrão global
(`system_config`, chaves `core.menu.*`) → ordem original
(`Transaction.order_index`, já persistida pelo sync). A profundidade
máxima de ícone (`core.menu.icon_max_depth`) é só mais uma chave nessa
mesma camada de padrão global — `-1` (default) nunca esconde ícone,
`N` esconde a partir do nível `N` (0-based). Editável em
`/admin/menu-settings/`.

## Como adicionar uma tela de admin nova que usa `system_config`

Seguir o padrão de `services/core/menu_preference_service.py`: uma
constante `_KEY_X = "namespace.chave"` por parâmetro, um getter
(`SystemConfig.get(key, default=...)`) e um setter que passa por uma
função privada `_set_config()`/similar — nunca ler/escrever
`SystemConfig` direto no controller.

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
| `flask db upgrade` falha com `already exists`/`duplicate column` numa migration que cria tabela ou coluna nova | `ModuleManager.create_all_pending_tables()` chama `db.create_all()` em todo boot, inclusive quando o boot é do próprio comando `flask db` — ele cria a estrutura antes do Alembic ter a chance | Corrigido: `create_all_pending_tables()` pula `db.create_all()` quando `sys.argv[1] == "db"`. Se ainda ocorrer numa migration muito antiga (ex.: `mash_control_rule`), é um caso pré-existente e separado — não passa pelo mesmo caminho de código, registrado no BACKLOG.md |
| Playground retorna 404 numa API que funciona no Postman | Query Params colados à mão dentro da própria `url`, sem encoding — v1 não tinha campo dedicado | Usar o campo "Query Params" da v2 (`params_json`), não colar na URL |
| OData: "Falha ao conectar" mesmo com a URL certa | `base_url` cadastrada já era a própria URL de `$metadata` — a descoberta antiga concatenava sufixo em cima | Corrigido: `_strip_metadata_suffix()` tenta a URL crua primeiro |
| OData: navegar uma entidade dá 404 mesmo ela existindo no servidor | Nome usado na rota era o `EntityType` (singular) em vez do `EntitySet` (plural, real) | Corrigido para EDMX real; para o formato customizado sem `EntitySet`, usar o campo editável de "nome da rota" na tela "Ver entidades" |
