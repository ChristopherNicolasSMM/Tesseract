# 04 — Modelo de Dados (Sistema — tabelas de Core)

> Cobre as tabelas de **Core**. O ER completo de cada domínio vive no
> próprio Addon/Feature:
> - `addons/addon_brewstation/features/feature_yeast_bank/docs/technical/04-modelo-de-dados.md` (8 tabelas)
> - `addons/addon_brewstation/features/feature_mash_control/docs/technical/04-modelo-de-dados.md` (18 tabelas)
> - `addons/addon_brewstation/features/feature_ingredientes/docs/technical/04-modelo-de-dados.md` (3 tabelas)
> - `addons/addon_brewstation/features/feature_envase/docs/technical/04-modelo-de-dados.md` (2 tabelas)
> - `addons/addon_brewstation/features/feature_brew_father/docs/technical/04-modelo-de-dados.md` (1 tabela)
> - `addons/addon_device_manager/docs/technical/04-modelo-de-dados.md` (4 tabelas — Addon independente, skill 05)
> - `addons/addon_estoque/docs/technical/04-modelo-de-dados.md` (8 tabelas)

```mermaid
erDiagram
    tesseract_user ||--o{ tesseract_user_roles : "tem"
    tesseract_role ||--o{ tesseract_user_roles : "atribuída a"
    tesseract_role ||--o{ tesseract_role_permissions : "tem"
    tesseract_permission ||--o{ tesseract_role_permissions : "concedida via"
    tesseract_user ||--o{ tesseract_code_snapshot : "autor de (opcional)"
    tesseract_code_snapshot ||--o{ tesseract_code_snapshot : "parent_snapshot_id"
    tesseract_user ||--o{ tesseract_user_list_preference : "configura colunas"
    tesseract_user ||--o{ tesseract_user_menu_preference : "override pessoal de menu"
    tesseract_user ||--o{ tesseract_odata_connection : "cria (opcional)"
    tesseract_user ||--o{ tesseract_designer_page : "cria (opcional)"
    tesseract_odata_connection ||--o{ tesseract_designer_data_action : "usada por (Fase 10)"
    tesseract_user ||--o{ tesseract_designer_data_action : "cria (opcional)"
    tesseract_transaction ||--o{ tesseract_transaction : "parent_id (árvore de menu)"
    tesseract_user ||--o{ tesseract_model_definition : "cria (opcional)"
    tesseract_model_definition ||--o{ tesseract_model_field_definition : "tem"
    tesseract_user ||--o{ tesseract_playground_request : "cria (opcional)"
    tesseract_playground_folder ||--o{ tesseract_playground_folder : "parent_id (árvore N-níveis)"
    tesseract_playground_folder ||--o{ tesseract_playground_request : "organiza"
    tesseract_user ||--o{ tesseract_playground_cookie_jar : "1:1 — sessão HTTP persistida"
    tesseract_scheduled_task ||--o{ tesseract_task_log : "gera execução"

    tesseract_user {
        int id PK
        string username
        string email
        string password_hash
        bool is_active
        bool is_admin
        string cpf
        string theme "light/dark"
    }
    tesseract_role {
        int id PK
        string name
    }
    tesseract_permission {
        int id PK
        string name
    }
    tesseract_module_state {
        int id PK
        string name
        string module_type
        bool is_active
    }
    tesseract_system_config {
        int id PK
        string key
        string value
        string value_type
    }
    tesseract_code_snapshot {
        int id PK
        string file_path
        text content
        string content_hash
        bool is_current
        int parent_snapshot_id FK
    }
    tesseract_transaction {
        int id PK
        string code UK
        string label
        string icon
        string route
        json route_params
        int parent_id FK "árvore, skill 10"
        int order_index
        string permission_required
        bool is_active
        bool is_standard
        string source_module "null/manual/<addon>"
    }
    tesseract_user_list_preference {
        int id PK
        int user_id FK
        string list_key "plural da entidade"
        json visible_columns_json
    }
    tesseract_user_menu_preference {
        int id PK
        int user_id FK UK
        json order_overrides_json
        json collapsed_nodes_json
        bool sidebar_collapsed "null = herda o padrão global"
    }
    tesseract_field_rule {
        int id PK
        string entity_key "plural da entidade"
        string field_name
        string rule_id "id do catalogo (core/rules_catalog.py)"
        json params_json
        bool is_active
    }
    tesseract_odata_connection {
        int id PK
        string name
        string base_url
        string auth_type "none/basic/bearer"
        json metadata_cache
        datetime metadata_cached_at
        json entity_route_overrides "nome_declarado -> nome_real_da_rota"
        bool is_local "Fase 10 — conexão que representa o próprio Tesseract"
    }
    tesseract_designer_page {
        int id PK
        string name
        string slug UK
        text content_html "Fase 12 — HTML escrito à mão; canvas_width/canvas_height/canvas_bg saíram junto do canvas"
        bool is_published
        string permission_required
        string replaces_entity_key "Fase 10 — plural, mesmo formato de field_rule.entity_key"
        string replaces_view "Fase 10 — manage/detail"
        bool replace_in_menu "Fase 10 — só tem efeito com replaces_view=manage"
    }
    tesseract_designer_data_action {
        int id PK
        string name UK
        string description
        int connection_id FK "tesseract_odata_connection"
        string entity_name
        string operation "query/create/update/delete (create/delete ainda não suportados pelo motor de execução)"
        json static_params
        string permission_required "Role — null = público"
        int created_by_user_id FK
    }
    tesseract_model_definition {
        int id PK
        string target_scope "existing_addon/new_addon/new_feature"
        string target_addon_name
        string target_feature_name
        string model_name "PascalCase"
        string table_short_name
        json manifest_draft_json
        string status "draft/generated/error"
        text error_message
        datetime generated_at
        string migration_revision
        int created_by_user_id FK
    }
    tesseract_model_field_definition {
        int id PK
        int model_definition_id FK
        string field_name
        string field_type
        bool nullable
        bool unique
        bool is_required
        string default_value
        int max_length
        string fk_target_table
        string label_text
        bool is_listview_column
        bool is_form_field
        int order_index
    }
    tesseract_playground_request {
        int id PK
        string kind "http/sql"
        string name
        string http_method
        string url
        json headers_json
        json body_json
        json params_json "v2 — query params estruturados"
        string auth_type "v2 — none/bearer/basic/api_key"
        json auth_config
        int folder_id FK
        bool is_archived
        text sql_text
        json last_response_json
        int last_status_code
        text last_error
        int created_by_user_id FK
    }
    tesseract_playground_folder {
        int id PK
        string name
        int parent_id FK "árvore N-níveis"
        int created_by_user_id FK
    }
    tesseract_playground_cookie_jar {
        int id PK
        int user_id FK UK
        json cookies_json
        datetime updated_at
    }
    tesseract_scheduled_task {
        int id PK
        string name
        string task_type "python_call/http_request/sql"
        text target
        string schedule "cron ou intervalo em minutos"
        string status "active/paused/completed/pending_approval/rejected"
        datetime last_run
        datetime next_run
        text result
        bool requires_approval
        bool approved
        int created_by FK
    }
    tesseract_task_log {
        int id PK
        int task_id FK
        string task_name
        string status "running/success/failure"
        datetime started_at
        datetime finished_at
        int duration_ms
        text result
        text error
    }
    tesseract_message_queue {
        int id PK
        string channel "email/webhook/notification"
        json payload
        string status "pending/processing/done/failed/cancelled"
        int retries
        int max_retries
        datetime scheduled_for
        datetime processed_at
        text error_msg
    }
    alembic_version {
        string version_num PK
    }
```

