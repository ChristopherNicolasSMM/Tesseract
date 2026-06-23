# 00 — Glossário e Convenções Gerais do Tesseract

> Esta skill é a base de leitura obrigatória antes de qualquer outra. Define os
> termos que as demais skills (nomenclatura, prefixos, parâmetros) usam sem
> reexplicar.

## Termos e suas definições oficiais

| Termo | Definição |
|---|---|
| **Core** | O Hub central do Tesseract. App factory Flask, DB factory, `ModuleManager`, `EventBus`, RBAC, CrudGen, sistema de versionamento. Nunca contém regra de negócio de domínio. |
| **Addon** | Módulo de 1ª classe que **cria tabela(s) no banco**. Tem `table_prefix` próprio. Pode ter Features internas. Gerado (parcialmente) pelo CrudGen. |
| **Feature** | Sub-módulo de um Addon. Tem tabela própria, com prefixo composto (`[addon]_[feature]_`). Não existe fora de um Addon — depende do Addon pai estar ativo. |
| **Plugin** | Módulo que **nunca cria tabela**. Só rotas (web/API), integrações externas, jobs agendados, orquestração. Pode ler dados de Addons via serviço, nunca via ORM direto de outro módulo. |
| **Module** | Termo genérico que engloba Addon e Plugin quando a regra se aplica aos dois igualmente (ex.: estado de ativação no banco). |
| **Manifesto** | Arquivo JSON (`addon.json` ou `plugin.json`) que declara identidade, versão, dependências e (só para Addon) prefixo de tabela e features. |
| **ModuleManager** | Componente do Core responsável por descoberta, instalação, ativação/desativação e registro de Addons e Plugins. |
| **Transação** | Um ponto de entrada navegável (rota + label + ícone) exposto no menu/launcher. Todo Addon/Feature/Plugin pode declarar uma ou mais. |
| **Hook** | Arquivo `_hooks.py` gerado uma única vez (nunca sobrescrito) onde o desenvolvedor customiza comportamento sem editar código gerado pelo CrudGen. |
| **CrudGen** | Pipeline de geração de código a partir de um model anotado. Roda **apenas sobre Addons/Features** (nunca sobre Plugins, que não têm model). |
| **Snapshot** | Registro no histórico de versionamento (`CodeSnapshot`) de um arquivo gerado ou editado. |

## Convenções de idioma

- **Nomes de pasta, arquivo, classe, tabela, coluna, rota, chave de config**: sempre em **inglês**, `snake_case` (pastas/arquivos/tabelas/colunas/config) ou `PascalCase` (classes).
- **Labels visíveis ao usuário final** (menu, formulário, mensagem de erro): **português do Brasil**, por enquanto — ver seção de i18n abaixo para o caminho de internacionalização.
- **Comentários e docstrings de código**: português do Brasil (mantendo o padrão já usado em BrewStation/PyTeca).
- Nunca misturar idioma dentro do mesmo identificador (`fix_cadastro` é proibido; `fix_registration` ou, em comentário, "corrige cadastro").

## Preparação para internacionalização (i18n)

A regra acima ("labels em PT-BR") descreve o **estado inicial do conteúdo**,
não uma limitação estrutural. Desde a primeira versão, todo texto visível ao
usuário final deve ser escrito de forma que **trocar de idioma não exija
alterar código nem regenerar nada via CrudGen** — só adicionar um arquivo de
tradução.

### Regra estrutural (vale desde o dia 1, mesmo rodando só em PT-BR)

- **Nenhuma string visível ao usuário é hardcoded** em template, controller,
  service ou mensagem de validação. Toda label, placeholder, mensagem de
  erro/sucesso e nome de coluna de SmartList é uma **chave de tradução**
  (`translation_key`), nunca o texto final direto.
- O texto em PT-BR não desaparece — ele se torna o **conteúdo do arquivo de
  tradução padrão** (`pt_BR`), que é obrigatório e funciona como fallback se
  uma chave não existir em outro idioma carregado.
- As anotações do CrudGen que hoje recebem texto direto (`@label("Cepa de
  Levedura")`, `Column(label="Data de Validade")`) continuam aceitando texto
  direto na anotação **apenas como conveniência de autoria** — o CrudGen, ao
  gerar o módulo, extrai esse texto automaticamente para a chave de tradução
  correspondente em `pt_BR`, em vez de embuti-lo no HTML/JS gerado.

