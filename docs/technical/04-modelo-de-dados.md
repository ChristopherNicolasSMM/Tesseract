# 04 — Modelo de Dados (Sistema — tabelas de Core)

> Cobre as tabelas de **Core**. O ER completo de cada domínio vive no
> próprio Addon/Feature:
> - `addons/addon_brewstation/features/feature_yeast_bank/docs/technical/04-modelo-de-dados.md` (8 tabelas)
> - `addons/addon_brewstation/features/feature_device_manager/docs/technical/04-modelo-de-dados.md` (4 tabelas)
> - `addons/addon_brewstation/features/feature_mash_control/docs/technical/04-modelo-de-dados.md` (12 tabelas)

```mermaid
erDiagram
    tesseract_user ||--o{ tesseract_user_roles : "tem"
    tesseract_role ||--o{ tesseract_user_roles : "atribuída a"
    tesseract_role ||--o{ tesseract_role_permissions : "tem"
    tesseract_permission ||--o{ tesseract_role_permissions : "concedida via"
    tesseract_user ||--o{ tesseract_code_snapshot : "autor de (opcional)"
    tesseract_code_snapshot ||--o{ tesseract_code_snapshot : "parent_snapshot_id"
    tesseract_user ||--o{ tesseract_user_list_preference : "configura colunas"
    tesseract_user ||--o{ tesseract_odata_connection : "cria (opcional)"
    tesseract_user ||--o{ tesseract_designer_page : "cria (opcional)"
    tesseract_designer_page ||--o{ tesseract_designer_component : "tem"

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
        string code
        string label
        string group
        string route
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
    }
    tesseract_designer_page {
        int id PK
        string name
        string slug UK
        int canvas_width
        int canvas_height
        bool is_published
        string permission_required
    }
    tesseract_designer_component {
        int id PK
        int page_id FK
        string type "heading/label/textbox/button/image/divider"
        int x
        int y
        int width
        int height
        json properties
        json rules "regras de Validação anexadas"
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
| `tesseract_transaction` | `is_standard` | `True` = catálogo de Core (`TX_*`); `False` = contribuída por Addon/Feature ou manual |
| `tesseract_transaction` | `source_module` | `None`/`"manual"` (criada pela tela) ou nome do Addon (ex.: `"brewstation"`) — define se a tela de edição completa é segura (`source_module="manual"`) ou só `is_active` (qualquer outro valor) |
| `tesseract_user_list_preference` | `list_key` | String, não FK — Core não referencia tabela de domínio |
| `tesseract_field_rule` | `entity_key`/`field_name` | Strings, não FK — mesma razão. `rule_id` referencia `core/rules_catalog.py`, não outra tabela |
| `tesseract_odata_connection` | `metadata_cache` | Cache de 5 minutos da descoberta de `$metadata` — evita bater no servidor externo a cada navegação |
| `tesseract_designer_component` | `rules` | JSON — onde uma regra do `tesseract_field_rule`-like catalog é referenciada por `js_function`, consumida pelo `rule_engine.js` no runtime |
| `alembic_version` | `version_num` | Controlada pelo Flask-Migrate — nunca editar manualmente |

## Regra de soft-delete

Todas as tabelas de domínio (Addon/Feature) seguem `is_deleted`/
`deleted_at` (skill 02). Tabelas de Core (`tesseract_user`,
`tesseract_role`, `tesseract_designer_page` etc.) não têm
soft-delete — usam `is_active` (User) ou exclusão de fato quando vazias
de referência (Role), ou simplesmente não precisam (Designer/OData
são configuração de admin, não dado de domínio auditável).

## Migrations

`db.create_all()` cria tabela nova (Addon/Feature recém-instalado, ou
qualquer tabela de Core nova como `tesseract_designer_page`).
**Nunca altera coluna de tabela já existente** — isso é
responsabilidade do Flask-Migrate (`python run.py db migrate && db
upgrade`). Ver `migrations/` na raiz do projeto.
