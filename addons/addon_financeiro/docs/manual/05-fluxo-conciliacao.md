# Fluxo de caixa, transferências e conciliação

O menu Financeiro acrescenta Transferências financeiras e Conciliação bancária.
Fluxo de caixa ocupa a entrada anterior de lançamentos; o histórico permanece
em `/financeiro/lancamentos/historico`. O addon mantém descoberta automática.
Escolha a organização e consulte para carregar suas contas e políticas.

## Fluxo de caixa

A consulta admite até 366 dias e conta opcional. Valores realizados seguem a
**data da operação**, não a ordem de cadastro. O saldo inicial resulta dos
lançamentos anteriores ao período; aberturas dentro do período aparecem em
coluna própria. Receitas/saídas realizadas incluem o dinheiro dos estornos.
Transferências e seus estornos aparecem separadamente; na consolidação da
organização as duas pontas se anulam.

O plano original usa valores base congelados das parcelas não canceladas.
A previsão usa o **pendente atual** das mesmas parcelas, pelo valor contábil
congelado na emissão. Não calcula câmbio futuro, nem reconstitui uma posição
histórica das pendências. Vencidos anteriores ao início entram no saldo
projetado inicial, informados separadamente. O saldo projetado soma esse saldo,
os movimentos realizados e as parcelas ainda pendentes do período.

Parcelas não possuem conta atribuída antes da baixa; ao filtrar uma conta,
a consulta mostra somente realizados, sem distribuir previsões arbitrariamente.
Datas futuras já registradas integram o realizado pela sua data de operação.
O saldo após cada lançamento no histórico é o saldo na ordem de registro,
que pode diferir de um saldo cronológico quando há lançamentos retroativos.

## Transferências

Informe organização, duas contas ativas distintas, valor positivo na moeda
base, data, política e chave de idempotência. A operação confirma as duas
pontas juntas, conserva o total da organização e exige saldo disponível.
Repetir a mesma chave/conteúdo retorna o evento original. Outro conteúdo
exige outra chave. Não há transferência entre organizações ou conversão.

Para corrigir, use Estornar, informe data igual ou posterior, motivo e nova
chave. O destino precisa ter saldo para devolver o valor integral. As contas
podem estar inativas no estorno; a organização precisa estar ativa. Nenhum
histórico é apagado. Estorno é integral e não permite editar o valor original.

## Extrato CSV

Importação manual normalizada, sem sincronização bancária. Selecione conta,
moeda explícita, referência, chave e arquivo UTF-8 (vírgula), até 2 MiB/2000 linhas:

```csv
external_id,operation_date,amount,description
BANCO-OUT-001,2026-10-19,-100.01,Pagamento fornecedor
BANCO-IN-002,2026-10-19,50.00,Recebimento cliente
```

O sinal é obrigatório conceitualmente: débito negativo, crédito positivo.
Use ponto decimal, data ISO e identificador bancário estável por conta.
Valores zero são recusados. Identificador repetido na conta invalida a
importação inteira; não são ignoradas linhas silenciosamente. Reenvio com
mesma chave/conteúdo é seguro. Pré-visualizar não grava. Após a prévia,
reescolha o mesmo arquivo para confirmar; a validação é repetida no servidor.
A conta e organização precisam estar ativas para novas importações.

A importação **não cria pagamentos nem altera saldos**. Na listagem de linhas,
selecione explicitamente um lançamento da mesma conta, com valor e sinal
idênticos. As opções mostram somente candidatos no período consultado; amplie
o período para diferenças de data. Datas diferentes exigem justificativa.
Nenhuma sugestão é confirmada automaticamente. Contas inativas podem ter seu
histórico conciliado; a organização precisa estar ativa.

Cada linha e cada lançamento podem ter só um vínculo ativo. Para corrigir,
desfaça o vínculo com motivo e nova chave e concilie novamente. O histórico
mostra autor/data/justificativa e desfazimentos; saldos continuam inalterados.
O painel também lista lançamentos ainda sem vínculo. Não apresenta saldo
bancário final presumido, pois o CSV não informa saldo de abertura do banco.

## Relatórios

Com Reports ativo, Financeiro > Relatórios contém Fluxo de caixa, Títulos,
Pagamentos e recebimentos e Conciliação bancária. Na IDE de Relatórios, crie
um modelo a partir do exemplo correspondente e publique a versão. Na emissão,
selecione organização, datas e modelo publicado, gere a prévia e imprima ou
salve PDF pelo navegador. Sem modelo publicado, a tela indica o que falta.

Títulos filtram data de emissão, baixas filtram data de operação e conciliação
filtra data da linha bancária; estados apresentados são atuais. Moedas originais
são identificadas e não agregadas. Valores base pertencem à organização.
O Financeiro funciona sem Reports; nenhum modelo financeiro é publicado
silenciosamente. As consultas não alteram títulos, baixas, estoque ou extratos.


A navegação atual utiliza as áreas Caixa e bancos e Conciliação do
[Workspace financeiro](06-workspace-dashboard.md). Relatórios são acessados
por botões contextuais; seus modelos continuam mantidos no Reports.
