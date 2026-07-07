# 10 — Menu Hierárquico (N níveis)

> **Status: EXECUTADA (2026-07-02), com revisão em 2026-07-07.** Nasceu
> de um pedido direto de navegação em árvore (`addon > sub item > sub
> item do sub item`, profundidade arbitrária), motivado por
> preocupação real de escala — sem isso, o menu ficaria grande demais
> pra navegar conforme mais Addons/Features forem entrando.
>
> Investigação no código real (`model/core/transaction.py`,
> `core/transactions_sync.py`, `controller/core/admin_transactions.py`)
> confirmou que `Transaction.group` hoje é só uma **string plana** —
> um único nível de agrupamento, sem `parent_id`, sem `order_index`,
> ordem sempre alfabética. Uso real de `.group` encontrado em 5
> arquivos: `controller/core/pages.py`,
> `controller/core/admin_transactions.py` (tela CRUD completa, com
> campo de texto livre "grupo"), `services/core/menu_preference_service.py`,
> `core/cli.py`, `core/transactions_sync.py`.
>
> **Revisão de 2026-07-07** (retomada de um item de backlog de sessão
> anterior — "`Transaction.parent_manually_set`"): investigação no
> código real de `admin_transactions.py` mostrou que essa proposta
> ficou **obsoleta** — a implementação real já resolveu o problema de
> um jeito mais simples (§9). Nessa mesma revisão, três achados novos
> ganharam decisão: hierarquia Addon→Feature ainda flat nos catálogos
> reais (§7.1), bug real confirmado no accordion aninhado (§5.1), e
> `core.menu.icon_max_depth` (§5.2) — todos **[DECIDIDO], ainda não
> implementados** nesta revisão (fase de documentação apenas).
>
> Mesmo peso normativo das demais skills. Convenção de status (igual
> skill 05-09): **[DECIDIDO]** / **[ABERTO]** / **[PENDENTE-SKILL]**.

---

## 0. Decisão raiz

**[DECIDIDO]** `Transaction` ganha `parent_id` (FK pra si mesma,
nullable — `NULL` = raiz) e `order_index` (Integer). Um "grupo" deixa
de ser string solta e vira **nó real da árvore**: uma Transação sem
rota (`route` passa a ser nullable), só container, com filhos via
`parent_id`. Profundidade **ilimitada, sem validação de máximo**
(decisão confirmada) — mesma tabela, sem esquema por nível.

**[DECIDIDO]** A coluna `group` é **removida por completo** (não
mantida como legado) — migra os 5 arquivos que a usam hoje, incluindo
a tela `admin_transactions.py`, que passa a ter seletor de pai em vez
de campo de texto livre (seção 7).

**[DECIDIDO]** As duas telas de personalização de menu (admin
`/admin/menu-settings` e pessoal `/perfil/menu-preferencias`, skill
07) viram árvore juntas nesta rodada — nenhuma fica pra depois.

---

## 1. Schema — `Transaction`

```python
class Transaction(db.Model):
    __tablename__ = "tesseract_transaction"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    icon = db.Column(db.String(50), default="bi-app")

    route = db.Column(db.String(300), nullable=True)          # ALTERADO: nullable=True (nó-pasta não navega)
    route_params = db.Column(db.JSON, default=lambda: {})

    parent_id = db.Column(db.Integer, db.ForeignKey("tesseract_transaction.id"), nullable=True)  # NOVO
    order_index = db.Column(db.Integer, nullable=False, default=0)                                # NOVO

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
    # `group` REMOVIDA — era db.Column(db.String(50), ...)
```

FK interna Core→Core (`parent_id` → `tesseract_transaction.id`),
sempre permitida (skill 02).

---

## 2. Migração de dados (schema + dado, não só schema)

**[DECIDIDO]** Uma migration só, com duas partes:

1. **Schema**: adiciona `parent_id`/`order_index`, torna `route`
   nullable, remove `group`.
2. **Dado**: para cada valor **distinto** de `group` já existente em
   produção/dev (lido antes do `DROP COLUMN`), cria uma linha-pasta
   nova (`code=TX_GROUP_<SLUG>`, `route=NULL`, `is_standard=True`,
   `parent_id=NULL`) e reatribui `parent_id` de toda Transação que
   tinha aquele `group` pra apontar pra ela.