## Tabelas e colunas não óbvias

| Tabela | Coluna | Descrição de negócio |
|---|---|---|
| `tesseract_user` | `is_admin` | Bypassa toda checagem de `has_permission()` |
| `tesseract_user` | `theme` | `"light"`/`"dark"` — preferência de UI por usuário |
| `tesseract_code_snapshot` | `is_current` | Só a versão marcada como atual aparece como "estado hoje" |
| `tesseract_code_snapshot` | `generation_run_id` | Agrupa N arquivos escritos numa mesma execução de `generate()` |
| `tesseract_transaction` | `parent_id`/`order_index` | Árvore de menu (skill 10) — substituiu o campo `group` (string) da skill 07 original |
| `tesseract_transaction` | `is_standard` | `True` = catálogo de Core (`TX_*`); `False` = contribuída por Addon/Feature ou manual |
| `tesseract_transaction` | `source_module` | `None`/`"manual"` (criada pela tela) ou nome do Addon (ex.: `"brewstation"`) — define se a tela de edição completa é segura (`source_module="manual"`) ou só `is_active`/posição na árvore (qualquer outro valor) |
| `tesseract_user_list_preference` | `list_key` | String, não FK — Core não referencia tabela de domínio |
| `tesseract_user_menu_preference` | `sidebar_collapsed` | `NULL` explícito = "não defini, use o padrão global" — não confundir com `False` |
| `tesseract_field_rule` | `entity_key`/`field_name` | Strings, não FK — mesma razão. `rule_id` referencia `core/rules_catalog.py`, não outra tabela |
| `tesseract_odata_connection` | `metadata_cache` | Cache de 5 minutos da descoberta de `$metadata` — evita bater no servidor externo a cada navegação |
| `tesseract_odata_connection` | `entity_route_overrides` | Só usado quando o metadata do servidor não declara `EntitySet` (formato customizado) — guarda a correção manual/automática do nome real da rota de coleção; nunca sobrescrito por um refresh de `metadata_cache` |
| `tesseract_odata_connection` | `is_local` (Fase 10) | Marca a conexão auto-seedada (idempotente, `core/odata_local_seed.py`) que representa o provedor OData do próprio Tesseract — habilita o atalho em processo (sem HTTP) em `ODataConnectionManager` |
| `tesseract_designer_page` | `replaces_entity_key`/`replaces_view`/`replace_in_menu` (Fase 10) | Referência fraca (nunca FK) — `core/designer_menu_override.py` resolve a `Transaction` a trocar via `permission_required == "<replaces_entity_key>.list"`; `replace_in_menu` só tem efeito com `replaces_view == "manage"` |
| `tesseract_designer_page` | `content_html` (Fase 12) | Renderizado com `\|safe`, **nunca** via `render_template_string()` — Jinja vindo do banco seria SSTI (execução de código no servidor). Dado dinâmico entra só por JavaScript (skill 17) |
| `tesseract_designer_data_action` | `static_params` (Fase 10) | JSON livre — parâmetros fixos aplicados sempre, independente de quem dispara a Ação (ex.: um `$filter` que nunca muda) |
| `tesseract_designer_data_action` | `permission_required` (Fase 10) | Mesmo padrão de `tesseract_designer_page.permission_required` (Role, via `User.has_permission()`) — `NULL` = público (sem permissão por usuário individual nesta fase, só por grupo/Role) |
| `tesseract_model_definition` | `manifest_draft_json` | Só preenchido quando `target_scope` é `new_addon`/`new_feature` — rascunho do `addon.json`/`feature.json` que será escrito no scaffold |
| `tesseract_model_field_definition` | `fk_target_table` | Nome completo já prefixado (skill 02) — usado tanto para FK real (mesmo Addon) quanto pra referência fraca (skill 11, quando cross-Addon) |
| `tesseract_playground_request` | `params_json` | Só existe desde a v2 (skill 06 §8) — lista `[{"key","value","enabled"}]`; a `url` guarda só a base, a query final é montada na hora de executar |
| `tesseract_playground_request` | `is_archived` | Ação separada de apagar (que é DELETE físico) — arquivar só esconde da lista principal, recuperável |
| `tesseract_playground_cookie_jar` | `cookies_json` | Escopo por usuário (não por pasta) — snapshot de `requests.Session().cookies`, atualizado a cada execução HTTP que retornar `Set-Cookie` |
| `alembic_version` | `version_num` | Controlada pelo Flask-Migrate — nunca editar manualmente |

