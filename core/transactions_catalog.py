"""
core/transactions_catalog.py

Catálogo inicial de transações de Core — seed executado no boot
(idempotente, igual ao seed de system_config). Adaptado de
transactions/catalog.py (DEVStationFlask) — mantidas só as entradas
que já existem no Tesseract hoje ou que fazem sentido como destino
"a criar"; descartadas as que dependem de peças que não migramos
ainda (DS_ODATA, DS_BUILD — Fase 8 e além).

Convenção de código: TX_<NOME>, paralela ao DS_*/NDS_* do original
mas sem o prefixo "DS" (que no DEVStationFlask distinguia núcleo de
plugin — aqui essa distinção já é o campo `is_standard`).
"""

CORE_TRANSACTIONS = [
    {
        "code": "TX_HOME",
        "label": "Início",
        "group": "Core",
        "description": "Tela inicial.",
        "icon": "bi-house-fill",
        "route": "/",
        "permission_required": None,  # qualquer usuário autenticado
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_USERS",
        "label": "Gestão de Usuários",
        "group": "Admin",
        "description": "Cadastro e configuração de usuários, papéis e permissões.",
        "icon": "bi-people-fill",
        "route": "/admin/users",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_ROLES",
        "label": "Papéis e Permissões",
        "group": "Admin",
        "description": "Criação de Roles e associação de Permissions.",
        "icon": "bi-shield-lock-fill",
        "route": "/admin/roles",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_VERSIONING",
        "label": "Versionamento de Código",
        "group": "Admin",
        "description": "Histórico de arquivos gerados/editados, diff e restauração.",
        "icon": "bi-clock-history",
        "route": "/admin/versioning",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_FIELD_RULES",
        "label": "Regras de Campo",
        "group": "Admin",
        "description": "Validação client-side anexada a campos de qualquer entidade.",
        "icon": "bi-rulers",
        "route": "/admin/field-rules",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_ODATA",
        "label": "Conexões OData",
        "group": "Admin",
        "description": "Conectar a servidores OData externos e navegar dados (somente leitura).",
        "icon": "bi-hdd-network",
        "route": "/admin/odata",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_DESIGNER",
        "label": "Designer Visual",
        "group": "Admin",
        "description": "Montagem de telas por drag-and-drop, sem precisar do CrudGen.",
        "icon": "bi-easel2-fill",
        "route": "/admin/designer",
        "permission_required": "admin",
        "is_standard": True,
    },
    {
        "code": "TX_ADMIN_TRANSACTIONS",
        "label": "Catálogo de Transações",
        "group": "Admin",
        "description": "Itens do menu — ativar/desativar e criar transações manuais.",
        "icon": "bi-signpost-split-fill",
        "route": "/admin/transactions",
        "permission_required": "admin",
        "is_standard": True,
    },
]
