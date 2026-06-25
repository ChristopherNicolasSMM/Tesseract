# 07 — Catálogo de Transações

> Gerado automaticamente por `python run.py transactions-doc` a partir do banco real — não editar manualmente, as edições se perdem na próxima geração. Para mudar uma transação vinda do código, edite o `get_transactions()`/`transactions_catalog.py` correspondente. Para uma transação manual, use a tela `/admin/transactions/`.

Total: 13 transação(ões), 13 ativa(s).

## Admin

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_ADMIN_TRANSACTIONS` | Catálogo de Transações | `/admin/transactions` | `admin` | Core | Ativa |
| `TX_ADMIN_ODATA` | Conexões OData | `/admin/odata` | `admin` | Core | Ativa |
| `TX_ADMIN_DESIGNER` | Designer Visual | `/admin/designer` | `admin` | Core | Ativa |
| `TX_ADMIN_USERS` | Gestão de Usuários | `/admin/users` | `admin` | Core | Ativa |
| `TX_ADMIN_ROLES` | Papéis e Permissões | `/admin/roles` | `admin` | Core | Ativa |
| `TX_ADMIN_FIELD_RULES` | Regras de Campo | `/admin/field-rules` | `admin` | Core | Ativa |
| `TX_ADMIN_VERSIONING` | Versionamento de Código | `/admin/versioning` | `admin` | Core | Ativa |

## BrewStation

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_YEAST_BANK` | Banco de Levedura | `/brewstation/yeast-strains` | `yeast_strains.list` | brewstation | Ativa |
| `TX_DEVICE_MANAGER` | Dispositivos IoT | `/brewstation/device-metadatas` | `device_metadatas.list` | brewstation | Ativa |
| `TX_YEAST_BANK_RECALC_VIABILITY` | Recalcular Viabilidade | `/brewstation/yeast-bank-tools/recalculate-viability` | `yeast_bank_items.recalculate_viability` | brewstation | Ativa |
| `TX_MASH_RECIPES` | Receitas de Brassagem | `/brewstation/mash-recipes` | `mash_recipes.list` | brewstation | Ativa |
| `TX_BREW_SESSIONS` | Sessões de Brassagem | `/brewstation/brew-sessions` | `brew_sessions.list` | brewstation | Ativa |

## Core

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_HOME` | Início | `/` | `—` | Core | Ativa |
