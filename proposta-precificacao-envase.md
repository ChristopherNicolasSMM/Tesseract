# Proposta — Precificação de Envase (Lote → Custo → Preço de Venda)

> Status: **[ABERTO]** — levantamento feito, schema é rascunho pra
> discussão, nada implementado. Segue o mesmo formato da skill 05
> (proposta antes de código).

## 0. Sobre o bug relatado (lote não listava no Envase)

Confirmado: é exatamente o que o patch pendente corrige —
`envase.lote_id` estava sem `@weak_ref` (Grupo B do relatório
anterior), então o formulário caía no fallback de id numérico cru, o
combo de Lote não aparecia. Assim que aplicar o patch, `lote_id`
passa a resolver contra `BrewSession` (via
`mash_control_lookups.get_session`) e lista normalmente.

## 1. O que o BrewStation (legado, GitHub) já tem

Local: `plugin_integ_bFather` (`model/calculo_envase.py`,
`utils/calculadora.py`, `api/routes/calculos_routes.py`). Mecânica
real (não é só ideia, está implementada e funcional):

```mermaid
flowchart LR
    A[Receita + ingredientes] -->|preco_kg / preco_unidade\ndo cadastro do ingrediente| B[Custo por litro]
    B --> C[Custo base = litro x quantidade_ml]
    C --> D[+ embalagem + impressão + tampinha]
    D --> E[Subtotal]
    E -->|% lucro + % cartão + % sanitização| F[Valor total]
    F -->|% impostos único, sobre o total| G[Valor de venda final]
```

Parâmetros hoje (`CalculoEnvase`, tabela `calculo_envase`):
`valor_litro_base`, `custo_embalagem`, `custo_impressao`,
`custo_tampinha`, `percentual_lucro`, `margem_cartao`,
`percentual_sanitizacao`, `percentual_impostos` (um único percentual
de imposto), `valor_total`, `valor_venda_final`. Vínculo opcional com
`Envase` (`envase_id`, nullable).

**Confirma o que você disse**: é uma base real e utilizável, mas
incompleta em 3 pontos específicos (seção 3).

## 2. O que o Tesseract já tem, que essa feature nova vai usar

| Peça | Onde já existe | Papel na precificação |
|---|---|---|
| "Lote" | `BrewSession` (`feature_mash_control`) | `envase.lote_id` já aponta pra cá (skill 05/02, cross-Feature mesmo Addon) — o Lote **já é** a BrewSession, não precisa de tabela nova só pra isso |
| Ingredientes da receita | `RecipeIngredient` (`feature_mash_control`), com referência fraca a `Material` (`addon_estoque`) | Fonte de quantidade + qual Material foi usado |
| Custo real pago | `ItemPedidoCompra.preco_unitario` (`addon_estoque`) — linha de recebimento já registrada por Material | Isso é **melhor** que o `preco_kg` fixo do legado: em vez de um preço de cadastro estático, dá pra pegar o **último preço realmente pago** (ou uma média) direto do ledger de compras |
| Embalagem | `ItemEnvase` + `Material` (tipo embalagem) | Quantidade e tipo de embalagem usada no envase |
| Tanque/planta | `BrewPlantVessel`, `BrewPlant` | Contexto, não entra direto no cálculo |

## 3. Lacunas reais (o que o legado NÃO tem, que você pediu)

1. **Preço padrão/fallback por Material quando não há preço real
   registrado.** Legado sempre usa `preco_kg` do cadastro (nunca fica
   sem valor, mas também nunca reflete o que foi realmente pago).
   Você quer o inverso: priorizar o preço real pago
   (`ItemPedidoCompra`), e só cair num valor padrão configurável
   (ex.: malte R$25/kg) quando não existir nenhuma compra registrada
   ainda pro Material.
2. **Impostos em linhas separadas (IPI, ICMS, ...), não um percentual
   único.** Legado tem `percentual_impostos` (um número só).
3. **Tela consolidada com abas/cards estilo SAP.** Legado é formulário
   + botão "calcular" separado, sem fluxo de "gerar Lote a partir da
   Receita" dentro do Workspace.

## 4. Perguntas em aberto (preciso da sua decisão antes de desenhar o schema)

| # | Pergunta | Opções |
|---|---|---|
| 1 | Onde mora o "preço padrão" por Material? | (A) campo novo em `Material` (`addon_estoque`) — um padrão por material, simples, mas mistura "cadastro" com "parâmetro de precificação" — (B) tabela nova própria de precificação (`PrecoPadrao` ou similar), fora de `Material` — mais limpo, mas mais uma tabela |
| 2 | "Divergência" do Lote — o que diverge, exatamente? | Você mencionou "informações do lote, divergentes dos dados reais" — preciso saber quais campos (volume real vs. planejado? data real vs. planejada? algo além disso?) pra saber se `BrewSession` já cobre isso (ela já tem campos reais separados dos da receita) ou se falta algo |
| 3 | Onde vive essa Feature nova? | (A) dentro de `feature_envase` (mais próximo do problema, mas mistura "empacotamento" com "precificação") — (B) `feature_precificacao` nova, dentro de `addon_brewstation`, consumindo `feature_envase`+`feature_mash_control`+`addon_estoque` (mais alinhado à skill 00 — um conceito, um módulo) |
| 4 | Impostos: percentual fixo por imposto, ou tabela de alíquotas configurável (por Material/UF/etc.)? | (A) simples — 2-3 campos de percentual (IPI, ICMS) direto no cálculo — (B) tabela de alíquotas própria, reaproveitável — mais correto fiscalmente, mais trabalho |
| 5 | O cálculo salvo (`CalculoEnvase`) fica preso a UM Envase, ou você quer simular preço ANTES de criar o Envase (como o legado permite, `envase_id` nullable)? | Afeta se o fluxo é "cria Envase → calcula" ou "simula → decide → cria Envase" |

## 5. Rascunho de schema (estrawman — só pra dar corpo à discussão, não é decisão)

Assumindo Opção B na pergunta 3 (`feature_precificacao`) e Opção A nas
perguntas 1 e 4 (mais simples, ajusta depois se crescer):

```mermaid
erDiagram
    Envase ||--o| CalculoPrecificacao : "gera"
    BrewSession ||--o{ Envase : "lote de"
    CalculoPrecificacao ||--o{ ItemCustoIngrediente : "detalha"
    Material ||--o{ ItemCustoIngrediente : "referencia (fraca)"

    CalculoPrecificacao {
        int id PK
        int envase_id FK "nullable - simulação antes de criar Envase"
        float custo_ingredientes_total
        float custo_embalagem_total
        float subtotal
        float percentual_lucro
        float valor_ipi
        float valor_icms
        float valor_total
        float valor_venda_final_unitario
        float lucro_estimado
    }
    ItemCustoIngrediente {
        int id PK
        int calculo_id FK
        int material_id "referencia fraca, addon_estoque"
        float quantidade
        float preco_unitario_usado
        string origem_preco "real | padrao"
    }
```

`origem_preco` (`"real"`/`"padrao"`) resolve a pergunta 1 do jeito
mais simples: o service tenta `ItemPedidoCompra` mais recente pro
Material, se não achar cai no valor padrão e marca a linha — assim a
tela mostra pro usuário quais custos são reais e quais são estimados,
sem esconder isso.

## Próximos passos

1. Suas respostas às 5 perguntas da seção 4.
2. Com isso, formalizo o schema definitivo + manifesto da
   Feature (seguindo skills 02/03), ainda como proposta — só depois
   de aprovado é que entra código.
3. Desenho de tela (abas/cards) fica pra depois do schema fechado —
   schema primeiro, UI depois.
