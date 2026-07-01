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
├── logs/                        # log global do Core (skill 08) — ver nota abaixo
│   └── core.log
├── addons/
│   └── addon_[nome]/
└── plugins/
    └── plugin_[nome]/
```

> **Pasta `logs/` na raiz do projeto (adenda — skill 08, Logging e
> Observabilidade)**: obrigatória, destino do log global do Core
> (camada de erro grave — broker inacessível, payload inválido, falha
> de fail-safe, etc.). **Não confundir** com a pasta `logs/` opcional
> por Addon (nota logo abaixo, na seção de Addon) — são dois destinos
> diferentes: log de rotina de um Addon específico nunca vai para
> `tesseract/logs/`, e o log global do Core nunca vai para
> `addons/addon_[nome]/logs/`. Path do arquivo (`core.log`) e regras de
> rotação (tamanho/backup count) são definidos via `system_config`,
> chaves `logging.*` (skill 03/08) — não hardcoded. Esta pasta não é
> versionada (entra no `.gitignore`), só a estrutura em si é garantida
> pelo boot do Core.

## Estrutura obrigatória de um Addon

```
addons/addon_[nome]/
├── addon.json                  # manifesto — ver skill 03
├── addon.py                    # classe AddonX(AddonBase)
├── menu_config.json            # opcional — ordem/label/ícone padrão do grupo de menu do Addon (skill 07)
├── root/                       # parte "núcleo" do addon, sem feature específica
│   ├── model/
│   ├── controller/
│   ├── services/
│   └── templates/addon_[nome]/
├── logs/                       # opcional — só presente se addon.json declarar "logging" (skill 03)
│   └── [arquivo definido em logging.integration_log_path]
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

> **Correção registrada em 2026-06-26**: esta seção dizia `core/` em
> vez de `root/` desde o primeiro commit do projeto — divergência da
> intenção real (confirmada em conversa, e já em uso desde a Fase 9 —
> `addons/addon_device_manager/root/...`). Corrigido aqui; `core/` sem
> prefixo continua reservado exclusivamente ao Core do Tesseract
> (`tesseract/core/`, ver seção anterior) — nunca à subpasta interna de
> um Addon.
>
> **Pasta `logs/` (adenda — docs/skills/05-proposta-addon-device-manager-e-mqtt.md,
> Fase A)**: opcional, só existe se o `addon.json` do módulo declarar a
> seção `logging` (skill 03). Quando presente, é o destino do log de
> integração local daquele Addon — nunca do log global do Core (esse
> continua centralizado em `tesseract/logs/`, ver seção anterior — skill
> 08). O caminho exato do arquivo dentro de `logs/` é definido por
> `logging.integration_log_path` no manifesto, não fixo nesta skill.
>
> **Arquivo `menu_config.json` na raiz do Addon (adenda — skill 07,
> Model Builder/Personalização de Menu)**: opcional. Antes desta
> adenda, `menu_config.json` só existia por Feature; passa a existir
> também na raiz do Addon e na raiz do Plugin (ver estrutura de Plugin
> abaixo), com o mesmo papel: declarar o **valor de autoria** do grupo
> de menu daquele módulo (ordem relativa sugerida, label, ícone) —
> nunca o **override de runtime** feito pelo admin ou pelo usuário
> final, que vive em `system_config`/`tesseract_user_menu_preference`
> (skill 07), não neste arquivo.

## Estrutura obrigatória de um Plugin

```
plugins/plugin_[nome]/
├── plugin.json                 # manifesto — ver skill 03
├── plugin.py                   # classe PluginX(PluginBase)
├── menu_config.json            # opcional — mesmo papel do Addon, ver nota acima (skill 07)
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