**[PENDENTE-SKILL → skill 03]** Isso é a primeira **migration de
dado** do projeto (todas as anteriores eram só estruturais) — skill 03
nunca cobriu esse caso. Adenda a fazer: seção nova em "Argumentos da
CLI do CrudGen" ou parágrafo próprio documentando que migrations de
dado (não só `ALTER TABLE`) são permitidas e como devem ser
estruturadas (schema primeiro, dado depois, no mesmo arquivo de
migration — nunca dois arquivos separados pra uma mudança que é
logicamente uma coisa só).

**Convenção do slug do código gerado**: `TX_GROUP_<LABEL_SLUGIFICADO>`
— maiúsculo, espaços viram `_`, acentos removidos. Ex.: "Ferramentas
de Desenvolvimento" → `TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO`.

---

## 3. Catálogo (`core/transactions_catalog.py`)

**[DECIDIDO]** Toda entrada troca `"group": "X"` por `"parent_code":
"TX_GROUP_X"`. Grupos viram entradas do próprio catálogo:

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
    # ...
]
```

`order_index` = posição na lista Python (implícito) — sem campo
explícito no dict, salvo quando precisar forçar uma ordem específica
(nesse caso, `"order_index": N` explícito no dict tem prioridade sobre
a posição na lista).

---

## 4. Sync — duas passadas

**[DECIDIDO]** `sync_transaction()` (código lidera, banco segue,
skill 00) ganha uma segunda passada:

1. Upsert de todo nó (sem tocar `parent_id`/`order_index` ainda).
2. Resolve `parent_code → parent_id` por `code` (estável) pra cada um,
   e aplica `order_index` (posição na lista ou override explícito).

Duas passadas tornam a sincronização independente da ordem de
declaração no catálogo, e permitem um Addon apontar `parent_code` pra
um grupo declarado pelo Core (ex.: uma Feature nova entrando dentro de
`TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO`, que é do Core).

---

## 5. Renderização (`core/base.html`)

**[DECIDIDO]** Vira macro Jinja recursiva — `{% for item in nodes
recursive %}` é suporte nativo do Jinja2 pra árvore, sem lib nova.
Cada nível ganha seu próprio `collapse` do Bootstrap aninhado dentro
do pai.

**Nota de divergência encontrada na revisão de 2026-07-07**: o código
real (`templates/core/base.html`) implementa a recursão como macro
nomeada chamando a si mesma (`render_menu_nodes`), não com o
modificador nativo `recursive` do Jinja2 — equivalente na prática,
sem impacto. Mas a segunda parte da frase acima ("cada nível ganha seu
próprio collapse... aninhado dentro do pai") **não é verdade no código
real** — ver §5.1.

### 5.1 [DECIDIDO — pendente de implementação] Bug real: accordion não aninha por nível

**Causa raiz confirmada** (`templates/core/base.html`, dentro da macro
`render_menu_nodes`): todo `<ul class="nav-content collapse">`, em
**qualquer** profundidade de recursão, usa o mesmo
`data-bs-parent="#sidebar-nav"` fixo. O plugin de collapse do
Bootstrap trata todo elemento que compartilha o mesmo `data-bs-parent`
como pertencente ao **mesmo** accordion — então abrir um nó em
qualquer profundidade fecha qualquer outro nó aberto em **qualquer**
outro lugar da árvore, não só os irmãos do mesmo nível/mesmo pai. Isso
confirma (não é mais suspeita) o comportamento relatado: mexer num
nível 2 colapsa o nível 1.

**Decisão**: `data-bs-parent` de cada `<ul>` deve apontar pro **id do
`<ul>` do nível imediatamente acima**, não pro `#sidebar-nav` global.
Isso exige passar o id do container pai como parâmetro na chamada
recursiva da macro (hoje `render_menu_nodes(nodes)` só recebe a lista
de nós — passa a receber também `parent_container_id`, com
`"sidebar-nav"` como valor inicial na primeira chamada, e
`"node-" ~ tx.code` do nível atual em cada chamada recursiva
subsequente).

### 5.2 [DECIDIDO — pendente de implementação] `core.menu.icon_max_depth`

**Semântica decidida**: a partir do nível `N` (inclusive), o item
renderiza **sem ícone** — só o texto do label. Níveis `0` até `N-1`
continuam mostrando ícone normalmente. Reaproveita o mesmo contador de
profundidade que a macro recursiva já calcula pra outros fins (§8.1,
"Indicador de nível" — dado derivado, nunca persistido, incrementado a
cada chamada recursiva).

