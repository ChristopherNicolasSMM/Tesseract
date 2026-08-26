# 23 — Proposta: Expansão Cadastral do Addon Estoque (Taxonomia, Fracionamento, Fornecedor/Transportadora/Endereço, Compras)

> **Status: [DECIDIDO] — aguardando execução.** Formaliza e fecha o
> item aberto em `BACKLOG.md`, seção "`addon_estoque` — expansão
> cadastral futura (planejado, não iniciado)", registrado em sessão
> anterior com 3 pontos em aberto (mais campos em Fabricante,
> Fornecedores, Sistema de Compras). Decisão estrutural raiz (seção 1)
> resolve todos os três a favor de manter tudo dentro do próprio
> `addon_estoque`, não um Addon novo.
>
> Convenção de status igual à skill 05: **[DECIDIDO]** fechado, pronto
> pra executar quando autorizado. **[EXECUTADO]** já no código.
> **[ABERTO]** ainda sem decisão. Nenhum item deste documento está
> **[EXECUTADO]** ainda — é 100% proposta até a Fase 1 ser autorizada
> (ver seção 7).

---

## 0. Motivação

Sessão de planejamento a pedido do Christopher: o `addon_estoque` hoje
resolve bem "o que é um Material e qual o saldo atual dele", mas não
tem nenhuma das peças em torno da cadeia de suprimento real — de onde
o material veio, a que preço, em que unidade foi comprado vs. em que
unidade é consumido, nem um fluxo de compra estruturado. Também faltava
uma forma correta de guardar mais de um endereço por fornecedor/
transportadora sem recorrer a um padrão polimórfico (que o projeto não
usa em lugar nenhum — ver seção 5).

## 1. Decisão raiz — escopo estrutural

**[DECIDIDO]** Todo o trabalho abaixo entra **dentro do
`addon_estoque` existente** (`table_prefix: "estoque"`) — não nasce um
`addon_compras` novo. Justificativa: o volume e o acoplamento das
entidades novas (Fornecedor/Transportadora/Endereço/PedidoCompra) são
pequenos o bastante, e ficam mais simples com FK real (permitida
dentro do mesmo Addon, skill 02) do que exigindo referência fraca +
service público entre dois Addons desde o primeiro dia. Se o domínio
de compras crescer muito no futuro (múltiplos fornecedores por
cotação, aprovação em várias etapas, etc.), promover para Addon
próprio é um refactor localizado — mesmo padrão de promoção já usado
em `addon_device_manager` (skill 05).

**[DECIDIDO]** Nenhuma tabela nova sai do `addon_estoque`. Toda FK
nova é local ao próprio Addon, sem exceção nesta fase.

### Nota sobre convenção de idioma (flag, não bloqueio)

Skill 00 exige identificador de código em inglês; o `addon_estoque`
real já roda em português nos nomes de classe/tabela (`Material`,
`Movimentacao`, `Categoria`...) — divergência já registrada
informalmente como débito técnico (não é precedente para outros
Addons). Este documento **continua o português** nas entidades novas
(`Fornecedor`, `Transportadora`, `Endereco`, `PedidoCompra`...) por
consistência interna do próprio Addon — mudar de idioma no meio do
mesmo módulo seria pior que manter a inconsistência já existente. Fica
registrado aqui como pendência de resolução formal da skill 00 (criar
uma seção de exceção documentada), não como nova violação silenciosa.

---

## 2. Fase 1 — Taxonomia (`TipoProduto` × `Categoria`)

**[DECIDIDO]** Resolve a sobreposição encontrada entre os dois lookups
existentes, sem apagar dado:

- **`TipoProduto`** passa a ser o eixo de **natureza** do Material.
  Seeds novos (mantendo `"Insumo"` já existente e usado pelo autocreate
  do BrewFather):
  - `Insumo`
  - `Embalagem`
  - `Produto Acabado`
  - `Peça`
  - `Uso e Consumo`
- **`Categoria`** passa a ser a **classificação fina dentro do tipo**
  (ex.: Categoria "Malte" com `tipo_produto_id` apontando para
  "Insumo"). Ganha uma coluna nova:

