# Aquecimento — entrega 4 e continuidade

A entrega 4 acrescenta controle liga/desliga principal/auxiliar em fonte protegida,
com habilitação explícita e autorização expirável. O operador informou proteção
externa de chama que corta corrente e aciona sirene, fora do software. Não há retorno
elétrico dessa proteção; corte/rearme após falha de chama dependem do circuito.

Execução: contrato e arbitragem local no Bridge; telemetria e delegação no Core;
widget e configuração; testes de falhas e regressão; documentação e publicação.
Não altera o PID/janela existente nem aplica migração nova.

[Manual completo](../manual/09-aquecimento-automatico.md).

Continuam pendentes: ensaios físicos e validação do circuito externo com responsável,
retorno de chama/válvula, watchdog elétrico, vazamento, nível/fluxo, controle de fervura
por intensidade e coordenação multiworker. HLT/sparge usa alvo planejado independente,
sem transferência automática, pressão ou volume medido.
