# Fase 10 — Designer v2 (Ações, Dados e Substituição de CrudGen)

> Planejamento consolidado desta rodada de conversa. Vira Skill 16
> (`docs/skills/16-designer-acoes-e-dados.md`) quando formalizada, e
> entra no BACKLOG.md como Fase 10, seguindo a mesma convenção de
> status das skills 05+ (`[DECIDIDO]`/`[EXECUTADO]`/`[ABERTO]`).

## Decisões já fechadas nesta rodada

1. Ações que tocam dado/API sempre executam via **proxy server-side**
   do Tesseract — nunca client-side quando há credencial envolvida.
2. Arquitetura em duas camadas: **catálogo de tipos de Ação** em
   código (`core/actions_catalog.py`, sem tabela — mesmo padrão de
   `rules_catalog.py`) + **Ação de Dado com tabela própria**
   (`tesseract_designer_data_action`, análoga a `ODataConnection`) só
   para ações que tocam API/dado. Ações sem segredo (`navigate`,
   `show_message`, `set_component_value`, `toggle_component`) ficam
   embutidas em `DesignerComponent.events` (JSON já existente).
3. Fonte de dado para substituir tela CrudGen: **só via conexão
   OData** — inclusive para dado local do próprio Tesseract, que
   precisa virar também **provedor** OData (hoje só existe o lado
   consumidor, Fase 8).
4. Exposição de entidade via OData local é **opt-in por entidade**
   (não automático) — nova anotação `@odata_expose` (Camada 2, mesmo
   padrão de `@permission`).
5. Controle de acesso a entidade exposta / Ação de Dado: reaproveita
   o mecanismo **já existente** (`permission_required` resolvido via
   Role, `User.has_permission()`) — sem permissão por usuário
   individual (não existe hoje, não entra nesta fase). Sem
   `permission_required` configurado = público.
6. Tipos de componente desta leva: **Tier 1 + Tier 2** do
   `mapeamento_niceadmin_designer.md` já entregue —
   `select`/`checkbox`/`radio`/`form_container`/`datagrid` (Tier 1) +
   `card`/`alert`/`badge`/`progress_bar`/`list` (Tier 2). Tier 3
   (`tabs`/`accordion`/`chart`/`rich_text`/`carousel`/modal-como-ação)
   fica para depois — **assumindo que você não pediu ajuste depois do
   "Topa?"; sinalizo aqui pra confirmar antes de eu travar isso no
   Patch 3.**
7. Substituição de tela CrudGen: `DesignerPage.replaces_entity_key` +
   `replaces_view` + checkbox `replace_in_menu`. Troca acontece **só
   no item de menu** (`Transaction.route`) — rota original do CrudGen
   nunca é tocada, sempre acessível direto pra debug. Limitação aceita:
   links internos que apontam direto pra rota do CrudGen (`url_for(...)`)
   continuam levando pra tela antiga.

## Decisão nova que apareceu ao planejar o Patch 1 — preciso do seu sinal

**HTTP loopback vs. chamada direta pro provedor OData local.**

`ODataConnectionManager` (Fase 8) faz requisição HTTP de verdade
(`urllib`) contra a `base_url` da conexão. Se um componente do
Designer for buscar dado local através desse mesmo caminho, toda
`datagrid`/`select` ligado a uma entidade do próprio Tesseract faria
uma requisição HTTP do Tesseract pra ele mesmo a cada carregamento de
página — funciona, mas é round-trip desnecessário (latência, uso de
worker/thread extra, e frágil se a `base_url` configurada não bater
com o host real em produção atrás de proxy reverso).

Proposta: o provedor OData local expõe endpoint HTTP de verdade
(`/api/odata-provider/...`, pra ferramenta externa consumir se quiser
— isso não muda), **mas** a execução de uma Ação de Dado que aponta
pra uma conexão marcada como "local" pula o HTTP e chama a função
Python do provedor **direto, em processo** — mesmo contrato de
entrada/saída (mesmo formato de metadata, mesmo `query()`/`patch()`),
só sem o round-trip de rede. Do ponto de vista do Designer (a tabela
`tesseract_designer_data_action`, a UI, o evento) é **exatamente o
mesmo mecanismo único** que você pediu — a otimização é interna,
invisível pra quem está montando a página.

Preciso da sua confirmação pra travar isso no Patch 1 (schema da
`ODataConnection` ganha uma flag `is_local`, sinalizando esse atalho).

---

## Roadmap de patches (git am, um de cada vez — mesmo fluxo de sempre)