| Coluna nova em `Categoria` | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `tipo_produto_id` | Integer, FK → `tipo_produto.id` | **Não** (nullable) | Nullable para não quebrar Categorias já cadastradas sem essa classificação; UI deve incentivar o preenchimento, mas não bloquear. |

Nenhuma migration de dado (backfill) prevista nesta fase — Categorias
existentes ficam com `tipo_produto_id=None` até revisão manual (mesmo
espírito do `pendente_revisao` já usado em `Material`).

---

## 3. Fase 2 — Fracionamento (unidade de compra × unidade de consumo)

**[DECIDIDO]** Nova tabela `MaterialUnidade` — permite múltiplas
unidades por Material, com fator de conversão para uma unidade-base
única por Material.

### `MaterialUnidade` (`tesseract_estoque_material_unidade`)

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `material_id` | Integer, FK → `material.id` (CASCADE) | Sim | |
| `unidade` | String(20) | Sim | Ex.: `kg`, `saco25kg`, `caixa12un`, `un`. Livre por enquanto — não é lookup (baixo volume de valores distintos por Material, não justifica tabela própria nesta fase). |
| `fator_para_base` | Float | Sim | Quantas unidades-base equivalem a 1 desta unidade. A unidade-base tem `fator_para_base = 1.0` por definição. |
| `is_unidade_base` | Boolean, default `false` | Sim | Exatamente **um** `true` por `material_id` — índice único parcial `WHERE is_unidade_base = true`, mesmo padrão já usado em `YeastBankConfig` (skill 21). |
| `tipo_uso` | String, `@choices` (`compra` / `consumo` / `ambos`) | Sim, default `ambos` | Filtra qual unidade aparece em qual tela (form de compra vs. form de movimentação manual). |
| `ativo` | Boolean, default `true` | Sim | |

**Regra de ouro desta fase**: `Saldo.quantidade_atual` e
`Movimentacao.quantidade` **sempre** na unidade-base do Material —
nunca a unidade de compra. A conversão acontece uma vez, na entrada do
dado (serviço de compra/movimentação), nunca no ledger em si. Isso
preserva a regra já existente de `Movimentacao` como ledger imutável e
sem ambiguidade de unidade entre linhas.

`Material.unidade_medida` (string livre já existente) **não é
removido** — passa a ser preenchido/sincronizado a partir da unidade
marcada `is_unidade_base=true`, mantido como campo de exibição rápida
para não quebrar telas/relatórios que já o leem hoje.

---

## 4. Fase 3 — Cadastros (Fornecedor, Transportadora, Endereço)

**[DECIDIDO]**

### `Fornecedor` (`tesseract_estoque_fornecedor`)

| Coluna | Tipo | Obrigatória |
|---|---|---|
| `id` | Integer, PK | Sim |
| `razao_social` | String(200) | Sim |
| `nome_fantasia` | String(200) | Não |
| `documento` (CNPJ/CPF) | String(20) | Não |
| `contato_nome` | String(150) | Não |
| `telefone` | String(30) | Não |
| `email` | String(150) | Não |
| `condicao_pagamento_padrao` | String(100) | Não |
| `prazo_entrega_padrao_dias` | Integer | Não |
| `observacoes` | Text | Não |
| `ativo` | Boolean, default `true` | Sim |
| + soft-delete/timestamps padrão | | |

### `Transportadora` (`tesseract_estoque_transportadora`)

| Coluna | Tipo | Obrigatória |
|---|---|---|
| `id` | Integer, PK | Sim |
| `nome` | String(200) | Sim |
| `documento` (CNPJ/CPF) | String(20) | Não |
| `contato_nome` | String(150) | Não |
| `telefone` | String(30) | Não |
| `email` | String(150) | Não |
| `tipo_frete` | String, `@choices` (`proprio` / `terceirizado`) | Sim |
| `observacoes` | Text | Não |
| `ativo` | Boolean, default `true` | Sim |
| + soft-delete/timestamps padrão | | |

### `Endereco` (`tesseract_estoque_endereco`) — dado puro, sem dono

