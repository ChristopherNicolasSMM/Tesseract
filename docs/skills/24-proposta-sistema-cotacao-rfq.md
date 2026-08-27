# 24 — Proposta: Sistema de Cotação (RFQ) — Addon Estoque

> **Status: [EXECUTADO] — todas as fases (6.1, 6.2, 6.3) entregues.**
> Continuação direta da skill 23 (Fases 1–5, todas entregues) — o item
> "Vamos planejar depois um sistema de cotação" ficou registrado no
> BACKLOG como decisão futura; esta skill formalizou esse planejamento
> e o executou por completo. Convenção de status igual às skills
> 05/23: **[DECIDIDO]** fechado, pronto pra executar. **[EXECUTADO]**
> já no código. **[ABERTO]** sem decisão.

---

## 0. Motivação e referência

Inspirado no fluxo de RFQ (Request for Quotation) do SAP MM: uma
cotação é enviada a **múltiplos fornecedores em paralelo** pro mesmo
processo de compra — cada fornecedor responde com seu próprio
documento (mesma estrutura de um Pedido de Compra: cabeçalho + itens),
todos ligados por um número de "cotação coletiva" pra comparação. Após
comparar preço/prazo por item, as linhas vencedoras (podendo estar
divididas entre fornecedores diferentes) viram Pedido(s) de Compra.

Decisão raiz herdada da skill 23: **tudo dentro do próprio
`addon_estoque`**, sem Addon novo — mesmo raciocínio (volume pequeno,
FK real mais simples que referência fraca entre Addons).

---

## 1. Decisões de sessão

**[DECIDIDO]** Estrutura: um cabeçalho de `Cotacao` **por fornecedor**
convidado, agrupados por um `ProcessoCotacao` comum (não um cabeçalho
único com N fornecedores dentro) — mesmo padrão SAP.

**[DECIDIDO]** Comparação é **por item**, não por cotação inteira — o
processo pode fechar com Malte do Fornecedor A e Lúpulo do Fornecedor
B na mesma rodada.

**[DECIDIDO]** Conversão pra Pedido de Compra é **manual** (botão
"Gerar Pedido", ação separada) — nunca automática ao marcar um item
como vencedor. Dá pra revisar antes de confirmar.

**[DECIDIDO]** `Cotacao`/`ItemCotacao` **não têm tela CRUD própria**
(mesma decisão da Fase 5) — API REST existe, a tela é o detalhe do
`ProcessoCotacao` desenhado com abas/grid, e a comparação é uma tela
própria desenhada.

---

## 2. Modelagem

> **[CORRIGIDO — achado do Christopher, sessão pós-Fase 6.3]** O
> desenho original desta seção tinha `ItemCotacao` com
> `material_id`/`material_unidade_id`/`quantidade` próprios — cada
> fornecedor redigitava o mesmo Material. Corrigido: o item pedido
> (Material+quantidade) agora vive em `ItemProcessoCotacao`, definido
> **uma vez** por processo; `ItemCotacao` só responde
> `preco_unitario` (e opcionalmente `quantidade_ofertada`, se o
> fornecedor não confirma a quantidade pedida) pra um
> `item_processo_cotacao_id` já existente. Ver seção 2.1 abaixo pro
> desenho atualizado; o texto original da seção 2 (histórico) fica
> preservado logo em seguida, riscado, pra registro de raciocínio.

## 2.1. Modelagem corrigida

```
ProcessoCotacao
├── ItemProcessoCotacao — o item PEDIDO, uma vez por processo
│   └── material_id, material_unidade_id, quantidade_desejada
│
└── Cotacao (por fornecedor, inalterado)
    └── ItemCotacao — a RESPOSTA de preço pra um ItemProcessoCotacao
        └── item_processo_cotacao_id FK (não mais material_id solto)
        └── preco_unitario, quantidade_ofertada (opcional)
        └── fator_conversao_aplicado/subtotal/selecionado_como_vencedor
            (inalterados, só a origem do fator/quantidade mudou — vem
            do ItemProcessoCotacao via unidade definida lá)
```

`ItemCotacao` ganhou `@property` de conveniência (`material_id`,
`material_unidade_id`, `quantidade`) que delegam pro
`ItemProcessoCotacao` pai — para código que só precisa ler esses
valores (ex.: `gerar_pedidos_de_cotacao()`), a mudança é transparente.

`selecionar_item_cotacao_vencedor()` ficou **mais simples**: agrupa
por `item_processo_cotacao_id` (FK real) em vez de nome de Material —
não precisa mais de JOIN com `Cotacao` pra filtrar.

