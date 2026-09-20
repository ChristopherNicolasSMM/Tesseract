# 07 — Menu: Personalização (Ordem/Colapso) e Hierarquia (Árvore N-níveis)

> **Status: EXECUTADO.** Esta skill funde os antigos documentos
> `07-menu-personalizacao.md` e `10-menu-hierarquico.md` — a fusão
> não muda nenhuma regra, só reorganiza (consolidação Fase 1,
> 2026-09). Motivo da fusão: os dois cobriam a mesma superfície (item
> de menu) em dois momentos — 07 nasceu de "carregar com itens
> colapsados e poder ordenar" (grupos de topo, string plana); 10
> evoluiu isso pra árvore de N níveis e, na própria seção 6 do
> original, já reescrevia o schema de 07. Manter os dois separados
> exigia ler um pra entender o que o outro supera.
>
> Convenção de status usada neste documento: **[DECIDIDO]** (fechado,
> pronto pra ser executado quando autorizado) / **[EXECUTADO]**
> (decidido e já implementado) / **[ABERTO]** (ainda precisa de
> decisão) / **[PENDENTE-SKILL]** (decidido aqui, exige ajuste em
> outra skill antes de executar sem conflito).
>
> Histórico de origem (contexto, não é regra em si): 07 nasceu de bug
> reportado sobre colapso/ordenação de menu, expondo lacuna nas skills
> 00–04. 10 nasceu de pedido de navegação em árvore de profundidade
> arbitrária, motivado por escala (menu ficaria grande demais conforme
> mais Addons/Features entrassem); confirmado no código real que
> `Transaction.group` era string plana, sem `parent_id`/`order_index`.
> Revisão de 2026-07-07 fechou três achados adicionais (§6.1, §6.2,
> §8.1) e obsoletou uma proposta de sessão anterior (§10).

---

## 0. Decisão raiz

**[EXECUTADO]** `Transaction` deixou de usar `group` (string plana) e
ganhou `parent_id` (FK pra si mesma, nullable = raiz) + `order_index`
(Integer) — um "grupo" é um nó real da árvore, sem rota própria
(`route` nullable), com filhos via `parent_id`. **Profundidade
ilimitada**, sem validação de máximo, mesma tabela em todos os níveis.

**[EXECUTADO]** A coluna `group` foi removida por completo (não
mantida como legado); os 5 pontos de uso migrados para `parent_id`/
`parent_code` (ver §3–§4).

**[EXECUTADO]** As duas telas de personalização (`/admin/menu-settings`
e `/perfil/menu-preferencias`) operam sobre a árvore, com drag-and-drop
aninhado em qualquer nível (não só grupos de topo).

**[DECIDIDO]** Além da estrutura em árvore, dois estados de
apresentação continuam existindo, cada um com override em dois níveis
(padrão global do admin + override opcional por usuário — ver §1):

| Estado | O que controla |
|---|---|
| Ordem dos nós, por pai | Em que ordem os filhos de um mesmo nó aparecem |
| Nós colapsados por padrão | Se um nó específico começa fechado ou aberto |
| Sidebar inteira aberta/fechada | Modo compacto vs. expandido — independente dos dois acima |

---

## 1. Onde cada nível de customização vive

| Nível | Papel | Onde |
|---|---|---|
| Autoria (valor de fábrica, por módulo) | Ordem relativa sugerida, label, ícone, posição na árvore (`parent_code`) | Catálogo Python do módulo (`get_transactions()`) ou auto-descoberta (skill 09) |
| Padrão global (admin, runtime) | Override do valor de fábrica, aplicado a todo usuário sem override próprio | `system_config` (skill 03, seção 5) |
| Override individual (usuário, runtime) | Sobrepõe o padrão global só para aquele usuário | `tesseract_user_menu_preference` (§2.2) |

Resolução em runtime, nesta ordem de prioridade: override do usuário →
padrão global (`system_config`) → valor de autoria (catálogo). Nível
ausente cai para o próximo.

`menu_config.json` (autoria de UI simples — label/ícone/ordem
sugerida, skill 01) continua existindo na raiz de Addon/Feature/Plugin
para o valor de fábrica; nunca é o lugar do override de runtime.

---

## 2. Schema de dados

### 2.1 `Transaction` (Core, prefixo fixo — skill 02)

```python
class Transaction(db.Model):
    __tablename__ = "tesseract_transaction"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    icon = db.Column(db.String(50), default="bi-app")

    route = db.Column(db.String(300), nullable=True)   # nullable: nó-pasta não navega
    route_params = db.Column(db.JSON, default=lambda: {})

    parent_id = db.Column(db.Integer, db.ForeignKey("tesseract_transaction.id"), nullable=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    permission_required = db.Column(db.String(150), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_standard = db.Column(db.Boolean, default=True, nullable=False)
    source_module = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    children = db.relationship(
        "Transaction",
        backref=db.backref("parent", remote_side=[id]),
        order_by="Transaction.order_index",
    )
```

