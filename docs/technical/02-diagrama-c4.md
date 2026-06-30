# 02 — Diagrama C4 (Sistema)

## Nível 1 — Contexto

```mermaid
C4Context
    title Tesseract — Contexto do Sistema

    Person(user, "Usuário", "Administrador / cervejeiro caseiro")
    System(tesseract, "Tesseract", "Hub modular Flask — Core + Addons + Features")
    SystemDb(db, "Banco de dados", "SQLite (dev) / PostgreSQL (produção)")
    System_Ext(odata, "Servidor OData V4", "Externo, opcional — conectado via /admin/odata/")

    Rel(user, tesseract, "Usa via navegador (telas) ou API")
    Rel(tesseract, db, "Lê e escreve (SQLAlchemy + Flask-Migrate)")
    Rel(tesseract, odata, "Descobre metadata e consulta dados (read-only)")
```

Atores externos ainda não integrados: API do BrewFather, broker MQTT
(`device_manager`), Telegram — aguardam a reescrita dedicada de
`integ_bfather`.

## Nível 2 — Container

```mermaid
C4Container
    title Tesseract — Containers

    Person(user, "Usuário")

    System_Boundary(tesseract, "Tesseract") {
        Container(core, "Core", "Flask + SQLAlchemy + Flask-Login + Flask-Migrate", "ModuleManager, EventBus, RBAC, CrudGen, Versionamento, Transações, Regras, OData, Designer")
        Container(corepages, "Páginas HTML de Core", "Jinja2 + Nice Admin", "Login, Home, Perfil, Admin (Users/Roles/Versioning/FieldRules/Transactions/OData/Designer)")
        Container(designer, "Designer Visual", "JS vanilla (drag/resize)", "Canvas de montagem de páginas, sem framework de frontend")
        Container(rules, "Motor de Regras", "rule_engine.js", "Validação client-side, conectada a formulários do CrudGen e a componentes do Designer")
        Container(brewstation, "addon_brewstation", "Python/Flask Blueprint", "Domínio: cervejaria caseira")
        Container(yeastbank, "feature_yeast_bank", "8 entidades", "Cepas, itens do banco, starters, motor de viabilidade")
        Container(devicemanager, "feature_device_manager", "4 entidades", "Funções, dispositivos IoT, atores, emulação")
        Container(mashcontrol, "feature_mash_control", "12 entidades", "Receitas, plantas, sessões, dashboards, regras de automação")
    }

    ContainerDb(db, "Banco de dados", "SQLite / PostgreSQL", "Todas as tabelas tesseract_*")
    System_Ext(odataext, "Servidor OData externo")

    Rel(user, corepages, "HTTP (sessão via cookie)")
    Rel(corepages, core, "usa RBAC/ModuleManager")
    Rel(corepages, designer, "/admin/designer/*")
    Rel(corepages, rules, "carrega rule_engine.js em formulários e páginas do Designer")
    Rel(core, brewstation, "ModuleManager descobre e registra")
    Rel(brewstation, yeastbank, "Addon contém Feature")
    Rel(brewstation, devicemanager, "Addon contém Feature")
    Rel(brewstation, mashcontrol, "Addon contém Feature")
    Rel(mashcontrol, devicemanager, "FK cross-Feature (mesmo Addon)")
    Rel(core, db, "SQLAlchemy + Alembic")
    Rel(core, odataext, "urllib — descoberta de $metadata e query")
```

## Nível 3 — Componente (dentro do Core)

```mermaid
C4Component
    title Core — Componentes

    Container_Boundary(core, "Core") {
        Component(app_factory, "app_factory.py", "Flask factory", "Monta a aplicação, ordem de boot")
        Component(module_manager, "ModuleManager", "Python", "Descoberta, prefixo de tabela, sync de permissão/transação, ChoiceLoader de templates")
        Component(event_bus, "EventBus", "Python", "Pub/sub em memória, síncrono — único canal cross-Addon (skill 02)")
        Component(auth, "auth.py / permissions.py", "Flask-Login", "Autenticação e RBAC")
        Component(crudgen, "crudgen/", "Jinja2", "Gera Service/Controller/Routes/Templates — smart-list completo")
        Component(versioning, "versioning.py / snapshot_service.py", "Python", "CodeSnapshot, diff, restauração")
        Component(transactions, "transactions_sync.py", "Python", "Catálogo de transações navegáveis")
        Component(rules, "rules_catalog.py", "Python", "Catálogo de regras (Validação/Visibilidade/Cálculo)")
        Component(odata, "odata/connection_manager.py", "urllib/json/xml stdlib", "Conexão e descoberta de metadata OData")
        Component(designer, "designer.py (controller)", "Flask", "CRUD de DesignerPage/DesignerComponent + runtime")
        Component(migrate, "Flask-Migrate", "Alembic", "ALTER de tabela já existente")
    }

    Rel(app_factory, module_manager, "instancia e chama discover_and_register_addons")
    Rel(module_manager, event_bus, "publica core.module.activated")
    Rel(module_manager, transactions, "sync_all_transactions()")
    Rel(crudgen, versioning, "snapshot_if_needed() a cada arquivo escrito")
    Rel(crudgen, rules, "lê FieldRule + catálogo para montar data-rules")
    Rel(designer, rules, "DesignerComponent.rules consumido pelo rule_engine.js no runtime")
    Rel(app_factory, migrate, "migrate.init_app(app, db)")
```

No nível Addon/Feature, gera-se só Componente quando a complexidade
interna justificar — o Container já foi coberto aqui.
