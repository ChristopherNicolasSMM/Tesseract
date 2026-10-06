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

## Confirmação de envase e correções

O formulário de Envases usa os combos de busca do CrudGen para Lote e Material resultante. Ao criar, valida volume positivo, confirma ingredientes pendentes e registra o envase junto com todas as baixas de embalagem em uma única transação. Uma falha cancela tudo, inclusive a baixa de ingredientes disparada automaticamente. O status informado no formulário não altera o status inicial `registrado`. Envases confirmados são exibidos em modo de consulta; edição, lixeira e exclusão direta não são permitidas. A correção de um envase usa o estorno rastreável disponível no detalhe, descrito abaixo.

## Custos históricos de embalagem

A partir desta versão, cada novo envase guarda a composição usada, a quantidade consumida, o custo médio de cada componente e o identificador da movimentação. A tela de detalhe apresenta cada componente, a quantidade, o custo e a movimentação correspondente. Consultas futuras preservam esses valores mesmo que você altere a composição ou receba novas embalagens com outro preço. Envases antigos, sem essa fotografia, continuam consultando o cadastro atual e são identificados como históricos indisponíveis no retorno técnico. A parcela de cerveja ainda é rateada pelo total de litros envasados no lote e pode mudar se forem registrados envases adicionais.

## Estornar envase

No detalhe de um envase confirmado após o registro de custos históricos, informe o motivo e clique **Estornar envase e devolver embalagens**. O sistema cria entradas no Estoque correspondentes a cada saída original e registra os dois IDs, a data e o usuário no envase cancelado. Não é possível estornar duas vezes. Os insumos de brassagem continuam consumidos no lote, pois não pertencem a um envase específico. Envases antigos sem fotografia das saídas exigem reconciliação manual. Envases cancelados não entram no rateio de custo dos envases ativos.

## Preparar envase dentro do lote

Na aba **Sessões** do workspace da planta, abra o lote (inclusive antigo).
No card **Envase e precificação**, abra **Preparar envase deste lote**:

1. Busque o **Material resultante**, com volume real positivo cadastrado.
2. Informe os litros e clique em **Consultar prévia de embalagens**.
3. Confira volume por unidade, unidades físicas, componentes por unidade,
   necessidade total, saldo atual e estimativa pelos custos médios atuais.
4. Confira avisos de custo/saldo ausente, componente indisponível, unidade
   sem base cadastrada ou composição vazia. Quantidades repetidas do mesmo
   componente são somadas. Unidades fracionadas não são arredondadas.
5. Se houver ingredientes ainda não confirmados, a prévia informa que o
   registro pelo fluxo existente os consumirá junto com as embalagens.
   Pendências da receita continuam impedindo esse registro.

Esta consulta não salva envase, não baixa/reserva estoque e não confirma
ingredientes. **Estimativa parcial** soma apenas custos conhecidos; valor
zero parcial não significa embalagens gratuitas. O custo registrado dos
insumos do lote inteiro é mostrado separadamente, sem ratear ou recalcular.
Selecionar PCT não significa 1 kg; nenhum pacote é convertido pela prévia.

Ao alterar o produto ou os litros, consulte novamente. Composição, preços e
saldo podem mudar até o registro; a prévia não é uma reserva nem garantia.
A consulta exige acesso aos lotes/envases e permissão de criar envases.
O registro agora também pode ser confirmado dentro da sessão; o estorno
continua no detalhe de envase existente. O atalho de precificação permanece
separado e esta prévia de embalagens não calcula preço de venda.

## Registrar envase na sessão da planta

Abra o lote na aba Sessões, inclusive se ele for antigo. Em Preparar envase,
selecione o produto, informe os litros e, se desejar, data e tipo do envase.
Consulte a prévia e confira componentes, unidades, custos e avisos.

Clique em **Registrar envase deste lote**. O modal informa se também serão
consumidos ingredientes ainda não confirmados. Cancelar o modal não grava
nada. Confirmar registra o envase e as baixas de estoque na mesma operação,
retornando à sessão escolhida. Ingredientes já confirmados e seu custo
registrado são preservados. Pendências precisam ser resolvidas primeiro.

Se a resposta se perder, tente novamente com a mesma confirmação exibida.
Essa repetição recupera o mesmo envase, sem outra baixa. Consultar uma nova
prévia inicia outro registro e permite um envase adicional. A prévia não
reserva estoque: composição e custos são conferidos no registro.