| Campo | Valor |
|---|---|
| Chave (`system_config`, skill 03) | `core.menu.icon_max_depth` |
| Tipo | `int` |
| **Default proposto** | `-1` (sentinela explícito = "sem corte", todo nível mostra ícone — preserva o comportamento visual atual até um admin configurar um valor real; skill 03 exige valor-padrão explícito, nunca `None` silencioso, e `-1` cumpre isso sem mudar nada visualmente por padrão) |
| Nível raiz | `0` (mesma convenção do indicador de nível, §8.1) |

Se este default (`-1` = sem corte) não for o que você tinha em mente,
sinalizar antes da implementação — é a única peça desta decisão que
não veio de um pedido explícito seu, foi inferida pra manter
compatibilidade visual por padrão.

---

## 6. Adenda skill 07 (menu personalizado) — schema muda de lista pra árvore

**[PENDENTE-SKILL → skill 07, aplicada junto com esta skill]**

| Campo (skill 07 original) | Campo novo | Motivo |
|---|---|---|
| `group_order_json: list[str]` (nomes de grupo) | `order_overrides_json: dict[str\|null, list[str]]` | Ordenação agora é **por pai** (`{parent_code_ou_null: [code_filho, ...]}`), não uma lista global de um nível só |
| `collapsed_groups_json: list[str]` (nomes de grupo) | `collapsed_nodes_json: list[str]` (códigos, qualquer nível) | Colapso agora existe em qualquer nível da árvore, não só na raiz |
| `sidebar_collapsed: bool` | Sem mudança | Continua sendo estado da sidebar inteira, não da árvore |

Mesma prioridade de resolução de sempre (usuário → global → ordem
original do catálogo) — só o formato do dado que muda.

**[DECIDIDO]** As duas telas de personalização (`/admin/menu-settings`
e `/perfil/menu-preferencias`) passam a renderizar árvore com
drag-and-drop aninhado — mesmo mecanismo nativo HTML5 já usado
(`draggable`, `dragover`/`drop`), só que operando em qualquer nível,
não só na lista de grupos de topo.

---

## 7. Adenda skill 09 (auto-descoberta) — `parent_code` pra Transação automática

**[PENDENTE-SKILL → skill 09, aplicada junto com esta skill]**
`auto_transactions_from_models()` hoje gera `group=module.label`.
Passa a gerar `parent_code`, criando (ou reaproveitando, se já
existir) uma pasta própria por módulo:

- **Código da pasta auto-gerada**: `TX_GROUP_AUTO_<ADDON_OU_FEATURE_MAIUSCULO>`
  — namespace `TX_GROUP_AUTO_` **separado** de `TX_GROUP_` (manual),
  de propósito: evita uma Transação automática colidir sozinha com um
  grupo curado à mão. Quem quiser unificar sobrescreve
  `get_transactions()` apontando `parent_code` pro grupo manual
  diretamente, em vez de usar o default.
- A pasta auto-gerada é criada (via `sync_transaction`, mesma função)
  na primeira vez que algum model daquele módulo é auto-descoberto,
  com `label=module.label` (mesma convenção já usada pro `group`
  antes desta skill).

### 7.1 [DECIDIDO — pendente de implementação] Catálogos manuais ainda flat — falta o nível Addon

**Achado da revisão de 2026-07-07**: a adenda acima cobre só o caminho
de auto-descoberta (skill 09). Os catálogos **manuais** (`get_transactions()`
escrito à mão, caso de toda Feature de `addon_brewstation` hoje) não
seguem a mesma regra — cada uma declara `"parent_code": None` pro
próprio grupo raiz, e `AddonBrewstation` não declara `get_transactions()`
nenhum. Resultado real confirmado no código: as 5 Features
(`mash_control`, `yeast_bank`, `envase`, `ingredientes`, `brew_father`)
aparecem como 5 itens soltos na raiz do menu — nenhuma pasta
"BrewStation" as agrupa, mesmo todas pertencendo ao mesmo Addon.

**Decisão**: `AddonBrewstation.get_transactions()` passa a declarar um
único nó-pasta raiz:

```python
{"code": "TX_GROUP_BREWSTATION", "label": "BrewStation", "parent_code": None, "route": None, "icon": "..."}
```

