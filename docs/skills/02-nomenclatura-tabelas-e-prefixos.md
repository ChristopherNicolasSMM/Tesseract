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

## Regra de PK externa (Integer interno + `external_id` UUID)

> **Decisão de arquitetura** (caso real: migração de `device_manager`,
> Fase 6 — o BrewStation original usava UUID como PK de
> `DeviceMetadata`/`DeviceActor`).

A regra de ouro "`id` é sempre Integer" (skill 02) **não tem exceção**
— mas isso não impede uma entidade de também precisar de um
identificador estável para expor a sistemas externos (broker MQTT,
API de terceiros, QR code físico em um equipamento). A solução é ter
os dois, com papéis diferentes:

- `id` (Integer, PK) — usado em toda FK **interna** do Tesseract,
  exatamente como qualquer outra tabela.
- `external_id` (String(36), UUID, `unique=True`) — gerado
  automaticamente na criação (`default=lambda: str(uuid.uuid4())`),
  nunca reaproveitado como PK. É o que se expõe em payload MQTT, URL
  pública, QR code, etc. — nunca o `id` interno (que pode, inclusive,
  ser reciclado/renumerado em uma migration futura sem quebrar nada
  externo).

```python
import uuid

class DeviceMetadata(db.Model):
    __tablename__ = "device"  # nome curto — CrudGen aplica o prefixo
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    ...
```

## Regra de ouro

> Nenhuma tabela é criada sem prefixo correspondente ao nível em que o
> módulo vive. `device` é proibido. `tesseract_device` é proibido (pertenceria
> ao Core, mas device é conceito do addon `brewstation`). O único nome
> correto é `tesseract_brewstation_dvm_device`.

## Regra adicional: nome curto único em todo o Addon (não só na Feature)

> **Achado real** (Fase 6: `YeastStorageDevice` de `feature_yeast_bank`
> e `DeviceMetadata` de `feature_device_manager` ambos usavam o nome
> curto `device`).

O `ModuleManager` importa **todos** os models de **todas** as Features
de um Addon antes de aplicar qualquer prefixo (necessário para FK
cross-Feature funcionar — ver seção de FK abaixo). Isso significa que,
no momento da importação, os nomes curtos (`__tablename__` sem
prefixo) de **todas as Features do mesmo Addon competem pelo mesmo
namespace** na metadata do SQLAlchemy — não só dentro da própria
Feature.

**Regra**: o nome curto de uma tabela deve ser único em todo o Addon,
não apenas dentro da Feature. Prefira nomes específicos
(`storage_device`, não `device`) sempre que o conceito puder colidir
com outra Feature do mesmo Addon — especialmente termos genéricos
(`device`, `item`, `event`, `config`, `log`).

## Limite de tamanho de identificador (PostgreSQL)

O PostgreSQL trunca silenciosamente qualquer identificador (nome de
tabela, índice, constraint) acima de **63 bytes** (`NAMEDATALEN`) —
não dá erro, só corta, e dois nomes que coincidam nos primeiros 63
caracteres colidem sem aviso. SQLite não tem esse limite, então o
problema só aparece em produção, depois do dev já ter "funcionado".

Regras obrigatórias para evitar isso:

- **Nome completo de tabela** (`tesseract_[addon]_[feature]_[tabela]`)
  deve ter **no máximo 55 caracteres** — a margem de 8 caracteres
  abaixo do limite de 63 fica para sufixos automáticos do SQLAlchemy
  em índices/constraints (`ix_`, `uq_`, `fk_`), que concatenam o nome
  da tabela e também estão sujeitos ao mesmo limite de 63.
- **`table_prefix` de Addon**: recomendado no máximo 15 caracteres.
- **`table_prefix_suffix` de Feature**: recomendado no máximo 12
  caracteres — é exatamente para isso que a regra de sigla (seção
  acima) existe; não usar o nome completo da Feature se ele for longo.
- **Checklist de validação** (skill 03) deve rejeitar a geração se o
  nome completo de tabela passar de 55 caracteres — ver item
  correspondente lá.

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
| `external_id` | Entidades que precisam de identificador estável **exposto externamente** (ex.: dispositivo IoT referenciado por um broker MQTT, integração externa) | String(36), UUID, `unique=True`, gerado automaticamente — nunca a PK em si (ver "Regra de PK externa" abaixo) |
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
- **Clarificação** (caso real: `feature_mash_control` referenciando
  `feature_device_manager`, Fase 6): FK entre **duas Features do
  MESMO Addon é permitida** — a restrição é só entre Addons
  diferentes. Duas Features do mesmo Addon compartilham o mesmo
  limite de isolamento (se o Addon for desinstalado, ambas as
  Features saem juntas, então não há risco de FK órfã).
- FK entre Feature e Plugin: impossível por definição (Plugin não tem
  tabela).
