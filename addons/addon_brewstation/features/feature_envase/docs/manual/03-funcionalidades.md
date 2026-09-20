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

## Precificação

Tela separada (Precificação) para simular quanto uma cerveja deveria
custar para vender, a partir do custo real dos ingredientes:

1. Escolha o Lote e informe a margem de lucro e os percentuais de
   IPI/ICMS desejados.
2. Clique em **Simular** — o sistema mostra o custo de cada
   ingrediente da receita, de onde veio esse preço (compra real já
   registrada, um valor padrão configurado, ou "sem preço" quando
   nenhum dos dois existe), e o valor final sugerido.
3. Ajuste os percentuais e simule de novo quantas vezes quiser — nada
   é gravado ainda nessa etapa.
4. Quando estiver satisfeito, clique em **Confirmar** para gravar esse
   cálculo. Se já existir um Envase para esse lote, é possível
   vincular o cálculo a ele.

Quando um ingrediente aparece como "sem preço", é porque ele nunca foi
comprado (sem histórico no Estoque) e não é malte, lúpulo nem levedura
(que têm um valor padrão configurável — veja "Preço Padrão de Insumo"
em Ingredientes). Vale cadastrar uma compra real ou um preço padrão
para esse item antes de confiar no valor final.
