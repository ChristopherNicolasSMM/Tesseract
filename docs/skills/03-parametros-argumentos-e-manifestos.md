# 03 — Parâmetros, Argumentos e Manifestos (Regras de Configuração)

Esta skill define **todo parâmetro/argumento** usado em três frentes:
manifestos de módulo (`addon.json`/`plugin.json`/`feature.json`), CLI de
geração (CrudGen), e configuração em runtime (`system_config`).

---

## 1. Manifesto de Addon — `addon.json`

```json
{
  "name": "brewstation",
  "label": "BrewStation",
  "version": "1.0.0",
  "description": "Plataforma de gestão para cervejarias artesanais",
  "author": "S2M Tech",
  "type": "addon",
  "table_prefix": "brewstation",
  "tesseract_min_version": "1.0.0",
  "requires": [],
  "provides": ["recipe_data", "inventory_data"],
  "features": [
    {
      "name": "feature_yeast_bank",
      "label": "Yeast Bank",
      "table_prefix_suffix": "yeastbank",
      "enabled_by_default": false,
      "requires": []
    }
  ],
  "env_keys": ["BREWFATHER_USER_ID", "BREWFATHER_API_KEY"],
  "default_locale": "pt_BR",
  "available_locales": ["pt_BR"]
}
```

| Campo | Obrigatório | Regra |
|---|---|---|
| `name` | Sim | `snake_case`, único em todo o Tesseract, igual ao nome da pasta sem o prefixo `addon_` |
| `label` | Sim | Texto em PT-BR, exibido na UI |
| `version` | Sim | SemVer (`MAJOR.MINOR.PATCH`), comparado pelo `ModuleManager` para checar dependências |
| `type` | Sim | Sempre `"addon"` — usado pelo `ModuleManager` para decidir se `register_models()` é exigido |
| `table_prefix` | Sim | `snake_case`, sem o prefixo `tesseract_` (que é implícito) — ver skill 02 |
| `tesseract_min_version` | Sim | Versão mínima do Core compatível |
| `requires` | Sim (pode ser `[]`) | Lista de `name` de outros Addons/Plugins necessários, com versão opcional (`"brewstation>=1.0.0"`) |
| `provides` | Não | Capacidades que outros módulos podem requisitar via `EventBus` |
| `features` | Sim (pode ser `[]`) | Lista de manifestos resumidos de Feature — o detalhe completo vive no `feature.json` próprio |
| `env_keys` | Não | Variáveis de ambiente que o Addon espera existir no `.env` |
| `default_locale` | Sim | Sempre `"pt_BR"` por enquanto — ver skill 00, seção de i18n |
| `available_locales` | Não | Lista de locales com arquivo em `i18n/` presente; se omitido, assume-se `["pt_BR"]` |

## 2. Manifesto de Feature — `feature.json`

```json
{
  "name": "feature_yeast_bank",
  "label": "Yeast Bank",
  "version": "1.0.0",
  "description": "Congelamento de cepas, slants e decaimento vital",
  "table_prefix_suffix": "yeastbank",
  "enabled": false,
  "requires": [],
  "provides": ["yeast_strain_data"],
  "settings": {}
}
```

Mesmas regras do `addon.json`, exceto:
- `table_prefix_suffix` em vez de `table_prefix` (ver skill 02, regra de sigla).
- `settings`: dicionário livre de parâmetros específicos da Feature, sempre
  com valores-padrão explícitos (nunca `None` silencioso) — lidos via
  `ConfigService` na primeira ativação e persistidos em `system_config`.

## 3. Manifesto de Plugin — `plugin.json`

```json
{
  "name": "brewfather_notifier",
  "label": "Notificador BrewFather",
  "version": "1.0.0",
  "description": "Consulta API do BrewFather e dispara notificação Telegram",
  "type": "plugin",
  "tesseract_min_version": "1.0.0",
  "requires": ["brewstation"],
  "provides": [],
  "routes": {
    "api_prefix": "/api/plugins/brewfather-notifier",
    "web_prefix": null
  },
  "env_keys": ["BREWFATHER_USER_ID", "BREWFATHER_API_KEY", "TELEGRAM_BOT_TOKEN"]
}
```