| Coluna | Tipo | Obrigatória |
|---|---|---|
| `id` | Integer, PK | Sim |
| `logradouro` | String(200) | Sim |
| `numero` | String(20) | Não |
| `complemento` | String(100) | Não |
| `bairro` | String(100) | Não |
| `cidade` | String(100) | Sim |
| `estado` (UF) | String(2) | Sim |
| `pais` | String(60), default `"Brasil"` | Sim |
| `cep` | String(15) | Não |
| `ponto_referencia` | String(200) | Não |
| `descricao` | String(150) | Não | Ex.: "Depósito 2", livre |
| + soft-delete/timestamps padrão | | |

### Tabelas de vínculo (uma por entidade dona — evita polimorfismo, ver seção 5)

**`FornecedorEndereco`** (`tesseract_estoque_fornecedor_endereco`) e
**`TransportadoraEndereco`** (`tesseract_estoque_transportadora_endereco`),
mesmo formato nas duas:

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `[entidade]_id` | Integer, FK → `fornecedor.id` / `transportadora.id` (CASCADE) | Sim | |
| `endereco_id` | Integer, FK → `endereco.id` (RESTRICT) | Sim | |
| `tipo_endereco` | String, `@choices` (`cobranca` / `entrega` / `correspondencia` / `faturamento` / `outro`) | Sim | Fechado em código — adicionar tipo novo exige alterar `@choices`, decisão explícita (mais simples que lookup, valores pouco voláteis). |
| `principal` | Boolean, default `false` | Sim | **Um `true` por entidade no total** (não por tipo) — índice único parcial `WHERE principal = true`, mesmo padrão de `is_unidade_base`. |
| `observacoes` | Text | Não | |
| + soft-delete/timestamps padrão | | | |

Um Addon futuro que precisar do mesmo padrão de endereço replica sua
própria tabela `[Entidade]Endereco` local, reaproveitando `Endereco`
via service público do `addon_estoque` (referência fraca — cross-addon,
skill 02) — nunca FK direta de fora do `addon_estoque`.

---

## 5. Por que não polimórfico (`entidade_tipo` + `entidade_id` genérico)

**[DECIDIDO]** Investigação no código real (`model/core/associations.py`,
`Composicao`) mostrou que o projeto **nunca** usa o padrão polimórfico
clássico (uma FK "solta" sem constraint real, resolvida por um
discriminador em string) — todo relacionamento hoje é FK de verdade.
Introduzir isso agora, só para `Endereco`, seria a primeira exceção
silenciosa a essa convenção implícita. Optou-se por manter integridade
referencial real via uma tabela de vínculo por entidade dona, com o
custo de uma tabela extra por dono — aceitável dado o número pequeno de
entidades que precisam disso hoje (2: Fornecedor e Transportadora).

---

## 6. Fase 4 — Sistema de Compras

**[DECIDIDO]** Fluxo: `PedidoCompra` → recebimento (**só total nesta
fase** — recebimento parcial fica para quando o volume real de uso
justificar, mesmo raciocínio de "cresce quando um caso real exigir" já
usado na skill 05, seção 2.2) → gera `Movimentacao` de entrada
automaticamente.

### `PedidoCompra` (`tesseract_estoque_pedido_compra`)

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `numero` | String(30), unique | Sim | Gerado automaticamente (sequencial), editável depois — mesmo padrão de `sku` em `Material`. |
| `fornecedor_id` | Integer, FK → `fornecedor.id` (RESTRICT) | Sim | |
| `transportadora_id` | Integer, FK → `transportadora.id` (RESTRICT) | Não | |
| `status` | String, `@choices` (`rascunho` / `enviado` / `confirmado` / `recebido` / `cancelado`) | Sim, default `rascunho` | Sem estado parcial nesta fase. |
| `data_pedido` | Date | Sim | |
| `data_previsao_entrega` | Date | Não | |
| `condicao_pagamento` | String(100) | Não | Herda de `Fornecedor.condicao_pagamento_padrao` no create, editável depois. |
| `valor_frete` | Float | Não | |
| `observacoes` | Text | Não | |
| + soft-delete/timestamps padrão | | | |

### `ItemPedidoCompra` (`tesseract_estoque_item_pedido_compra`)