FK interna Core→Core (`parent_id` → `tesseract_transaction.id`),
sempre permitida (skill 02).

### 2.2 `tesseract_user_menu_preference` (Core, prefixo fixo — skill 02)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `user_id` | Integer, FK → `tesseract_user.id` | Sempre permitido (skill 02) |
| `order_overrides_json` | JSON, nullable | `{parent_code_ou_null: [code_filho, ...]}` — ordenação por pai, qualquer nível. `null` = herda o padrão global |
| `collapsed_nodes_json` | JSON, nullable | Lista de `code`, qualquer nível. `null` = herda o padrão global |
| `sidebar_collapsed` | Boolean, nullable | Estado da sidebar inteira. `null` = herda o padrão global |
| `updated_at` | DateTime | |

Chaves equivalentes em `system_config` (skill 03, `[namespace].[parametro]`)
para o padrão global do admin: `core.menu.order_overrides`,
`core.menu.collapsed_nodes`, `core.menu.default_sidebar_collapsed`.

> Nota histórica: a v1 (skill 07 original) usava `group_order_json`/
> `collapsed_groups_json` — listas simples de nomes de grupo de topo,
> porque só existia um nível. Vira `dict` por pai quando a árvore
> (§0) entra, único formato válido hoje.

---

## 3. Migração de dados (`group` → árvore)

**[EXECUTADO]** Uma migration só, schema + dado:

1. **Schema**: adiciona `parent_id`/`order_index`, torna `route`
   nullable, remove `group`.
2. **Dado**: para cada valor distinto de `group` já existente (lido
   antes do `DROP COLUMN`), cria uma linha-pasta nova
   (`code=TX_GROUP_<SLUG>`, `route=NULL`, `is_standard=True`,
   `parent_id=NULL`) e reatribui `parent_id` de toda Transação que
   tinha aquele `group`.

Convenção de slug: `TX_GROUP_<LABEL_SLUGIFICADO>` — maiúsculo, espaços
viram `_`, acentos removidos (ex.: "Ferramentas de Desenvolvimento" →
`TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO`).

**[PENDENTE-SKILL → skill 03]** Esta foi a primeira migration de
**dado** (não só estrutural) do projeto — falta adenda formal em skill
03 documentando que migrations de dado são permitidas e devem ficar no
mesmo arquivo da parte estrutural (schema primeiro, dado depois),
nunca em dois arquivos separados para uma mudança logicamente única.

---

## 4. Catálogo (`core/transactions_catalog.py`)

**[EXECUTADO]** Toda entrada troca `"group": "X"` por `"parent_code":
"TX_GROUP_X"`; grupos viram entradas do próprio catálogo:

```python
CORE_TRANSACTIONS = [
    {
        "code": "TX_GROUP_ADMIN", "label": "Admin", "route": None,
        "parent_code": None, "icon": "bi-gear-fill", "is_standard": True,
    },
    {
        "code": "TX_ADMIN_ROLES", "label": "Roles", "parent_code": "TX_GROUP_ADMIN",
        "route": "/admin/roles/", "icon": "bi-people-fill",
        "permission_required": "admin", "is_standard": True,
    },
]
```

`order_index` = posição na lista Python, salvo `"order_index": N`
explícito no dict (tem prioridade sobre a posição implícita).

---

## 5. Sync — duas passadas

**[EXECUTADO]** `sync_transaction()` (código lidera, banco segue —
skill 00) roda em duas passadas:

1. Upsert de todo nó (sem tocar `parent_id`/`order_index` ainda).
2. Resolve `parent_code → parent_id` por `code` (estável) e aplica
   `order_index` (posição na lista ou override explícito).

Duas passadas tornam a sincronização independente da ordem de
declaração no catálogo, e permitem um Addon apontar `parent_code` para
um grupo declarado pelo Core.

---

## 6. Renderização (`templates/core/base.html`)

**[EXECUTADO]** Macro Jinja recursiva nomeada (`render_menu_nodes`,
chamando a si mesma) — equivalente na prática ao modificador nativo
`recursive` do Jinja2, sem lib nova. Cada nível ganha seu próprio
`collapse` do Bootstrap, aninhado dentro do pai.

### 6.1 Bug corrigido — accordion não aninhava por nível