| Campo | Diferença em relação ao Addon |
|---|---|
| `type` | Sempre `"plugin"` |
| `table_prefix` | **Não existe** — campo proibido neste manifesto |
| `features` | **Não existe** — Plugin não tem Feature |
| `routes` | Objeto explícito de prefixo de rota (Addon resolve isso por convenção a partir do `name`; Plugin declara porque pode não ter rota nenhuma) |

Se um `plugin.json` for encontrado com o campo `table_prefix` presente, o
`ModuleManager` deve **rejeitar o carregamento** com erro explícito — é a
salvaguarda automática da regra "Plugin não tem tabela".

## 4. Argumentos da CLI do CrudGen

```
tesseract generate --model <Caminho> [--overwrite] [--addon <nome>] [--feature <nome>]
tesseract module create-addon <nome>
tesseract module create-feature <addon> <nome>
tesseract module create-plugin <nome>
tesseract module list [--type addon|plugin] [--active|--inactive]
tesseract module enable <nome>
tesseract module disable <nome>
```

| Argumento | Regra |
|---|---|
| `--model` | Caminho relativo ao model anotado. Obrigatório. |
| `--overwrite` | Sem essa flag, o CrudGen nunca sobrescreve arquivo já gerado — só cria os que faltam. Arquivos `_hooks.py` **nunca** são sobrescritos, mesmo com a flag. |
| `--addon` | Obrigatório quando o model não está dentro de uma pasta de Addon já identificável pelo caminho. |
| `--feature` | Opcional — se omitido, o model é tratado como núcleo do Addon (sem Feature). |
| `module create-plugin` | Nunca aceita `--model` — não existe geração de model para Plugin. |

## 5. Parâmetros de runtime (`system_config`)

Convenção de chave: `[namespace].[parametro]`, namespace = nome do
subsistema do Core ou do Addon/Feature dono do parâmetro.

| Chave | Namespace | Tipo | Padrão | Origem |
|---|---|---|---|---|
| `versioning.enabled` | Core | bool | `True` | PyTeca |
| `versioning.trigger` | Core | string (`always`/`on_diff`/`on_overwrite`/`manual_only`) | `on_diff` | PyTeca |
| `versioning.retention_days` | Core | int | `0` (nunca expira) | PyTeca |
| `versioning.retention_max_per_file` | Core | int | `0` (ilimitado) | PyTeca |
| `rbac.session_eager_load` | Core | bool | `True` | PyTeca (joinedload no user_loader) |
| `module_manager.table_creation_max_passes` | Core | int | `10` | BrewStation |
| `module_manager.allow_cross_addon_fk` | Core | bool | `False` | Regra nova (skill 02) |
| `brewstation.yeastbank.<param>` | Addon/Feature | livre | — | Definido pela própria Feature em `settings` do `feature.json` |

**Regra de ouro de parâmetro de runtime**: todo parâmetro alterável sem
redeploy vive em `system_config`, nunca em `.env` (que é reservado para
segredos e coisas que exigem restart: chaves de API, string de conexão de
banco, `SECRET_KEY`).

## 6. Checklist de validação antes de aceitar um manifesto

- [ ] `name` é único entre todos os manifestos já carregados
- [ ] `version` segue SemVer
- [ ] Addon: `table_prefix` presente e em `snake_case`
- [ ] Plugin: campo `table_prefix` **ausente**
- [ ] Toda entrada em `requires` existe (mesmo que ainda inativa) ou o
      carregamento falha com mensagem listando o que falta
- [ ] Feature: `table_prefix_suffix` presente e não duplicado com outra
      Feature do mesmo Addon
- [ ] `i18n/pt_BR.json` presente na pasta do módulo (Addon, Feature e Plugin)
- [ ] `docs/technical/` e `docs/manual/` presentes, com pelo menos
      `01-*.md` preenchido em cada um (ver skill 04)
- [ ] Nenhuma chave de `env_keys` colide com uma já declarada por outro
      módulo (exceto se for intencionalmente compartilhada, ex.: SMTP)
