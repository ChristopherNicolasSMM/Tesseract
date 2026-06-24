# 03 — Fluxos (Sistema)

## Caminho feliz: boot do app (`create_app()`)

```mermaid
flowchart TD
    A[create_app] --> B[Config por ambiente + logging]
    B --> C[DB factory + Flask-Migrate]
    C --> D[Flask-Login]
    D --> E[Comandos CLI: init-admin/generate/reset-password]
    E --> F[Importa models de Core]
    F --> G[discover_and_register_addons]
    G --> H[Importa TODOS os models de TODAS as Features primeiro]
    H --> I[SÓ DEPOIS aplica prefixo de tabela em todos]
    I --> J[apply_template_loader — ChoiceLoader com templates de cada Addon/Feature]
    J --> K[create_all_pending_tables]
    K --> L[sync_all_permissions]
    L --> M[sync_all_transactions + sync_core_transactions]
    M --> N[ensure_default_system_config]
    N --> O[Registra Blueprints de Core: auth, admin/users, admin/roles, admin/versioning, pages, profile]
    O --> P[App pronto]
```

## Sequência: login até a home

```mermaid
sequenceDiagram
    actor U as Usuário
    participant Login as GET/POST /login
    participant Auth as /api/auth/login
    participant Home as GET /
    participant TX as Transaction (catálogo)

    U->>Login: GET /login
    Login-->>U: formulário
    U->>Auth: POST {username, password}
    Auth->>Auth: check_password() + login_user()
    Auth-->>U: 200 {success: true}
    U->>Home: GET / (redirect via JS)
    Home->>TX: lista transações ativas, filtra por has_permission()
    TX-->>Home: agrupadas por "group"
    Home-->>U: sidebar + cards
```

## Sequência: requisição autenticada a uma rota gerada pelo CrudGen

```mermaid
sequenceDiagram
    actor U as Usuário
    participant F as Flask (rota gerada)
    participant L as Flask-Login
    participant P as permission_required
    participant S as Service (gerado)
    participant DB as Banco

    U->>F: POST /brewstation/yeast-strains/ (form: novo registro)
    F->>L: current_user.is_authenticated?
    L-->>F: True
    F->>P: has_permission("yeast_strains.create")?
    P-->>F: True
    F->>S: YeastStrainService().create(data)
    S->>DB: INSERT INTO tesseract_brewstation_yeastbank_strain
    DB-->>S: OK
    S-->>F: ServiceResult(success=True)
    F-->>U: redirect + flash "Criado com sucesso"
```

## Sequência: alterar coluna de model existente (migration)

```mermaid
sequenceDiagram
    actor Dev as Desenvolvedor
    participant Model as model/core/user.py
    participant CLI as python run.py db migrate
    participant Alembic as Alembic
    participant DB as Banco real

    Dev->>Model: adiciona nova coluna
    Dev->>CLI: db migrate -m "descrição"
    CLI->>Alembic: autogenerate (compara metadata vs banco)
    Alembic-->>CLI: gera migrations/versions/xxxx.py (só o delta)
    Dev->>CLI: db upgrade
    CLI->>DB: ALTER TABLE ... ADD COLUMN ...
    DB-->>Dev: coluna existe de verdade
```

## Sequência: `python run.py generate` (CrudGen)

```mermaid
sequenceDiagram
    actor Dev as Desenvolvedor
    participant CLI as run.py generate
    participant Gen as core/crudgen/generator.py
    participant TP as table_prefix.py
    participant Ver as core/versioning.py
    participant Perm as permissions_sync.py

    Dev->>CLI: --model x.py --addon brewstation --feature yeast_bank
    CLI->>Gen: generate(Model, ...)
    Gen->>TP: apply_table_prefix(Model, "brewstation_yeastbank")
    TP-->>Gen: nome final (rejeita se > 55 chars)
    loop Para cada arquivo
        Gen->>Gen: Renderiza template Jinja2
        Gen->>Ver: snapshot_if_needed(caminho, conteúdo)
        Gen->>Gen: Escreve arquivo em disco
    end
    Gen->>Perm: sync_model_permissions(Model, "plural")
    Gen-->>Dev: resumo (arquivos, tabela, permissões)
```