**Causa raiz**: todo `<ul class="nav-content collapse">`, em qualquer
profundidade, usava o mesmo `data-bs-parent="#sidebar-nav"` fixo — o
Bootstrap trata todo elemento com o mesmo `data-bs-parent` como do
mesmo accordion, então abrir um nó em qualquer profundidade fechava
qualquer outro nó aberto em **qualquer** lugar da árvore.

**[EXECUTADO]** `render_menu_nodes` ganhou parâmetro
`parent_container_id` (inicial: `"sidebar-nav"`; em cada chamada
recursiva: `"node-" ~ tx.code` do nível atual) — cada `<ul>` aponta
para o container imediatamente acima, não mais para o global.

### 6.2 `core.menu.icon_max_depth`

**[EXECUTADO]** A partir do nível `N` (inclusive), o item renderiza
sem ícone, só o label. Reaproveita o contador de profundidade que a
macro recursiva já calcula (§8.1).

| Campo | Valor |
|---|---|
| Chave (`system_config`) | `core.menu.icon_max_depth` |
| Tipo | `int` |
| Default | `-1` (sentinela = "sem corte", todo nível mostra ícone — preserva o visual atual até um admin configurar um valor real) |
| Nível raiz | `0` |

Lido via `SystemConfig.get(...)` direto no `context_processor`
(`core/app_factory.py`) — sem seed row obrigatória.

---

## 7. Adenda skill 09 (auto-descoberta) — `parent_code` para Transação automática

**[EXECUTADO]** `auto_transactions_from_models()` gera `parent_code`
em vez de `group=module.label`, criando (ou reaproveitando) uma pasta
própria por módulo:

- Código da pasta auto-gerada: `TX_GROUP_AUTO_<ADDON_OU_FEATURE_MAIUSCULO>`
  — namespace `TX_GROUP_AUTO_` separado de `TX_GROUP_` (manual), para
  evitar colisão entre uma Transação automática e um grupo curado à
  mão. Quem quiser unificar sobrescreve `get_transactions()` apontando
  `parent_code` direto pro grupo manual.
- A pasta é criada (via `sync_transaction`) na primeira vez que algum
  model daquele módulo é auto-descoberto, com `label=module.label`.

### 7.1 Correção — catálogos manuais ainda flat (Addon com múltiplas Features)

**Achado**: a adenda acima cobre só o caminho de auto-descoberta. Os
catálogos manuais (`get_transactions()` escrito à mão) não seguiam a
mesma regra — cada Feature de `addon_brewstation` declarava
`"parent_code": None` para o próprio grupo, sem `AddonBrewstation`
declarar `get_transactions()` nenhum. Resultado real: as 5 Features
(`mash_control`, `yeast_bank`, `envase`, `ingredientes`, `brew_father`)
apareciam soltas na raiz, sem pasta "BrewStation" agrupando-as.

**[EXECUTADO]** `AddonBrewstation.get_transactions()` declara um
único nó-pasta raiz (`TX_GROUP_BREWSTATION`, `parent_code: None`), e
cada uma das 5 Features passou `parent_code` para apontar para ele —
sem mudar a estrutura interna de cada Feature.

**Escopo**: só `addon_brewstation`, único Addon com mais de uma
Feature. `addon_estoque`/`addon_device_manager` não precisam do
wrapper (Addon sem Feature própria usa o grupo raiz que já teria como
nível 1 real). Regra geral para manifestos futuros: Addon com Feature
própria declara seu grupo raiz; Addon sem Feature não precisa.

---

## 8. Adenda: `admin_transactions.py` — CRUD manual vira tree-aware

**[EXECUTADO, detalhe de UI ficou por conta da implementação]**
- Campo de texto livre "grupo" virou `<select>` de "pai" — lista todo
  nó-pasta existente (`route IS NULL`), mais "sem pai / raiz".
- Listagem ganhou indentação/coluna de caminho completo (ex.: `Admin >
  Roles`) para mostrar profundidade.
- Export CSV/XLSX: coluna `group` virou `parent_code` (ou caminho
  completo).
- Regra de edição já existente (campos code-sourced só permitem toggle
  `is_active`) não mudou — só o campo de agrupamento.

### 8.1 Indicador de nível + promover/rebaixar

**[EXECUTADO] Indicador de nível**: sem schema novo — profundidade é
calculada na renderização (a macro recursiva já sabe em que nível
está, incrementa 1 a cada chamada). Dado derivado, nunca persistido.

**[EXECUTADO] Promover/rebaixar existe nas duas telas, com efeito
diferente por baixo**:

