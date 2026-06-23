# 02 — Nomenclatura de Tabelas e Prefixos (Regra Tri-Nível)

## Hierarquia de prefixo

```
tesseract_[tabela]                          ← Core (User, Role, Permission, SystemConfig,
                                              ModuleState, CodeSnapshot)
tesseract_[addon]_[tabela]                  ← Tabelas do núcleo de um Addon (sem Feature)
tesseract_[addon]_[feature]_[tabela]        ← Tabelas de uma Feature dentro de um Addon
```

**Plugins nunca aparecem nesta hierarquia** — por definição, não criam tabela
(ver skill 00). Se um nome de tabela começar com `tesseract_[plugin_name]_`,
isso é um erro de classificação: o módulo deveria ser um Addon.

## Exemplos concretos

| Tabela | Camada |
|---|---|
| `tesseract_user` | Core |
| `tesseract_role` | Core |
| `tesseract_permission` | Core |
| `tesseract_module_state` | Core (estado de ativação de Addons/Plugins) |
| `tesseract_code_snapshot` | Core (versionamento) |
| `tesseract_brewstation_recipe` | Núcleo do Addon `brewstation` |
| `tesseract_brewstation_inventory` | Núcleo do Addon `brewstation` |
| `tesseract_brewstation_yeastbank_strain` | Feature `yeast_bank` dentro do Addon `brewstation` |
| `tesseract_brewstation_yeastbank_starter_log` | Feature `yeast_bank` |
| `tesseract_brewstation_mashctrl_session` | Feature `mash_control` (sigla `mashctrl`, ver regra de sigla abaixo) |

## Regra de sigla de Feature

Quando o nome da Feature for longo, define-se uma **sigla curta e estável**
no `feature.json` (campo `table_prefix_suffix`), nunca abreviada
informalmente no código. A sigla, uma vez publicada em uma versão, **não
muda** — alterar exigiria migration de rename em todas as tabelas da
Feature.

| Feature | Sigla (`table_prefix_suffix`) |
|---|---|
| `feature_mash_control` | `mashctrl` |
| `feature_device_manager` | `dvm` |
| `feature_yeast_bank` | `yeastbank` (curto o bastante, sem necessidade de abreviar mais) |
| `feature_integ_bfather` | `bf` |

## Regra de ouro

> Nenhuma tabela é criada sem prefixo correspondente ao nível em que o
> módulo vive. `device` é proibido. `tesseract_device` é proibido (pertenceria
> ao Core, mas device é conceito do addon `brewstation`). O único nome
> correto é `tesseract_brewstation_dvm_device`.

## Onde o prefixo é declarado (e nunca hardcoded em model.py)

- **Core**: fixo, `tesseract_`, definido uma vez em `core/model/__init__.py`.
- **Addon**: campo `table_prefix` no `addon.json` — ex.: `"table_prefix": "brewstation"`.
- **Feature**: campo `table_prefix_suffix` no `feature.json` da Feature — o
  prefixo final é resolvido em runtime pelo `ModuleManager` concatenando
  `tesseract_` + `table_prefix` do Addon pai + `table_prefix_suffix` da Feature.
- O desenvolvedor escreve `__tablename__ = "yeast_strain"` (nome curto, sem
  prefixo) no model; o `ModuleManager`/CrudGen aplica o prefixo completo no
  momento do registro no SQLAlchemy metadata — igual ao mecanismo de
  `prefix_models()` que já existia no BrewStation, agora generalizado para
  qualquer Addon/Feature.

## Colunas — convenções obrigatórias

| Coluna | Quando obrigatória | Tipo |
|---|---|---|
| `id` | Toda tabela | Integer, PK |
| `created_at` | Toda tabela | DateTime, default `utcnow` |
| `updated_at` | Toda tabela editável | DateTime, `onupdate=utcnow` |
| `created_by_user_id` | Tabelas com rastreamento de autoria (FK para `tesseract_user.id`) | Integer, FK, nullable |
| `is_deleted` / `deleted_at` | Tabelas com soft-delete (padrão para qualquer entidade gerada pelo CrudGen — ver skill de versionamento/permissões: ações `trash`/`restore`) | Boolean + DateTime |
| `[entidade]_id` em FK | Sempre singular + `_id` | `yeast_strain_id`, nunca `yeaststrainid` ou `id_yeast_strain` |

## Resolução de Foreign Key entre módulos

- FK de uma Feature para o núcleo do próprio Addon: permitido diretamente
  (ex.: `feature_yeast_bank` → `tesseract_brewstation_recipe`).
- FK de uma Feature/Addon para `tesseract_user` (Core): sempre permitido —
  User é global.
- FK entre **Addons diferentes**, ou entre **Features de Addons
  diferentes**: proibido em nível de banco. A comunicação é só via
  `EventBus` ou chamada de `service` público do outro Addon — nunca FK
  direta. Isso preserva o requisito de isolamento (se um Addon for
  desinstalado, nenhuma FK órfã quebra outro).
- FK entre Feature e Plugin: impossível por definição (Plugin não tem
  tabela).