| Patch | Escopo | Depende de |
|---|---|---|
| **1** | Schema completo (sem UI de edição ainda): `tesseract_designer_data_action`, `ODataConnection.is_local` (+ seed da conexão local), `@odata_expose` (anotação, sem endpoint ainda), `DesignerPage.replaces_entity_key`/`replaces_view`/`replace_in_menu`. Migrations + models + testes de schema puro. | — |
| **2** | Provedor OData local: endpoint `/api/odata-provider/$metadata` + `query()`/`patch()` (HTTP real, pra uso externo) + atalho direto-em-processo (Patch 1). Metadata enriquecida com enum/weak-ref (formato JSON custom já reconhecido pelo parser da Fase 8). | 1 |
| **3** | `core/actions_catalog.py` + engine de execução de Ação (server-side, endpoint `/admin/designer/component/<id>/fire-event` ou similar) + UI no editor pra configurar `events` de um componente (hoje campo morto). | 1, 2 |
| **4** | Tier 1 de componente: `select`, `checkbox`, `radio`, `form_container`, `datagrid` — model (`COMPONENT_TYPES`, defaults), editor (paleta+propriedades), runtime (renderização + bind real via Ação de Dado). | 2, 3 |
| **5** | Tier 2 de componente: `card`, `alert`, `badge`, `progress_bar`, `list` — mesma trinca model/editor/runtime, mais simples que o Patch 4 (sem bind obrigatório a registro único). | 4 (reaproveita infra de bind) |
| **6** | Substituição de tela CrudGen: checkbox `replace_in_menu` conectado de fato — resolver de `Transaction.route` (skill 10) checando `DesignerPage` publicada na sincronização. | 1 |
| **7** | Documentação: Skill 16 formalizada, `docs/technical/`/`docs/manual/` do Designer (skill 04) atualizados, manual de uso completo do Designer (pedido seu, cobrindo os 3 trilhos: Ações, Dados, Substituição). | 1–6 |

Cada patch continua seguindo o fluxo de sempre: implementação →
pytest completo → `git format-patch` → validação em clone limpo →
entrega → você aplica e dá `git push` antes do próximo.

---

## Detalhe do Patch 1 (pronto pra implementar assim que confirmado)

### Tabela nova — `tesseract_designer_data_action`

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `name` | String(100) | Nome de exibição, único |
| `description` | String(300), nullable | |
| `connection_id` | Integer, FK → `tesseract_odata_connection.id` | Nunca nulo — mesmo pra dado local (aponta pra conexão local seedada) |
| `entity_name` | String(100) | Nome da entidade/EntitySet dentro da conexão |
| `operation` | String(20) | `query` \| `create` \| `update` \| `delete` |
| `static_params` | JSON, default `{}` | Parâmetros fixos (ex.: `$filter` sempre aplicado, sem depender do componente) |
| `permission_required` | String(150), nullable | Role — igual `DesignerPage.permission_required`; `NULL` = público |
| `created_by_user_id` | Integer, FK → `tesseract_user.id`, nullable | |
| `created_at`/`updated_at` | DateTime | |

### `ODataConnection` — coluna nova

| Coluna | Tipo | Observação |
|---|---|---|
| `is_local` | Boolean, default `False` | Marca a conexão auto-seedada que representa o próprio Tesseract — habilita o atalho direto-em-processo (decisão pendente acima) |

Seed no boot (idempotente, mesmo padrão de `system_config`/catálogo de
Transação): uma linha `ODataConnection(name="Tesseract (local)",
is_local=True, base_url="/api/odata-provider")`.

### `DesignerPage` — colunas novas

| Coluna | Tipo | Observação |
|---|---|---|
| `replaces_entity_key` | String(150), nullable | Referência fraca (nunca FK — skill 02), mesmo padrão de `FieldRule.entity_key` |
| `replaces_view` | String(20), nullable | `manage` \| `detail` |
| `replace_in_menu` | Boolean, default `False` | Checkbox — só tem efeito se `replaces_entity_key` estiver preenchido |

### Anotação nova — `@odata_expose` (`annotations/__init__.py`)

```python
@odata_expose(entity_name="yeast_strain", permission_required=None)
class YeastStrain(db.Model):
    ...
```

Mesmo padrão de `@permission` (`_odata_expose` como atributo de
classe + `get_odata_expose_meta(cls)` pra extrair). Sem endpoint
ainda neste patch — só a marcação, pro Patch 2 consumir.

### Testes do Patch 1

Só schema — sem endpoint, sem UI: migration up/down válida, defaults
corretos, `is_local` seedado uma única vez (idempotência do boot),
`@odata_expose` marca e recupera metadata corretamente em pelo menos
uma entidade real de teste.

---

## Documentação a atualizar (por patch, não só no final)

Por pedido seu ("todas as decisões devem atualizar a documentação"),
cada patch acima **inclui**, não deixa pra depois:
- Skill 16 ganha a seção correspondente ao que foi decidido naquele
  patch (mesmo padrão incremental da skill 05/10).
- `docs/technical/04-modelo-de-dados.md` e `docs/manual/` do Designer
  (skill 04) atualizados a cada patch que muda schema ou comportamento
  visível ao usuário final.
- BACKLOG.md ganha a seção "Fase 10" logo no Patch 1, marcada
  `(em andamento)`, e cada patch subsequente marca seus itens como
  `[x]` — sem esperar o fechamento de tudo pra registrar.