Para estornar, use o detalhe de envase existente. A integração do estorno
dentro da sessão e a consolidação da precificação são próximas etapas.


## Detalhes e estorno no workspace (2B)

O número do envase na aba Sessões abre os detalhes dentro do lote. Consulte
os snapshots de embalagens/custos e de devoluções, incluindo registros
cancelados. O formulário de estorno requer `envases.update`, motivo e
confirmação no modal padrão. A consulta requer `envases.list` e
`envases.detail`, além do acesso a sessões. O estorno e seu log são gravados
na mesma transação; falha desfaz as devoluções. Ingredientes não são estornados.
Os acessos existentes de detalhe/estorno continuam disponíveis. Envases sem
snapshot não ganham baixa ou estorno baseado na composição atual.


## Precificação: custo registrado e estimativa (2C.1)

Depois de confirmar ingredientes, a precificação usa `custo_total_insumos`
congelado do lote. Não recalcula esse total com preços atuais nem apresenta
uma lista estimada de ingredientes como se fosse histórico. Antes da
confirmação, permanece estimativa por preço atual/padrão, sinalizada como
incompleta quando faltam vínculos/preços ou conversão confiável.

Com envase selecionado, embalagens vêm de seu snapshot de confirmação,
com origem “Registrado no envase”. Snapshot vazio é custo zero conhecido;
snapshot ausente usa ItemEnvase legado como estimativa atual. Snapshot com
custo ausente exige conferência e não é substituído por zero/preço atual.
Envase cancelado, apagado ou de outro lote é rejeitado. Cálculos salvos
anteriormente permanecem com seus valores históricos após estorno.

Com envase selecionado, o incremento 2C.2 aplica o rateio descrito abaixo.
Sem envase, permanece o custo de ingredientes do lote inteiro. Simular não
escreve; Calcular e Salvar grava a precificação, sem registrar envase ou
movimentar estoque.
No detalhe de envase registrado do workspace há atalho para abrir ambos os
combos preenchidos e retornar à mesma sessão/envase.

## Precificação por envase e unidade (2C.2)

Abra a precificação pelo detalhe do envase na aba Sessões. Ingredientes
recebem a fração litros do envase / soma dos litros dos envases registrados
e não apagados do lote. Cancelados não participam. Embalagens são apenas
as do envase escolhido. A tela informa litros, percentual e custo total
do lote usado como base; quantidades de ingredientes continuam sendo da
receita completa e o custo aplicado é proporcional.

Custo por unidade = subtotal / unidades do envase. Preço por unidade =
total após lucro/impostos / unidades. Preço por litro = total / litros do
envase. As fórmulas de lucro e impostos existentes foram preservadas.
As unidades não são arredondadas para inteiro. Sem envase não se calcula
preço unitário. Volume ausente/inválido em qualquer envase participante
bloqueia o rateio, exigindo conferir o histórico.

Novos registros guardam volume por unidade e unidades geradas. Alterar
o cadastro do produto depois não altera essa base. Para envases antigos,
a tela identifica unidades estimadas pelo volume atual do produto ou
preço unitário indisponível. Não se deduz volume pelo nome do material,
pacote ou unidade PCT. Custos registrados e estimados mantêm indicação
separada; estimativas incompletas não se tornam custos confirmados.

Calcular e Salvar congela a base do rateio e valores unitários. Um novo
envase ou estorno altera novos cálculos, sem reescrever cálculos salvos.
Vincular posteriormente um cálculo do lote a um envase mantém sua base
original; faça novo cálculo com o envase selecionado para aplicar rateio.
Cálculos antigos sem snapshot permanecem históricos, sem reconstrução.
Simular e consultar não movimentam estoque.


## Continuidade com o lote da planta

Na aba Sessões da planta, prepare e registre o envase, confira detalhes e
snapshots e abra a precificação. Retorne ao mesmo lote pelo atalho da tela.
Prévia/simulação não movimentam estoque. Estorno com motivo devolve embalagens
registradas e mantém ingredientes da brassagem consumidos e custo congelado.
Repetir registro com a mesma confirmação não duplica baixa; novo envase exige
nova confirmação. Envases antigos sem movimentos identificados precisam de
reconciliação própria e não recebem um estorno inventado.