`ItemProcessoCotacao` também não tem tela própria (mesma decisão já
tomada pra `Cotacao`/`ItemCotacao`) — gerenciado dentro da aba
"Cotações" do detalhe de `ProcessoCotacao` (seção "Itens Pedidos").

## 2.2. Modelagem original (histórico, substituída pela seção 2.1)

```
ProcessoCotacao          (tesseract_estoque_processo_cotacao)
├── numero (auto, COT-000001), descricao, status, data_abertura,
│   data_limite_resposta, observacoes
│
└── Cotacao               (tesseract_estoque_cotacao)
    ├── processo_cotacao_id FK, fornecedor_id FK, numero (auto)
    ├── status (rascunho/enviada/respondida/recusada)
    ├── condicao_pagamento, prazo_entrega_dias, observacoes
    │
    └── ItemCotacao        (tesseract_estoque_item_cotacao)
        ├── cotacao_id FK, material_id FK, material_unidade_id FK
        ├── quantidade, preco_unitario
        ├── fator_conversao_aplicado / quantidade_convertida_base /
        │   subtotal — calculados no hook, mesmo padrão de
        │   ItemPedidoCompra (skill 23, Fase 4)
        └── selecionado_como_vencedor (bool, default false)
```

### `ProcessoCotacao` (`tesseract_estoque_processo_cotacao`)

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `numero` | String(30), unique | Não | Auto (`COT-000001`), mesmo padrão de `PedidoCompra.numero` (hook, editável depois) |
| `descricao` | String(200) | Sim | Ex.: "Cotação Malte Pilsen — Safra 2026" |
| `status` | `@enum_field` (`aberto` / `comparado` / `finalizado` / `cancelado`) | Sim, default `aberto` | `finalizado` = já gerou todos os Pedidos de Compra pretendidos; não bloqueia gerar mais depois se sobrar item sem vencedor |
| `data_abertura` | Date | Sim | |
| `data_limite_resposta` | Date | Não | |
| `observacoes` | Text | Não | |
| + soft-delete/timestamps padrão | | | |

### `Cotacao` (`tesseract_estoque_cotacao`)

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `processo_cotacao_id` | FK → `processo_cotacao.id` (CASCADE) | Sim | |
| `fornecedor_id` | FK → `fornecedor.id` (RESTRICT) | Sim | |
| `numero` | String(30), unique | Não | Auto (`COT-000001-A`, sufixo por fornecedor — ver seção 4) |
| `status` | `@enum_field` (`rascunho` / `enviada` / `respondida` / `recusada`) | Sim, default `rascunho` | |
| `condicao_pagamento` | String(100) | Não | |
| `prazo_entrega_dias` | Integer | Não | |
| `observacoes` | Text | Não | |
| + soft-delete/timestamps padrão | | | |

Índice único parcial: no máximo uma `Cotacao` não-deletada por
`(processo_cotacao_id, fornecedor_id)` — não faz sentido convidar o
mesmo fornecedor duas vezes no mesmo processo.

### `ItemCotacao` (`tesseract_estoque_item_cotacao`)

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `cotacao_id` | FK → `cotacao.id` (CASCADE) | Sim | |
| `material_id` | FK → `material.id` (RESTRICT) | Sim | |
| `material_unidade_id` | FK → `material_unidade.id` (RESTRICT) | Sim | |
| `quantidade` | Float | Sim | Na unidade de compra, mesmo raciocínio de `ItemPedidoCompra` |
| `fator_conversao_aplicado` | Float | Calculado (hook) | Snapshot |
| `quantidade_convertida_base` | Float | Calculado (hook) | |
| `preco_unitario` | Float | Sim | |
| `subtotal` | Float | Calculado (hook) | |
| `selecionado_como_vencedor` | Boolean, default `false` | Sim | Setado pela tela de comparação (ação dedicada, não edição direta do campo) |
| + soft-delete/timestamps padrão | | | |

**Regra de vencedor único por Material**: no máximo um
`ItemCotacao.selecionado_como_vencedor = true` por
`(processo_cotacao_id, material_id)` — atravessa `Cotacao`
(fornecedores diferentes), então **não dá pra ser índice único de
banco** (índice único só enxerga colunas da própria tabela +
join implícito não existe em constraint). Validado na ação de
seleção (service), não em constraint — documentado aqui pra não ser
esquecido numa migration futura achando que "faltou o índice".

---

## 3. Fluxo (preparação pra `docs/technical/03-fluxos.md` quando formalizado)