e cada uma das 5 Features troca `"parent_code": None` pelo próprio
grupo raiz por `"parent_code": "TX_GROUP_BREWSTATION"` — sem mudar
mais nada na estrutura interna de cada Feature (suas próprias
sub-transações continuam apontando pro grupo da Feature, não
diretamente pro grupo do Addon). Mecanismo de resolução já suporta
isso sem mudança (§4 — duas passadas, independente de ordem de
declaração, já pensado justamente pra permitir um módulo apontar
`parent_code` pra grupo declarado por outro).

**Escopo da correção**: só `addon_brewstation`, único Addon com mais
de uma Feature hoje. `addon_estoque`/`addon_device_manager` não têm
esse problema — Addon sem Feature própria não precisa de wrapper
extra (adicionar um nível "Estoque > Estoque" seria redundante, não
resolve nada). Regra geral pra manifestos futuros: Addon com Feature
própria declara seu grupo raiz; Addon sem Feature usa o grupo raiz que
já teria de qualquer forma como o nível 1 real.

---

## 8. Adenda: `admin_transactions.py` — CRUD manual vira tree-aware

**[DECIDIDO, detalhe de UI fica pra implementação]**
- Campo de texto livre "grupo" no form de criar/editar vira `<select>`
  de "pai" — lista todo nó-pasta existente (`route IS NULL`), mais
  opção "sem pai / raiz".
- Listagem principal ganha indentação ou coluna "caminho completo"
  (ex.: `Admin > Roles`) pra mostrar profundidade.
- Export CSV/XLSX: coluna `group` vira `parent_code` (ou caminho
  completo — decisão de implementação, não de arquitetura).
- Regra de edição existente (campos code-sourced só permitem toggle
  `is_active`, skill já documentada no próprio arquivo) não muda —
  só o campo de agrupamento em si.

---

## 8.1 Adenda: indicador de nível + promover/rebaixar

> Nasceu de feedback direto sobre a tela `/admin/menu-settings`
> (ainda em uso, print real anexado à conversa): faltava indicador de
> profundidade e forma de reorganizar sem depender só de arrastar
> entre listas — pedido natural depois que a árvore ganhou
> profundidade arbitrária (seção 0).

**[DECIDIDO] Indicador de nível**: sem schema novo — profundidade é
calculada na hora da renderização (a macro recursiva já sabe em que
nível está, incrementa 1 a cada chamada). Puro dado derivado, nunca
persistido.

**[DECIDIDO] Promover/rebaixar existe nas DUAS telas (admin e
pessoal), mas com efeito diferente por baixo — é a mesma decisão que
já separava as duas desde a skill 07, só reafirmada aqui**:

| Tela | O que "promover/rebaixar" faz de verdade |
|---|---|
| `/perfil/menu-preferencias` (pessoal) | Só a **exibição individual** — grava em `order_overrides_json` do próprio usuário (`tesseract_user_menu_preference`), exatamente como o drag-and-drop já fazia. Não toca `Transaction.parent_id`. Nenhuma permissão além de login (skill 07 §4, inalterado). |
| `/admin/menu-settings` — parte de **exibição padrão** | Mesma coisa, só que grava no padrão global (`system_config`) em vez da preferência pessoal. Também não toca `parent_id`. |
| `/admin/menu-settings` — parte de **estrutura real** (linhas de Transação manual) | Muda `Transaction.parent_id` de verdade, afeta todo mundo, permanente — submete pros mesmos endpoints novos do `admin_transactions.py` (abaixo). Só disponível pra transação manual (mesma trava de sempre). |

**Regra de ouro desta adenda**: o mesmo rótulo de botão ("Promover"/
"Rebaixar") aparece nas duas telas, mas o efeito por baixo depende de
qual mecanismo está por trás — **nunca o mesmo endpoint**. A UI marca
visualmente a diferença (cor/ícone distintos) pra não passar a
impressão de que é a mesma ação.

### Convenção de movimento (vale para os dois mecanismos — exibição e estrutura real)

- **Promover** (sobe um nível, "outdent"): o item passa a ser irmão do
  seu pai atual, inserido logo depois dele na lista de filhos do avô.
  Item que já está na raiz (sem pai) não tem pra onde promover — botão
  desabilitado.
- **Rebaixar** (desce um nível, "indent"): o item passa a ser o último
  filho do irmão imediatamente anterior a ele na lista atual. Item que
  já é o primeiro da própria lista não tem irmão anterior — botão
  desabilitado.

