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
   `OperationalError: no such column` em produção.

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

Implementar `get_transactions()` em qualquer `ModuleBase`/
`FeatureBase` — retorna lista de dicts com `code`, `label`, `group`,
`route`, `permission_required` (nome de Permission real, nunca um
tier separado). Sincronizado automaticamente pelo `ModuleManager` no
boot (`core/transactions_sync.py`).

## Como depreciar/remover uma Feature ou Addon sem deixar tabela órfã

Ainda não há rotina automatizada. Hoje significa:
1. Migration manual de `DROP TABLE` (`flask db revision` + editar à
   mão, já que não há autogenerate pra remoção segura de dados).
2. Remover a pasta do Addon/Feature do disco.
3. Remover a entrada de `tesseract_module_state` (se existir).
4. Permissions/Transactions associadas ficam órfãs — sem limpeza
   automática ainda.

## Pontos de extensão conhecidos

- **`EventBus`** — pub/sub sem acoplamento direto entre Addons.
- **Hooks** (`*_hooks.py`) — customização sem editar código gerado.
- **`core/versioning.py`/`snapshot_service.py`** — qualquer escrita de
  arquivo pode ser versionada, não só pelo CrudGen.
- **`get_transactions()`** — qualquer módulo contribui itens de menu.
- **Migrations (Alembic)** — `migrations/` na raiz, baseline já
  stampada; só precisa de `db migrate`/`db upgrade` daqui pra frente.

## Erros conhecidos e como resolver

| Erro | Causa | Solução |
|---|---|---|
| `OperationalError: no such column` | Coluna nova num model com tabela já existente, sem migration | `python run.py db migrate && db upgrade` |
| `Table 'X' is already defined` | Dois models (testes ou Features diferentes) usando o mesmo `__tablename__` curto | Renomear um deles — nome curto deve ser único em todo o Addon |
| `Foreign key... could not find table` | FK cross-Feature resolvida antes de todos os models serem importados | Não deveria mais ocorrer — `ModuleManager` importa tudo antes de prefixar; se ocorrer, é regressão nesse mecanismo |
| `TemplateNotFound` numa tela de Addon | `ChoiceLoader` não incluiu a pasta `templates/` daquela Feature | Confirmar que `apply_template_loader()` roda depois de `discover_and_register_addons()` |