```mermaid
sequenceDiagram
    actor U as Comprador
    participant PC as ProcessoCotacao
    participant C as Cotacao (por fornecedor)
    participant IC as ItemCotacao
    participant PComp as PedidoCompra

    U->>PC: cria processo, define Materiais/quantidades desejadas
    U->>C: cria uma Cotacao por fornecedor convidado
    U->>IC: preenche itens pedidos em cada Cotacao (preco_unitario inicialmente vazio/estimado)
    Note over U,C: fornecedor responde por fora do sistema (email/telefone) - comprador digita o preço retornado
    U->>C: status = respondida, preco_unitario preenchido por item
    U->>PC: tela de Comparação - por Material, vê preço de cada Cotacao respondida
    U->>IC: marca selecionado_como_vencedor = true (um por Material)
    U->>PC: botão "Gerar Pedido" (manual)
    PC->>PComp: agrupa itens vencedores por fornecedor, cria 1 PedidoCompra por fornecedor
    Note over PComp: PedidoCompra nasce em rascunho - fluxo da Fase 4 (confirmar -> receber) continua valendo
```

---

## 4. Numeração da `Cotacao` (achado a decidir na implementação)

`Cotacao.numero` precisa ser único mas relacionado ao
`ProcessoCotacao` pai — proposta: `{numero_do_processo}-{sufixo_letra}`
(ex.: processo `COT-000001` gera cotações `COT-000001-A`,
`COT-000001-B`, uma por fornecedor, na ordem de criação). Calculado no
hook de `Cotacao` (mesmo mecanismo de `PedidoCompra.numero`), lendo o
número do `ProcessoCotacao` pai + contando quantas `Cotacao` já
existem naquele processo.

---

## 5. Telas (mesmo padrão desenhado da Fase 5 — skill 23, seção 8)

- **`ProcessoCotacao`**: tela de lista simples (CrudGen) + detalhe com
  abas — Cabeçalho / Cotações (grid de `Cotacao` por fornecedor,
  adicionar convite em modal) / Comparação (grid por Material, uma
  linha por Cotacao que cotou aquele Material, botão "Selecionar como
  vencedor" por linha) / ação "Gerar Pedido".
- **`Cotacao`/`ItemCotacao`**: sem tela própria — API REST só,
  consumida pela aba "Cotações" (visão resumida) e por uma tela de
  detalhe de Cotacao específica (abre a partir do grid) pra editar os
  itens daquela cotação (grid de Itens, mesmo padrão de
  `ItemPedidoCompra` na Fase 5 — busca de Material, unidade
  dependente).

---

## 6. Plano de execução (ordem)

| Fase | Entrega | Depende de |
|---|---|---|
| 6.1 | `ProcessoCotacao`/`Cotacao`/`ItemCotacao` — models, migration, CrudGen básico, numeração automática, cálculo de subtotal/fator (hooks) — **[EXECUTADO]** | Fase 4 (usa `Fornecedor`/`MaterialUnidade`) |
| 6.2 | Tela de Comparação (desenhada, grid Material × Cotacao) + ação "selecionar vencedor" (valida único vencedor por Material) — **[EXECUTADO]** | 6.1 |
| 6.3 | Ação "Gerar Pedido" (agrupa vencedores por fornecedor → cria `PedidoCompra`/`ItemPedidoCompra`) — **[EXECUTADO]** | 6.2, Fase 4 |

## 9. Fase 6.3 — Ação "Gerar Pedido" (execução real)

**[EXECUTADO]** `estoque_service.gerar_pedidos_de_cotacao(processo_cotacao_id)`:
busca todos os `ItemCotacao` vencedores do processo ainda não
convertidos (`pedido_compra_item_id IS NULL`), agrupa por fornecedor
(via `Cotacao.fornecedor_id`) e cria **um `PedidoCompra` por
fornecedor vencedor** (nasce em `status="rascunho"`, revisável antes
de confirmar — fluxo da Fase 4 continua valendo a partir daí). Passa
pelos services (`PedidoCompraService`/`ItemPedidoCompraService`), não
INSERT direto — reaproveita os hooks já existentes (número automático,
cálculo de fator/subtotal).

**Coluna nova** (schema, migration `fd143ed5695c`): `ItemCotacao.
pedido_compra_item_id` (FK nullable → `item_pedido_compra.id`) —
rastreia se o item vencedor já virou linha de pedido, evitando
duplicar se "Gerar Pedido" for chamado mais de uma vez. Item já
convertido não pode mais ter o vencedor alterado (trava no service,
`ValueError`).

`ProcessoCotacao.status` vira `"finalizado"` automaticamente ao
gerar — não bloqueia gerar mais depois se sobrar item vencedor sem
pedido (ex.: novo Material vencido depois de já ter gerado uma
primeira leva).

Cada fase entra em patch separado, mesmo fluxo já validado (proposta →
autorização → migration com FK conferida à mão → testes → `git am
--keep-cr` em clone limpo → entrega).
