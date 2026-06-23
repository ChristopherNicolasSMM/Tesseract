# 02 — Diagrama C4 (Sistema)

## Nível 1 — Contexto

```mermaid
C4Context
    title Tesseract — Contexto do Sistema

    Person(user, "Usuário", "Administrador / cervejeiro caseiro")
    System(tesseract, "Tesseract", "Hub modular Flask — Core + Addons + Features")
    SystemDb(db, "Banco de dados", "SQLite (dev) / PostgreSQL (produção)")

    Rel(user, tesseract, "Usa via navegador / API")
    Rel(tesseract, db, "Lê e escreve")
```

Atores externos futuros (ainda não integrados): API do BrewFather,
broker MQTT (device_manager), Telegram (notificações) — entram nas
Fases 6+.

## Nível 2 — Container

```mermaid
C4Container
    title Tesseract — Containers

    Person(user, "Usuário")

    System_Boundary(tesseract, "Tesseract") {
        Container(core, "Core", "Flask + Flask-SQLAlchemy + Flask-Login", "ModuleManager, EventBus, RBAC, CrudGen, Versionamento")
        Container(brewstation, "addon_brewstation", "Python/Flask Blueprint", "Domínio: cervejaria caseira")
        Container(yeastbank, "feature_yeast_bank", "Python/Flask Blueprint", "Cepas de levedura (YeastStrain)")
    }

    ContainerDb(db, "Banco de dados", "SQLite / PostgreSQL", "Todas as tabelas tesseract_*")

    Rel(user, core, "HTTP (sessão via cookie)")
    Rel(core, brewstation, "ModuleManager descobre e registra")
    Rel(brewstation, yeastbank, "Addon contém Feature (get_features())")
    Rel(core, db, "SQLAlchemy")
    Rel(yeastbank, db, "SQLAlchemy (via Core)")
```

## Nível 3 — Componente (dentro do Core)

```mermaid
C4Component
    title Core — Componentes

    Container_Boundary(core, "Core") {
        Component(app_factory, "app_factory.py", "Flask factory", "Monta a aplicação, ordem de boot")
        Component(module_manager, "ModuleManager", "Python", "Descoberta, prefixo de tabela, sync de permissão")
        Component(event_bus, "EventBus", "Python", "Pub/sub em memória")
        Component(auth, "auth.py / permissions.py", "Flask-Login", "Autenticação e RBAC")
        Component(crudgen, "crudgen/", "Jinja2", "Gera Service/Controller/Routes/Templates")
        Component(versioning, "versioning.py", "Python", "CodeSnapshot, captura de edição manual perdida")
    }

    Rel(app_factory, module_manager, "instancia e chama discover_and_register_addons")
    Rel(module_manager, event_bus, "publica core.module.activated")
    Rel(module_manager, auth, "usa permission_required indiretamente (rotas geradas)")
    Rel(crudgen, versioning, "snapshot_if_needed() a cada arquivo escrito")
```

No nível Addon/Feature (`addons/addon_brewstation/docs/technical/
02-diagrama-c4.md`, a criar quando houver componente interno
suficientemente complexo para justificar), gera-se só Componente — o
Container já foi coberto aqui.
