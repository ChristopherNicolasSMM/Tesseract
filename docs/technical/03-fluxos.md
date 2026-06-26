# 03 — Fluxos (Sistema)

## Caminho feliz: boot do app (`create_app()`)

```mermaid
flowchart TD
    A[create_app] --> B[Config por ambiente + logging]
    B --> C[DB factory + Flask-Migrate]
    C --> D[Flask-Login]
    D --> E[Comandos CLI: init-admin/generate/reset-password/transactions-doc]
    E --> F[Importa models de Core]
    F --> G[discover_and_register_addons]
    G --> H[Importa TODOS os models de TODAS as Features primeiro]
    H --> I[SÓ DEPOIS aplica prefixo de tabela em todos]
    I --> J[apply_template_loader — ChoiceLoader com templates de cada Addon/Feature]
    J --> K[create_all_pending_tables]
    K --> L[sync_all_permissions]
    L --> M[sync_all_transactions + sync_core_transactions]
    M --> N[ensure_default_system_config]
    N --> O[Registra Blueprints de Core: auth, admin/*, pages, profile, designer]
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
    Home-->>U: sidebar com submenus colapsáveis + cards
```

## Sequência: requisição autenticada a uma rota gerada pelo CrudGen

```mermaid
sequenceDiagram
    actor U as Usuário
    participant F as Flask (rota gerada)
    participant L as Flask-Login
    participant P as permission_required
    participant FR as FieldRule (Fase 7b)
    participant S as Service (gerado)
    participant DB as Banco

    U->>F: GET /brewstation/yeast-strains/
    F->>L: current_user.is_authenticated?
    F->>P: has_permission("yeast_strains.list")?
    F->>FR: busca regras de validação ativas por campo
    F->>S: query com filtro tipado + paginação
    S->>DB: SELECT ... WHERE is_deleted=False
    F-->>U: HTML com data-rules + rule_engine.js incluído
    U->>F: POST (novo registro, com validação client-side já passada)
    F->>S: create(data)
    S->>DB: INSERT
    F-->>U: redirect + flash
```

## Sequência: anexar regra de validação e ver ela funcionar (Fase 7b)

```mermaid
sequenceDiagram
    actor Admin as Administrador
    participant FRUI as /admin/field-rules/
    participant FR as FieldRule (banco)
    participant Form as Formulário gerado (CrudGen ou Designer)
    participant RE as rule_engine.js

    Admin->>FRUI: cria regra (entity_key, field_name, rule_id, params)
    FRUI->>FR: INSERT
    Admin->>Form: abre tela (manage.html, detail.html, ou runtime do Designer)
    Form->>FR: consulta regras ativas para esta entidade/campo
    Form-->>Admin: renderiza input com data-rules='[...]'
    Admin->>Form: tenta enviar formulário sem preencher
    Form->>RE: validateForm() roda no submit
    RE-->>Admin: mostra erro inline, bloqueia envio
```

## Sequência: montar e publicar uma página no Designer (Fase 7c)

```mermaid
sequenceDiagram
    actor Admin as Administrador
    participant Editor as /admin/designer/<id>/edit
    participant API as Endpoints JSON do Designer
    participant DB as DesignerPage/DesignerComponent
    participant Runtime as /designer/<slug>

    Admin->>Editor: abre o canvas
    Admin->>API: clica "+ Textbox" na paleta
    API->>DB: INSERT DesignerComponent (tamanho padrão do tipo)
    API-->>Editor: renderiza o componente no canvas
    Admin->>API: arrasta/redimensiona (mousedown/mousemove/mouseup)
    API->>DB: UPDATE x/y/width/height
    Admin->>API: anexa regra de validação ao textbox
    API->>DB: UPDATE rules (JSON)
    Admin->>Editor: clica "Publicar"
    Editor->>DB: UPDATE is_published=True
    Admin->>Runtime: abre /designer/<slug>
    Runtime->>DB: SELECT página + componentes (só se is_published)
    Runtime-->>Admin: HTML real renderizado, com rule_engine.js conectado
```

## Sequência: navegar dados de um servidor OData externo (Fase 8)

```mermaid
sequenceDiagram
    actor Admin as Administrador
    participant UI as /admin/odata/
    participant Mgr as ODataConnectionManager
    participant Ext as Servidor OData externo
    participant DB as ODataConnection (cache)

    Admin->>UI: cria conexão (nome, URL base)
    Admin->>UI: clica "Testar"
    UI->>Mgr: test_connection()
    Mgr->>Ext: tenta $metadata.json, $metadata, etc (cadeia de descoberta)
    Ext-->>Mgr: metadata (JSON ou XML/EDMX)
    Mgr->>DB: cacheia por 5 minutos
    Mgr-->>UI: "N entidades encontradas"
    Admin->>UI: "Ver entidades" → "Navegar dados"
    UI->>Mgr: query(entidade, $filter/$top/$skip)
    Mgr->>Ext: GET com os parâmetros OData
    Ext-->>UI: linhas reais, paginadas
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