Esta tabela **é** o histórico de preços/últimas compras — não existe
tabela separada de "histórico de preço" (evita duplicar dado que já
mora aqui; consulta de "últimas compras deste Material" é uma query
sobre `ItemPedidoCompra` + `PedidoCompra.data_pedido`, sem tabela
nova).

| Coluna | Tipo | Obrigatória | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | |
| `pedido_compra_id` | Integer, FK → `pedido_compra.id` (CASCADE) | Sim | |
| `material_id` | Integer, FK → `material.id` (RESTRICT) | Sim | |
| `material_unidade_id` | Integer, FK → `material_unidade.id` (RESTRICT) | Sim | Unidade de compra escolhida (ex.: `saco25kg`). |
| `quantidade` | Float | Sim | Na unidade de compra, não na base. |
| `fator_conversao_aplicado` | Float | Sim | Snapshot de `MaterialUnidade.fator_para_base` no momento do pedido — se o fator mudar depois, histórico não é reescrito. |
| `quantidade_convertida_base` | Float | Sim | `quantidade × fator_conversao_aplicado`, calculado no save. |
| `preco_unitario` | Float | Sim | Preço por unidade de compra (não por unidade-base). |
| `subtotal` | Float | Sim | Calculado. |
| + soft-delete/timestamps padrão | | | |

### Alterações em tabelas existentes

| Tabela | Coluna nova | Obrigatória | Observação |
|---|---|---|---|
| `Movimentacao` | `fornecedor_id` | Não | FK → `fornecedor.id`, RESTRICT. |
| `Movimentacao` | `pedido_compra_item_id` | Não | FK → `item_pedido_compra.id`, RESTRICT. Rastreabilidade completa: de qual item de qual pedido essa entrada veio. |
| `Movimentacao` | `unidade_original` | Não | String — a unidade em que a compra foi de fato feita (ex.: `saco25kg`), mesmo depois de convertida. |
| `Movimentacao` | `quantidade_original` | Não | Float — quantidade na unidade original, antes da conversão. |
| `Movimentacao` | `fator_conversao_aplicado` | Não | Float — snapshot igual ao de `ItemPedidoCompra`, para auditoria mesmo em movimentações manuais (não só as vindas de `PedidoCompra`). |
| `Saldo` | `ultimo_preco_compra` | Não | Float — cache, atualizado a cada recebimento. |
| `Saldo` | `ultimo_fornecedor_id` | Não | FK → `fornecedor.id`, RESTRICT. |
| `Saldo` | `data_ultima_compra` | Não | Date. |

Todas as colunas novas em `Movimentacao`/`Saldo` são `nullable=True` —
movimentações manuais (ajuste, ou entrada sem passar por
`PedidoCompra`) continuam válidas sem preencher nada disso.

---

## 7. Plano de execução (ordem)

| Fase | Depende de | Status |
|---|---|---|
| 1 — Taxonomia | — | [EXECUTADO] |
| 2 — Fracionamento | — (independente da Fase 1, mas patch único conforme pedido) | [EXECUTADO] |
| 3 — Cadastros + Endereço | — | [EXECUTADO] |
| 4 — Compras | Fases 2 e 3 (usa `MaterialUnidade` e `Fornecedor`) | [DECIDIDO], não iniciada |

**Decisão de entrega**: Fases 1 e 2 saem juntas no **mesmo patch**
(autorização já dada para essa combinação). Fases 3 e 4 ficam para
sessões seguintes, patches separados, cada uma com autorização própria
— não incluídas no patch desta rodada.

## 8. Atualização de documentação relacionada

- `BACKLOG.md`, seção "`addon_estoque` — expansão cadastral futura
  (planejado, não iniciado)": marcar como resolvida por esta skill,
  substituindo os 3 itens em aberto por link para este documento.
- `addons/addon_estoque/docs/technical/04-modelo-de-dados.md`: será
  atualizado a cada fase entregue (não de uma vez só), seguindo o
  padrão já usado nesse documento (nota de "atualizado nesta sessão"
  no topo).
- `addons/addon_estoque/docs/technical/06-manutencao-e-expansao.md`:
  referenciar este documento como o desenho vigente, substituindo os
  3 bullets antigos.