**[EXECUTADO — achado na implementação]** Rebaixar pra dentro de um
irmão que **tem rota própria** (não é pasta) é **rejeitado com
mensagem**, nunca convertido silenciosamente em pasta. Motivo: um nó
com `route` preenchido é tratado como folha pura na renderização
(`controller/core/pages.py`) — se ganhasse filhos por baixo dos panos,
esses filhos ficariam órfãos/invisíveis na sidebar, já que o
código só recursiona em nós sem rota. Pra rebaixar algo pra dentro de
um item hoje-folha, o usuário precisa primeiro editá-lo e deixar a
rota em branco (vira pasta explicitamente), depois rebaixar.

### Endpoints novos em `admin_transactions.py` (estrutura real)

**[DECIDIDO]** Dois endpoints novos, além do form de editar que a
seção 8 já previa — mesma permissão (`admin`) e mesma trava de
transação code-sourced que `update`/`delete` já aplicam:

- `POST /admin/transactions/<id>/promote`
- `POST /admin/transactions/<id>/demote`

Reordenação dos irmãos afetados (pai antigo e pai novo) é
renumerada por completo a cada chamada — mais simples e robusto que
tentar encaixar um `order_index` fracionário no meio de uma lista já
existente.

---

## 9. Pendências desta skill

- [ABERTO] Nenhuma pendência de **arquitetura da árvore em si**
  restante — as três decisões que estavam em aberto (remoção de
  `group`, escopo das duas telas, profundidade ilimitada) foram todas
  fechadas na rodada inicial, e o indicador de nível + promover/
  rebaixar (seção 8.1) foram fechados numa rodada seguinte.
- Detalhe de implementação (não bloqueia): geração exata do slug do
  código de pasta migrado (seção 2) — usar uma função de slugify
  simples (maiúsculo, troca não-alfanumérico por `_`, colapsa
  `_` repetido) na hora do código, sem biblioteca nova.

### `Transaction.parent_manually_set` — proposta de sessão anterior, obsoleta

Um item de backlog de sessão anterior a esta (ainda não implementado
na época) propunha um campo `Transaction.parent_manually_set`
(Boolean) pra fazer `resolve_transaction_parents()` pular transações
com override manual de estrutura, evitando que o boot sobrescrevesse
uma reorganização feita pelo admin.

**Achado na revisão de 2026-07-07**: essa proposta não se aplica mais
— quando a árvore foi implementada de fato (seções 0–8 acima), o
problema foi resolvido de um jeito estruturalmente mais simples e sem
nenhuma flag nova: `admin_transactions.py` (`_is_code_sourced()`)
**bloqueia por completo** qualquer edição de `parent_id` (e de
label/rota/ícone) em transação vinda do código, tanto no formulário de
editar quanto em `promote()`/`demote()`, com mensagem de erro
explícita ao usuário. Só transação `source_module="manual"` pode ter
a própria estrutura alterada — e essa nunca é tocada por
`sync_transaction()`/`resolve_transaction_parents()`, que só
processam o que está literalmente presente no catálogo Python. Não
existe, portanto, o cenário que a proposta original tentava resolver
("admin editou a estrutura, boot sobrescreveu") — porque editar
estrutura de item vindo do código nunca foi permitido, e a checagem já
é feita antes da escrita chegar ao banco, não depois. **Não implementar
o campo `parent_manually_set`** — item fechado por obsolescência, não
por implementação.

### Itens novos desta revisão — [DECIDIDO], pendentes de implementação

Três achados confirmados no código real nesta revisão (2026-07-07),
com decisão já tomada, aguardando autorização explícita pra
implementar (fase de documentação apenas até aqui):

1. **§5.1** — bug real do accordion (`data-bs-parent` fixo em
   `#sidebar-nav` em todo nível) — mexer num nível 2 colapsa o nível
   1. Fix: `data-bs-parent` aponta pro `<ul>` do nível imediatamente
   acima, não pro `#sidebar-nav` global.
2. **§7.1** — catálogos manuais de Feature ainda flat (`parent_code:
   None` em todas as 5 Features de `addon_brewstation`, sem grupo
   Addon-pai). Fix: `TX_GROUP_BREWSTATION` novo em
   `AddonBrewstation.get_transactions()`, 5 Features apontam
   `parent_code` pra ele.
3. **§5.2** — `core.menu.icon_max_depth` (`system_config`, int,
   default proposto `-1` = sem corte) — a partir do nível `N`, item
   renderiza sem ícone.

