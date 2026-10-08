# Integração futura com addon financeiro

## Estado conferido na fase 3 — 08/10/2026

Fundação inicial implementada no ambiente de geração; integração com Estoque
ainda proposta. Os modelos atuais de Cotacao e PedidoCompra
não possuem campos de moeda ou taxa; a seleção de moeda não está entregue
nesses documentos. Não interpretar preços estrangeiros como já convertidos.
O primeiro pacote da fase 3 reconcilia documentação; a implementação financeira
depende do contrato de conversão e histórico. Ver
[inventário e sequência](../../../../docs/patches/fase3-inventario-e-sequencia.md).

## Decisões confirmadas — continuação da fase 3

Usuário escolheu moeda-base por organização, addon financeiro primeiro e
identidade de organização compartilhada no Core. O estoque atual é global por
material: segregação/contexto de organização precisa de contrato posterior
antes de receber custos em bases monetárias diferentes. Não atribuir históricos
nem User.empresa automaticamente a uma organização. Fundação de identidade:
[organizações Core](../../../../docs/patches/fase3-organizacoes-core.md).
Organizações aplicadas e validadas localmente, com primeira empresa criada.
O pacote inicial seguinte implementa addon financeiro, catálogo, política
monetária explícita e quantização Decimal. Taxas direcionais e conversões com snapshots imutáveis já foram entregues
no Financeiro; versões explícitas de precisão/arredondamento também.
A integração desses resultados com o recebimento do Estoque permanece pendente. Ver [pacote inicial](../../../../docs/patches/fase3-financeiro-organizacoes-getcep.md).

## Contexto organizacional preparatório

Decisão validada: catálogo de materiais compartilhado; compras, saldos e
custos separados por organização. O pacote de contexto permite vínculo
explícito e imutável de pedidos em rascunho e processos antes de convidar
fornecedores. Nenhum histórico recebe organização automaticamente. A entrega
seguinte habilita ledger/saldos Decimal, propagação atômica de organização e
recebimento mediante avaliação monetária congelada. Os preços persistidos
em documentos antigos continuam Float; a adaptação não recupera precisão perdida. Ver
[recebimento e limites](../../../../docs/patches/fase3-estoque-organizacional-recebimento.md).

## Desenho proposto após as decisões

Cadastrar a moeda no documento de cotação e no pedido de compra. O futuro addon
financeiro mantém moeda de referência por organização, catálogo de moedas
(código ISO 4217 e precisão), cotações cambiais com par de moedas, data de
vigência, fonte e tipo da taxa, além do histórico de alterações. A seleção da
taxa deve gravar no documento uma cópia imutável da taxa efetivamente usada.

Antes de confirmar o recebimento em moeda diferente da moeda-base explícita
da organização, exigir montante convertido nessa base, taxa positiva, data e
origem da taxa. BRL não é uma base global presumida.
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
