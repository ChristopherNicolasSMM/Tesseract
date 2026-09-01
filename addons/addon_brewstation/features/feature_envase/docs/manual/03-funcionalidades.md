# 03 — Funcionalidades (Envase)

## Envases

Registro de um empacotamento — qual lote foi envasado, em que Material
resultante (produto acabado) e em quantos litros. A partir disso, o
sistema calcula:

- **Quantas unidades** o envase representa (litros ÷ Volume Real do
  Material resultante).
- **Baixa automática** dos componentes de embalagem, resolvidos pela
  Composição do Material resultante — nenhuma digitação linha a linha.
- **Custo real de industrialização**: a parte da cerveja (rateada do
  custo total de insumo da receita pelo volume produzido) mais o custo
  de cada componente de embalagem (pelo custo médio de cada um no
  Estoque).

## Confirmar Ingredientes (na tela da Sessão de Brassagem)

Antes — ou no momento — de envasar, o sistema precisa saber quanto
custaram os insumos da receita (malte, lúpulo, levedura) usados
naquele lote, pra poder ratear isso no custo do envase. O botão
**Confirmar Ingredientes**, na tela do lote, faz essa baixa de estoque
e trava o custo — só acontece uma vez por lote. Se você for direto pro
Envase sem confirmar antes, o sistema confirma sozinho automaticamente
nesse momento.

## Itens de Envase (histórico)

Telas antigas de Envase guardavam os componentes de embalagem um por
um, em "Itens de Envase". Essa tabela continua existindo só como
histórico do que já foi registrado antes — novos Envases não criam
mais itens aqui, o componente vem da Composição do Material
resultante (ver acima).