| Tela | O que "promover/rebaixar" faz de verdade |
|---|---|
| `/perfil/menu-preferencias` (pessoal) | Só a exibição individual — grava em `order_overrides_json` do próprio usuário. Não toca `Transaction.parent_id`. Sem permissão além de login. |
| `/admin/menu-settings` — exibição padrão | Mesma coisa, grava no padrão global (`system_config`). Também não toca `parent_id`. |
| `/admin/menu-settings` — estrutura real (transação manual) | Muda `Transaction.parent_id` de verdade, afeta todo mundo, permanente — via os endpoints novos abaixo. Só disponível para transação manual. |

**Regra de ouro**: o mesmo rótulo de botão aparece nas duas telas, mas
o efeito por baixo depende do mecanismo — nunca o mesmo endpoint. A UI
marca a diferença visualmente (cor/ícone) para não sugerir que é a
mesma ação.

**Convenção de movimento** (vale para os dois mecanismos):
- **Promover** ("outdent"): o item vira irmão do seu pai atual,
  inserido logo depois dele na lista de filhos do avô. Item já na raiz
  não tem para onde promover — botão desabilitado.
- **Rebaixar** ("indent"): o item vira o último filho do irmão
  imediatamente anterior na lista atual. Item que já é o primeiro da
  lista não tem irmão anterior — botão desabilitado.

**[EXECUTADO]** Rebaixar para dentro de um irmão que **tem rota
própria** (não é pasta) é rejeitado com mensagem, nunca convertido
silenciosamente em pasta — um nó com `route` preenchido é folha pura
na renderização (`controller/core/pages.py`, que só recursiona em nós
sem rota); filhos por baixo dele ficariam órfãos/invisíveis. Para
rebaixar algo para dentro de um item hoje-folha, o usuário edita e
deixa a rota em branco primeiro (vira pasta explicitamente).

**Endpoints** (mesma permissão `admin` e mesma trava de
transação code-sourced que `update`/`delete` já aplicam):
- `POST /admin/transactions/<id>/promote`
- `POST /admin/transactions/<id>/demote`

Reordenação dos irmãos afetados (pai antigo e novo) é renumerada por
completo a cada chamada — mais simples e robusto que encaixar um
`order_index` fracionário no meio de uma lista existente.

---

## 9. RBAC

| Permissão | Escopo |
|---|---|
| `system_config.menu_settings` | Editar o padrão global (`core.menu.*`) e a estrutura real via `admin_transactions.py` |
| `admin` | Endpoints `promote`/`demote` (mesma trava de `update`/`delete` de Transação) |
| — (nenhuma permissão nova) | Editar a própria preferência (`/perfil/menu-preferencias`) não exige nada além de estar autenticado — escopo já restrito ao próprio `user_id` |

---

## 10. Pendências e itens fechados por obsolescência

- [ABERTO] Nenhuma pendência de arquitetura restante — remoção de
  `group`, escopo das duas telas, profundidade ilimitada, indicador de
  nível e promover/rebaixar foram todos fechados.
- Detalhe de implementação (não bloqueia): slugify do código de pasta
  migrado (§3) — função simples (maiúsculo, não-alfanumérico vira `_`,
  colapsa `_` repetido), sem biblioteca nova.

### `Transaction.parent_manually_set` — proposta obsoleta

Um item de backlog anterior a esta skill propunha um campo booleano
`parent_manually_set` para `resolve_transaction_parents()` pular
transações com override manual, evitando que o boot sobrescrevesse
reorganização feita pelo admin.

**Achado**: não se aplica mais — `admin_transactions.py`
(`_is_code_sourced()`) já bloqueia por completo qualquer edição de
`parent_id`/label/rota/ícone em transação vinda do código (form de
editar e `promote()`/`demote()`), com mensagem explícita. Só
transação `source_module="manual"` tem a própria estrutura alterável,
e essa nunca é tocada por `sync_transaction()`/
`resolve_transaction_parents()`. O cenário que a proposta tentava
resolver não existe — editar estrutura de item vindo do código nunca
foi permitido, e a checagem ocorre antes da escrita chegar ao banco.
**Campo não implementado** — item fechado por obsolescência.

### Conflito de teste encontrado e resolvido na implementação de §7.1

`tests/test_menu_grouped_by_feature.py` tinha um teste
(`test_nao_existe_mais_grupo_brewstation_generico`) afirmando o
oposto de §7.1 — que nenhuma pasta "BrewStation" deveria existir. Era
de uma fase anterior à árvore `parent_id`: com `group` como string
plana, havia um bucket genérico "BrewStation" duplicando transações
que também apareciam soltas por Feature, e a correção da época foi
remover o genérico em favor do específico (sem hierarquia real
disponível para ter as duas coisas). Com `parent_id`, o dilema não
existe mais — uma pasta raiz pode conter as 5 pastas de Feature como
filhas sem duplicar nada. Teste atualizado para a invariante nova
(existe exatamente uma pasta "BrewStation", e é a raiz).