### Onde os arquivos de tradução vivem

```
core/i18n/
├── pt_BR.json                          ← obrigatório, é o fallback de todo o sistema
└── en_US.json                          ← opcional, exemplo de segundo idioma

addons/addon_[nome]/i18n/
├── pt_BR.json                          ← obrigatório por Addon (gerado pelo CrudGen)
└── [outro_idioma].json                 ← opcional

addons/addon_[nome]/features/feature_[nome]/i18n/
├── pt_BR.json
└── [outro_idioma].json

plugins/plugin_[nome]/i18n/
├── pt_BR.json
└── [outro_idioma].json
```

Cada Addon, Feature e Plugin tem sua **própria pasta de tradução**, isolada
das demais — um Addon pode ser traduzido para `en_US` sem depender de outro
módulo estar traduzido. Isso é o que torna "addons e plugins também
nativamente traduzíveis" verdadeiro: tradução é uma responsabilidade local
do módulo, resolvida pelo Core via merge das chaves em runtime, não um
arquivo gigante central.

### Convenção de chave de tradução

`[modulo].[entidade_ou_tela].[campo_ou_contexto]`

| Chave | Conteúdo em `pt_BR.json` |
|---|---|
| `core.auth.login_label` | "Entrar" |
| `core.admin.users.field_cpf` | "CPF" |
| `brewstation.recipe.field_name` | "Nome da Receita" |
| `brewstation_yeastbank.strain.field_viability` | "Viabilidade" |
| `brewfather_notifier.error.api_timeout` | "Tempo limite ao consultar a API do BrewFather" |

### Resolução de idioma em runtime (regra, não implementação)

- O idioma ativo é uma preferência por usuário (`tesseract_user.locale`,
  default `pt_BR`) e/ou parâmetro de runtime global
  (`i18n.default_locale` em `system_config`).
- Se uma chave não existir no idioma ativo, o Core cai para `pt_BR`
  automaticamente — nunca mostra a chave bruta (`brewstation.recipe.field_name`)
  na tela.
- Adicionar um novo idioma a um Addon existente é **só adicionar o arquivo
  `i18n/[locale].json`** dentro da pasta do módulo — não exige tocar em
  model, controller, template ou regenerar nada via CrudGen.

### O que isso muda nas demais skills

- Skill 01 (pastas/arquivos): toda pasta de módulo passa a ter uma subpasta
  `i18n/` obrigatória, listada na estrutura padrão.
- Skill 03 (manifestos): `addon.json`/`feature.json`/`plugin.json` ganham um
  campo `default_locale` (sempre `"pt_BR"` por enquanto) e, opcionalmente,
  `available_locales` (lista de locales com arquivo de tradução presente).

## Convenção de casing — referência rápida

| Elemento | Casing | Exemplo |
|---|---|---|
| Pasta de Addon | `snake_case`, prefixo `addon_` | `addon_brewstation` |
| Pasta de Plugin | `snake_case`, prefixo `plugin_` | `plugin_brewfather_notifier` |
| Pasta de Feature | `snake_case`, prefixo `feature_` | `feature_yeast_bank` |
| Classe Python | `PascalCase` | `YeastStrain`, `FeatureYeastBank` |
| Tabela | `snake_case`, prefixo tri-nível (ver skill 02) | `tesseract_brewstation_yeast_strain` |
| Coluna | `snake_case` | `created_at`, `table_prefix` |
| Rota web | kebab-friendly, plural | `/brewstation/yeast-strains` |
| Rota API | igual à web, sob `/api/` | `/api/brewstation/yeast-strains` |
| Chave de config (`system_config`) | `snake_case` com namespace por ponto | `versioning.retention_days` |
| Evento (EventBus) | namespace por ponto, presente do indicativo no domínio + passado na ação | `brewstation.device.status_changed` |
| Permissão (RBAC) | `<plural>.<acao>` | `yeast_strains.trash` |

## Regra de ouro transversal

> Se um nome (pasta, tabela, rota, evento, permissão) não segue o padrão
> descrito nas skills 01–03, a geração/PR é rejeitada — não existe exceção
> "por agora resolve assim". Ajustar a skill antes de violar a convenção.
