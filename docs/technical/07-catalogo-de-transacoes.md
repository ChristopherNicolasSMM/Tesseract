# 07 — Catálogo de Transações

> Gerado automaticamente por `python run.py transactions-doc` a partir do banco real — não editar manualmente, as edições se perdem na próxima geração. Para mudar uma transação vinda do código, edite o `get_transactions()`/`transactions_catalog.py` correspondente. Para uma transação manual, use a tela `/admin/transactions/`. Árvore de profundidade arbitrária (skill 10) — cada nível vira uma seção aninhada.

Total: 78 transação(ões), 78 ativa(s).

## BrewStation

### Banco de Levedura

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_YEAST_BANK` | Cepas de Levedura | `/brewstation/yeast-strains` | `yeast_strains.list` | brewstation | Ativa |
| `TX_YEAST_BANK_ITEMS` | Itens do Banco | `/brewstation/yeast-bank-items` | `yeast_bank_items.list` | brewstation | Ativa |
| `TX_YEAST_CONTAINERS` | Containers | `/brewstation/yeast-containers` | `yeast_containers.list` | brewstation | Ativa |
| `TX_YEAST_STORAGE_DEVICES` | Dispositivos de Armazenamento | `/brewstation/yeast-storage-devices` | `yeast_storage_devices.list` | brewstation | Ativa |
| `TX_YEAST_STORAGE_READINGS` | Leituras de Temperatura | `/brewstation/yeast-storage-readings` | `yeast_storage_readings.list` | brewstation | Ativa |
| `TX_YEAST_STARTER_LOGS` | Starters | `/brewstation/yeast-starter-logs` | `yeast_starter_logs.list` | brewstation | Ativa |
| `TX_YEAST_CELL_COUNT_HISTORIES` | Contagens de Células | `/brewstation/yeast-cell-count-histories` | `yeast_cell_count_histories.list` | brewstation | Ativa |
| `TX_YEAST_BANK_EVENTS` | Eventos do Banco | `/brewstation/yeast-bank-events` | `yeast_bank_events.list` | brewstation | Ativa |
| `TX_YEAST_BANK_CONFIGS` | Configurações do Banco | `/brewstation/yeast-bank-configs` | `yeast_bank_configs.list` | brewstation | Ativa |
| `TX_YEAST_BANK_RECALC_VIABILITY` | Recalcular Viabilidade | `/brewstation/yeast-bank-tools/recalculate-viability` | `yeast_bank_items.recalculate_viability` | brewstation | Ativa |

### Controle de Mostura

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_BRIDGE_IMPORT` | Cadastro Primário (Bridge) | `/brewstation/bridge-import/` | `device_actors.create` | brewstation | Ativa |
| `TX_PLANT_WORKSPACE` | Workspace de Planta | `/brewstation/plant-workspace/` | `brew_plants.list` | brewstation | Ativa |
| `TX_DASHBOARD_LAYOUTS` | Layouts de Dashboard | `/brewstation/dashboard-layouts` | `dashboard_layouts.list` | brewstation | Ativa |
| `TX_DASHBOARD_WIDGETS` | Widgets de Dashboard | `/brewstation/dashboard-widgets` | `dashboard_widgets.list` | brewstation | Ativa |

#### Receitas

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_MASH_RECIPES` | Receitas de Brassagem | `/brewstation/mash-recipes` | `mash_recipes.list` | brewstation | Ativa |
| `TX_RECIPE_INGREDIENTS` | Ingredientes de Receita | `/brewstation/recipe-ingredients` | `recipe_ingredients.list` | brewstation | Ativa |
| `TX_RECIPE_STEPS` | Etapas da Receita | `/brewstation/recipe-steps` | `recipe_steps.list` | brewstation | Ativa |
| `TX_RECIPE_TIMELINE` | Importar Receita para Brassar | `/brewstation/recipe-timeline` | `recipe_steps.list` | brewstation | Ativa |
| `TX_FERMENTATION_STEPS` | Etapas de Fermentação | `/brewstation/fermentation-steps` | `fermentation_steps.list` | brewstation | Ativa |
| `TX_WATER_PROFILES` | Perfis de Água | `/brewstation/water-profiles` | `water_profiles.list` | brewstation | Ativa |
| `TX_RECIPE_HISTORYS` | Histórico de Receitas | `/brewstation/recipe-historys` | `recipe_historys.list` | brewstation | Ativa |

#### Planta & Sessão

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_BREW_PLANTS` | Plantas de Brassagem | `/brewstation/brew-plants` | `brew_plants.list` | brewstation | Ativa |
| `TX_BREW_PLANT_VESSELS` | Tanques | `/brewstation/brew-plant-vessels` | `brew_plant_vessels.list` | brewstation | Ativa |
| `TX_BREW_PLANT_MAPPINGS` | Mapeamentos de Planta | `/brewstation/brew-plant-mappings` | `brew_plant_mappings.list` | brewstation | Ativa |

