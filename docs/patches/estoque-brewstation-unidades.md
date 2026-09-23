# Estoque e BrewStation: unidades de compra e consumo

## Caso de referência

Para um pacote de 1 kg de cloreto de cálcio comprado por R$ 25,00:

- Cadastre KG como unidade-base, fator 1.
- Cadastre PCT como unidade de compra, fator 1 (um pacote equivale a 1 kg).
- Cadastre G como unidade de consumo, fator 0,001.
- Receber 1 PCT lança 1 kg e custo médio de R$ 25,00/kg.
- Consumir 10 G baixa 0,01 kg e atribui R$ 0,25 ao lote.

O cadastro `Material.unidade_medida` é legado; quando existe uma
`MaterialUnidade` base, a precificação e o consumo usam esta última.
No formulário de material, mantenha os dois nomes coerentes enquanto
o campo legado existir.

## Entregue neste patch

- Prévia do custo da receita com quantidade convertida, saldo disponível,
  falta e aviso de custo incompleto.
- Conversão antes da baixa dos ingredientes; falha de conversão interrompe
  a confirmação. Saídas e marcação do lote compartilham uma transação.
- Conversão de ML para L no cálculo de unidades envasadas.
- Sugestões de unidades/formato, dicas de fator e prévia da conversão no
  recebimento do pedido. Preços em tela identificados como BRL.

## Pendências que exigem decisão de negócio

- O fluxo permanece em BRL. Permitir outras moedas requer taxa de câmbio
  datada e persistida na cotação/pedido, conversão para moeda contábil
  antes de atualizar `Saldo.custo_medio`, e símbolos por documento.
  Não se deve apenas trocar o símbolo exibido para USD/EUR.
- O recebimento histórico incorreto não é alterado por mudar o fator
  cadastrado. Corrija o registro com ajuste contábil de estoque validado
  para o lote, ou estorne e receba novamente por um fluxo apropriado.
- Compras com vários itens ainda fazem commit por linha. A transação
  unificada neste patch cobre somente a confirmação de insumos do lote.