## Regra de soft-delete

Todas as tabelas de domínio (Addon/Feature) seguem `is_deleted`/
`deleted_at` (skill 02). Tabelas de Core (`tesseract_user`,
`tesseract_role`, `tesseract_designer_page`, `tesseract_playground_*`
etc.) não têm soft-delete — usam `is_active` (User), exclusão de fato
quando vazias de referência (Role), `is_archived` como alternativa
separada de apagar (Playground), ou simplesmente não precisam
(Designer/OData são configuração de admin, não dado de domínio
auditável). Ver skill 00, Adendo Fase 7a.

## Migrations

`db.create_all()` cria tabela nova (Addon/Feature recém-instalado, ou
qualquer tabela de Core nova como `tesseract_designer_page`).
**Nunca altera coluna de tabela já existente** — isso é
responsabilidade do Flask-Migrate (`python run.py db migrate && db
upgrade`). Ver `migrations/` na raiz do projeto.

**Cuidado**: `db.create_all()` roda em todo boot do app — inclusive
quando o boot é disparado pelo próprio comando `flask db upgrade`.
Isso foi corrigido (`ModuleManager.create_all_pending_tables()` pula
`db.create_all()` quando detecta um comando `flask db ...` em
`sys.argv`) porque, sem essa guarda, `db.create_all()` "ganhava a
corrida" do Alembic em qualquer migration que criasse tabela nova ou
alterasse coluna — a tabela/coluna já existia (criada pelo
`create_all`, refletindo o model já atualizado) no momento em que o
Alembic tentava criar/alterar, e a migration falhava como duplicada.
Ver BACKLOG.md para o achado completo.