##### Sessões / Batches

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_BREW_SESSIONS` | Sessões de Brassagem | `/brewstation/brew-sessions` | `brew_sessions.list` | brewstation | Ativa |
| `TX_BREW_SESSION_STEPS` | Passos da Sessão | `/brewstation/brew-session-steps` | `brew_session_steps.list` | brewstation | Ativa |
| `TX_BREW_SESSION_LOGS` | Logs da Sessão | `/brewstation/brew-session-logs` | `brew_session_logs.list` | brewstation | Ativa |
| `TX_BREW_SESSION_ALARMS` | Alarmes da Sessão | `/brewstation/brew-session-alarms` | `brew_session_alarms.list` | brewstation | Ativa |
| `TX_DASHBOARD_VIEW` | Dashboard | `/brewstation/dashboards` | `dashboard_layouts.list` | brewstation | Ativa |

#### Automação

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_AUTOMATION_RULES` | Regras de Automação | `/brewstation/automation-rules` | `automation_rules.list` | brewstation | Ativa |
| `TX_AUTOMATION_RULE_LOGS` | Histórico de Regras | `/brewstation/automation-rule-logs` | `automation_rule_logs.list` | brewstation | Ativa |

### Ingredientes

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_INGREDIENT_MAPPINGS` | Mapeamento de Ingredientes (De-Para) | `/brewstation/ingredient-mappings` | `ingredient_mappings.list` | brewstation | Ativa |
| `TX_MALTES` | Maltes | `/brewstation/maltes` | `maltes.list` | brewstation | Ativa |
| `TX_LUPULOS` | Lúpulos | `/brewstation/lupulos` | `lupulos.list` | brewstation | Ativa |
| `TX_LEVEDURAS` | Leveduras | `/brewstation/leveduras` | `leveduras.list` | brewstation | Ativa |

### Envase

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_ENVASES` | Envases | `/brewstation/envases` | `envases.list` | brewstation | Ativa |
| `TX_ITEM_ENVASES` | Itens de Envase | `/brewstation/item-envases` | `item_envases.list` | brewstation | Ativa |

### Integração BrewFather

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_BREWFATHER_SYNCS` | Sincronizações | `/brewstation/brewfather-syncs` | `brewfather_syncs.list` | brewstation | Ativa |

## Core

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_HOME` | Início | `/` | `—` | Core | Ativa |

## Admin

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_ADMIN_USERS` | Gestão de Usuários | `/admin/users` | `admin` | Core | Ativa |
| `TX_ADMIN_ROLES` | Papéis e Permissões | `/admin/roles` | `admin` | Core | Ativa |
| `TX_ADMIN_TRANSACTIONS` | Catálogo de Transações | `/admin/transactions` | `admin` | Core | Ativa |
| `TX_ADMIN_TASKS` | Monitor de Tarefas | `/admin/tasks` | `admin` | Core | Ativa |
| `TX_ADMIN_LOGS` | Logs | `/admin/logs` | `admin` | Core | Ativa |
| `TX_ADMIN_MENU_SETTINGS` | Configurações de Menu | `/admin/menu-settings` | `system_config.menu_settings` | Core | Ativa |

## Ferramentas de Desenvolvimento

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_ADMIN_MODEL_BUILDER` | Model Builder | `/admin/model-builder` | `model_definitions.view` | Core | Ativa |
| `TX_ADMIN_PLAYGROUND` | API/SQL Playground | `/admin/playground` | `playground_requests.execute` | Core | Ativa |
| `TX_ADMIN_ODATA` | Conexões OData | `/admin/odata` | `admin` | Core | Ativa |
| `TX_ADMIN_FIELD_RULES` | Regras de Campo | `/admin/field-rules` | `admin` | Core | Ativa |
| `TX_ADMIN_DESIGNER` | Designer Visual | `/admin/designer` | `admin` | Core | Ativa |
| `TX_ADMIN_VERSIONING` | Versionamento de Código | `/admin/versioning` | `admin` | Core | Ativa |

## Dispositivos IoT

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_DEVICE_FUNCTIONS` | Funções de Dispositivo | `/device-manager/device-functions` | `device_functions.list` | device_manager | Ativa |
| `TX_DEVICE_MANAGER` | Dispositivos | `/device-manager/device-metadatas` | `device_metadatas.list` | device_manager | Ativa |
| `TX_DEVICE_ACTORS` | Atores | `/device-manager/device-actors` | `device_actors.list` | device_manager | Ativa |
| `TX_EMULATED_DEVICES` | Dispositivos Emulados | `/device-manager/emulated-devices` | `emulated_devices.list` | device_manager | Ativa |

## Estoque

| Código | Label | Rota | Permissão | Origem | Status |
|---|---|---|---|---|---|
| `TX_MATERIALS` | Materiais | `/estoque/materials` | `materials.list` | estoque | Ativa |
| `TX_MOVIMENTACAOS` | Movimentações | `/estoque/movimentacaos` | `movimentacaos.list` | estoque | Ativa |
| `TX_SALDOS` | Saldo de Estoque | `/estoque/saldos` | `saldos.list` | estoque | Ativa |
| `TX_COMPOSICAOS` | Composições | `/estoque/composicaos` | `composicaos.list` | estoque | Ativa |
| `TX_FABRICANTES` | Fabricantes | `/estoque/fabricantes` | `fabricantes.list` | estoque | Ativa |
| `TX_ORIGEMS` | Origens | `/estoque/origems` | `origems.list` | estoque | Ativa |
| `TX_TIPO_PRODUTOS` | Tipos de Produto | `/estoque/tipo-produtos` | `tipo_produtos.list` | estoque | Ativa |
| `TX_CATEGORIAS` | Categorias | `/estoque/categorias` | `categorias.list` | estoque | Ativa |
