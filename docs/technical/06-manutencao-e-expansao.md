# 06 — Manutenção e Expansão (Sistema)

## Como adicionar um campo a um model existente

1. Editar a coluna em `model/<entidade>.py` (Addon/Feature) ou em
   `model/core/*.py` (Core).
2. Se a entidade passa pelo CrudGen: `python run.py generate --model ... --addon ... [--feature ...] --overwrite`
   (nunca sobrescreve `*_hooks.py`).
3. **Sempre, independente de CrudGen**: se a tabela já existia no
   banco, rodar:
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

- **`EventBus`** — pub/sub sem acoplamento direto entre Addons.
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
