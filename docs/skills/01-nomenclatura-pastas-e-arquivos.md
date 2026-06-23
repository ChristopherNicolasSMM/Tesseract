# 01 — Nomenclatura de Pastas e Arquivos

## Estrutura raiz do Core

```
tesseract/
├── core/
│   ├── module_manager.py
│   ├── module_loader.py
│   ├── module_base.py          # classe abstrata comum a Addon e Plugin
│   ├── addon_base.py           # herda ModuleBase, exige table_prefix e register_models()
│   ├── plugin_base.py          # herda ModuleBase, register_models() é proibido/ausente
│   ├── event_bus.py
│   ├── permission_manager.py   # RBAC (Role/Permission/has_permission)
│   ├── crudgen/                # gerador de CRUD (só aplicável a Addon/Feature)
│   ├── versioning/             # CodeSnapshot, snapshot_if_needed()
│   └── template_loader.py
├── annotations/                 # decorators (@label, @plural, @listview, @form, @permission...)
├── model/core/                  # User, Role, Permission, SystemConfig, ModuleState, CodeSnapshot
├── controller/core/             # auth, admin (roles/users), dashboard
├── api/routes/core/             # endpoints de API do Core
├── services/core/
├── templates/core/
├── static/core/
├── addons/
│   └── addon_[nome]/
└── plugins/
    └── plugin_[nome]/
```

## Estrutura obrigatória de um Addon

```
addons/addon_[nome]/
├── addon.json                  # manifesto — ver skill 03
├── addon.py                    # classe AddonX(AddonBase)
├── core/                       # parte "núcleo" do addon, sem feature específica
│   ├── model/
│   ├── controller/
│   ├── services/
│   └── templates/addon_[nome]/
├── features/
│   └── feature_[nome_feature]/
│       ├── feature.json
│       ├── feature.py
│       ├── menu_config.json
│       ├── model/
│       ├── controller/
│       ├── services/
│       ├── templates/feature_[nome_feature]/
│       ├── i18n/                       # pt_BR.json obrigatório, demais opcionais
│       └── docs/
├── i18n/                               # pt_BR.json obrigatório, demais opcionais
├── static/
└── docs/
```

## Estrutura obrigatória de um Plugin

```
plugins/plugin_[nome]/
├── plugin.json                 # manifesto — ver skill 03
├── plugin.py                   # classe PluginX(PluginBase)
├── controller/                 # rotas web, se houver
├── api/routes/                 # rotas REST, se houver
├── services/                   # orquestração, integrações externas
├── templates/plugin_[nome]/    # só se o plugin tiver tela própria
├── i18n/                       # pt_BR.json obrigatório, demais opcionais
├── static/
└── docs/
```

**Proibido em um Plugin**: pasta `model/` com classes `db.Model`. Se aparecer
necessidade de persistir dado, o módulo deixou de ser Plugin — vira Addon (ou
o dado pertence a um Addon já existente e o Plugin deve falar com o `service`
desse Addon).

## Regras de nomenclatura de arquivo dentro de um módulo

| Tipo de arquivo | Padrão | Exemplo (Addon `brewstation`, Feature `yeast_bank`) |
|---|---|---|
| Model | `[entidade_singular].py` | `model/yeast_strain.py` |
| Controller (web) | `[entidade_plural].py` | `controller/yeast_strains.py` |
| Service | `[entidade_singular]_service.py` | `services/yeast_strain_service.py` |
| Rotas API | `[entidade_plural]_routes.py` | `api/routes/yeast_strains_routes.py` |
| Hooks (controller) | `[entidade_plural]_hooks.py` | `controller/yeast_strains_hooks.py` |
| Hooks (service) | `[entidade_singular]_service_hooks.py` | `services/yeast_strain_service_hooks.py` |
| Hooks (rotas API) | `[entidade_plural]_routes_hooks.py` | `api/routes/yeast_strains_routes_hooks.py` |
| Template de listagem | `manage.html` | `templates/feature_yeast_bank/yeast_strains/manage.html` |
| Template de detalhe | `detail.html` | `.../yeast_strains/detail.html` |
| Modal de formulário | `_modals/form_modal.html` | `.../yeast_strains/_modals/form_modal.html` |

Arquivos `*_hooks.py` são criados **uma única vez** pelo CrudGen e nunca
sobrescritos em `--overwrite`. Todo o restante listado acima é gerado e pode
ser sobrescrito livremente.

## Regra de nomenclatura de classes

| Elemento | Padrão | Exemplo |
|---|---|---|
| Classe de Addon | `Addon` + PascalCase do nome | `AddonBrewstation` |
| Classe de Plugin | `Plugin` + PascalCase do nome | `PluginBrewfatherNotifier` |
| Classe de Feature | `Feature` + PascalCase do nome | `FeatureYeastBank` |
| Variável obrigatória no `addon.py`/`plugin.py`/`feature.py` | `__module__ = "NomeDaClasse"` | `__module__ = "AddonBrewstation"` |

## O que NUNCA pode ser criado dentro de `tesseract/core/`

Qualquer arquivo que represente regra de negócio de um domínio específico
(cervejaria, biblioteca, CRM, etc.) é proibido em `core/`. Se uma IA ou dev
está prestes a criar `core/model/yeast_strain.py`, a ação correta é criar
`addons/addon_brewstation/features/feature_yeast_bank/model/yeast_strain.py`.
