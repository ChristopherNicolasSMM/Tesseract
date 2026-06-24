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

    tesseract_user {
        int id PK
        string username
        string email
        string password_hash
        bool is_active
        bool is_admin
        string cpf
        string theme
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
        string source_module
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
| `tesseract_transaction` | `is_standard` | `True` = catálogo de Core (`TX_*`); `False` = contribuída por Addon/Feature |
| `tesseract_transaction` | `permission_required` | Nome de Permission real — nunca um tier separado |
| `alembic_version` | `version_num` | Controlada pelo Flask-Migrate — nunca editar manualmente |

## Regra de soft-delete

Todas as tabelas de domínio (Addon/Feature) seguem `is_deleted`/
`deleted_at` (skill 02). Tabelas de Core (`tesseract_user`,
`tesseract_role` etc.) não têm soft-delete — usam `is_active` (User)
ou são removidas de fato quando vazias de referência (Role).

## Migrations

`db.create_all()` cria tabela nova (Addon/Feature recém-instalado).
**Nunca altera coluna de tabela já existente** — isso é
responsabilidade do Flask-Migrate (`python run.py db migrate && db
upgrade`). Ver `migrations/` na raiz do projeto.
