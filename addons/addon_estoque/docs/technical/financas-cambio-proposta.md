# Integração futura com addon financeiro

## Estado conferido na fase 3 — 07/10/2026

Proposta ainda não implementada. Os modelos atuais de Cotacao e PedidoCompra
não possuem campos de moeda ou taxa; a seleção de moeda não está entregue
nesses documentos. Não interpretar preços estrangeiros como já convertidos.
O primeiro pacote da fase 3 reconcilia documentação; a implementação financeira
depende do contrato de conversão e histórico. Ver
[inventário e sequência](../../../../docs/patches/fase3-inventario-e-sequencia.md).

## Decisão proposta

Cadastrar a moeda no documento de cotação e no pedido de compra. O futuro addon
financeiro mantém moeda de referência por organização, catálogo de moedas
(código ISO 4217 e precisão), cotações cambiais com par de moedas, data de
vigência, fonte e tipo da taxa, além do histórico de alterações. A seleção da
taxa deve gravar no documento uma cópia imutável da taxa efetivamente usada.

Antes de confirmar o recebimento de documento em moeda diferente de BRL,
exigir montante convertido em BRL, taxa positiva, data e origem da taxa.
Somente o custo convertido entra em `Movimentacao` e no custo médio do saldo;
o preço na moeda original e o cálculo da conversão permanecem no documento.
Arredondar o valor monetário segundo a precisão da moeda, mantendo a taxa
com precisão adicional e registrando o critério de arredondamento. A revisão
de taxas futuras não altera lançamentos já contabilizados. Diferenças entre
taxa do recebimento e do pagamento pertencem ao fluxo financeiro.

O addon de estoque deve consumir um resultado de conversão validado por um
serviço público do addon financeiro, sem consultar diretamente suas tabelas.
Notas fiscais, emissão e PDV são outra etapa; esta proposta não define campos
fiscais nem regras tributárias.

## Inspiração

- [Microsoft Business Central: moedas, taxas com vigência e histórico](https://learn.microsoft.com/en-gb/dynamics365/business-central/finance-set-up-currencies).
- [Oracle: taxas diárias por par, data e tipo](https://docs.oracle.com/en/cloud/saas/financials/25a/facsf/currency-rates.html).
