# Versões da política monetária

A configuração já cadastrada em Políticas monetárias passa a ser apresentada
como **versão 1**, mantendo seu ID, dados e uso original. Não há conversão ou
reescrita de registros antigos durante a atualização.

## Cadastrar uma revisão

Acesse `/financeiro/policy-versions/`, pelo menu Financeiro → Versões monetárias.
Escolha uma organização ativa com política cadastrada e confira a última versão
mostrada. Informe casas decimais (0–6), arredondamento HALF_UP/HALF_EVEN, data
inicial de validade e motivo. A moeda-base é a da política inicial; não se altera
neste formulário. Casas definem a precisão do montante dessa política, podendo
ser diferentes das casas do catálogo de moeda. A adequação dessa precisão à
operação deve ser escolhida pelo administrador.

HALF_UP afasta de zero nos empates; HALF_EVEN escolhe o último dígito par.
Exemplo: 1.005 com duas casas resulta em 1.01 por HALF_UP e 1.00 por HALF_EVEN.
Com três casas, 1.005 permanece 1.005.

A nova revisão precisa alterar casas ou arredondamento. Sua data não pode
anteceder a última revisão; a mesma data é permitida, pois a seleção é explícita.
Datas passadas ou futuras são aceitas sem recalcular o histórico. Se outra pessoa
cadastrar uma revisão enquanto seu formulário estiver aberto, será exibido um
conflito com seus campos preservados. Recarregue, confira a última versão e
preencha novamente a revisão desejada; ela não será aplicada silenciosamente.

## Usar em uma conversão

Em `/financeiro/conversions/`, o seletor Política monetária oferece:

- Política inicial (versão 1) da organização selecionada.
- Cada revisão cadastrada, identificada por organização, versão/ID, casas,
  arredondamento e data de início.

Escolha a política, a data e a taxa aplicável. A revisão precisa pertencer à
organização e já ser válida na data da operação. Não há seleção automática da
última versão: cada cálculo mantém a escolha explícita. Uma revisão anterior
continua disponível depois de cadastrar a próxima, para reproduzir operações
anteriores. A data é um limite inicial, não um intervalo com encerramento automático.

Simular não grava. Confirmar mantém snapshot da política escolhida, inclusive
versão, data, motivo e autoria, além dos valores e da taxa. Em Detalhes do cálculo,
confira a versão utilizada. Registros antigos mostram versão 1 sem alterar o
snapshot armazenado. Reenvio da mesma chave/cálculo continua idempotente; mudar
a versão para uma chave já confirmada retorna conflito.

Versões não possuem edição/exclusão. Administradores cadastram; permissões de
lista podem ser concedidas pelo padrão de roles. Acesso de lista não libera
cadastro, e não há segregação por organização/tenant nesse mecanismo.

## Atualização

Aplique o patch e execute `python run.py db upgrade`, no ambiente habitual.
Migration `e15a2b76d340`, após `d04f1a65c239`. Reinicie e use Ctrl+F5.
Downgrade com revisões cadastradas é bloqueado para preservar a história.

Mudança de moeda-base depende de tratamento explícito de saldos e contexto
organizacional. O cadastro de versões não movimenta estoque, não gera títulos
nem liquida pagamentos. Compras/estoque e contas a pagar/receber continuam
próximas entregas.
