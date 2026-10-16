# Tesouraria — contas a pagar e receber

Disponível no Financeiro 1.3.0, segunda das três entregas aprovadas.

## Preparação

1. Cadastre organização ativa, moedas e política monetária no Financeiro.
2. Em **Financeiro → Contas financeiras**, crie uma conta bancária ou caixa.
   A moeda é a base da organização; informe saldo inicial explícito (zero é
   válido), data de abertura e política. A abertura gera um lançamento imutável.
   Contas em moeda estrangeira distinta da base não fazem parte desta entrega.
3. Cadastre **Categorias financeiras**, escolhendo pagar/despesa ou receber/receita,
   e **Centros de custo** na mesma organização. Não há organizações ou valores
   padrão inferidos. Nome e estado ativo podem ser alterados; a identidade,
   direção e abertura são preservadas. A edição usa versão para detectar conflito.

Os menus seguem a descoberta automática do addon. Selecione a organização no
filtro e clique **Filtrar** para carregar suas categorias, versões e taxas.
Uma tela sem filtro permite consultar os históricos de todas as organizações
conforme a permissão concedida. Não existe isolamento tenant por usuário.

## Criar títulos e parcelas

Abra **Financeiro → Títulos a pagar e receber**. As abas separam contas a pagar
e contas a receber. Informe organização, fornecedor/cliente, documento, categoria,
centro de custo, moeda original, total, emissão, primeiro vencimento, quantidade
de parcelas e referência única de criação. A primeira data não pode anteceder
à emissão. O parcelamento é mensal, de 1 a 120 parcelas, respeitando o dia do
primeiro vencimento quando existir naquele mês. Ex.: 31/10, 30/11, 31/12.

**Conferir título e parcelas** mostra os valores sem gravar o título. O resíduo
da divisão fica na última parcela: total 100,01 em três parcelas resulta em
33,33 + 33,33 + 33,35. A soma dos valores originais e das avaliações na base é
preservada. Um valor incapaz de formar parcelas positivas é recusado.

Na moeda-base não informe taxa. Em moeda estrangeira escolha taxa da mesma
organização, par original → base e data exata da emissão. Não há inversão,
triangulação nem seleção automática da taxa mais recente. Versão vazia significa
configuração inicial; revisões posteriores exigem escolha explícita.

**Registrar título e parcelas** congela a avaliação e a classificação. Não
altera caixa/estoque. Repetição equivalente da referência retorna o título
original; reutilização com dados diferentes é recusada. Correções de documento
são feitas por cancelamento e novo título, preservando os anteriores.

## Origem em pedido de compra

No formulário de título, **Carregar pedido de compra confirmado** recupera
organização, fornecedor, moeda e total do cadastro monetário congelado, incluindo
frete. Somente pedidos confirmados ou recebidos, com contexto organizacional e
cadastro monetário, podem originar uma conta a pagar. O addon Estoque deve estar
ativo. A leitura exige a permissão de detalhe de pedidos.

Confira a prévia antes de registrar. O total exato do pedido é preservado no
snapshot; a obrigação usa a precisão da moeda original e o arredondamento da
política escolhida. Ex.: custo unitário detalhado pode produzir total 1,246913…,
cuja obrigação na moeda de duas casas será 1,25. Na moeda estrangeira primeiro
se arredonda o total original, depois se converte a obrigação para a base.
As duas etapas ficam registradas. Isso não modifica o pedido ou o custo do estoque.

Um pedido só pode originar um título, inclusive se o título for cancelado.
Referências diferentes não permitem duplicar a obrigação de compra. Não há
geração automática ao confirmar/receber mercadoria. Contas a receber são
manuais nesta entrega, pois não existe integração comercial nova.

## Pagamentos e recebimentos

Abra o título e a parcela. Selecione conta da mesma organização, data da baixa,
principal liquidado, juros, multa, desconto, versão, taxa quando estrangeira e
referência única. Principal deve ser positivo e não exceder o saldo da parcela;
desconto não pode superar o principal. Os componentes são na moeda original.

**Valor de caixa = principal + juros + multa − desconto.** O principal determina
quanto da dívida foi quitado. Os outros componentes não aumentam/reduzem o
principal novamente. A conversão do caixa usa a taxa explícita da data da baixa,
que pode diferir da emissão. A diferença cambial do principal e eventuais
resíduos de arredondamento ficam separados no histórico.

**Conferir prévia** não reserva dinheiro nem grava lançamentos. **Confirmar baixa**
registra baixa e movimento da conta juntos, ou desfaz ambos. Pagamentos não podem
levar a conta a saldo negativo. A data não pode anteceder a emissão nem a abertura
da conta. Podem existir baixas parciais e várias baixas por parcela; o saldo
pendente é recalculado a partir dos eventos não estornados. A referência protege
contra repetição e confirmações concorrentes.

## Estornar e cancelar

No histórico do título, abra **Estornar baixa**, informe motivo, data e referência
única. O estorno inverte exatamente o movimento original, preserva a taxa usada e
reabre o principal da parcela; não recota câmbio. Para estornar um recebimento,
a conta precisa ter saldo suficiente para a saída. Conta inativa permite o
estorno do histórico, mas bloqueia novas baixas. A organização deve estar ativa.

Cancelamento do título exige que todas as baixas estejam estornadas. Nenhum
histórico é apagado, nem existe exclusão física nas telas/APIs. Os lançamentos
seguem a ordem de gravação; a data da operação é guardada separadamente.
Inativar um cadastro não remove seus saldos e históricos.

## Permissões e limites

Consultas HTML usam as permissões automáticas das respectivas listas. Escritas
e APIs seguem o padrão administrativo do Financeiro e exigem `admin`. Não
execute SQL direto para corrigir valores. A entrega não executa operações em
bancos externos, emissão fiscal, partidas dobradas ou apuração tributária.
Fluxo de caixa, transferências entre contas, conciliação e relatórios são a
terceira entrega; lançamentos de caixa já estão disponíveis para auditoria.
