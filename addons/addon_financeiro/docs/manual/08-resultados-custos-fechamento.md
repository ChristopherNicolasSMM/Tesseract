# Resultados, custos e fechamento gerencial

No workspace Financeiro, abra **Resultados**. O dashboard reúne receita líquida, resultado bruto, operacional e líquido, evolução mensal, formação do resultado e gastos por categoria e centro. Todos os valores derivam dos reconhecimentos da DRE. Os links conduzem à composição e às origens no mesmo workspace.

A comparação usa a mesma quantidade de competências completas imediatamente anteriores, até 12 meses. Variação percentual sem valor anterior e margem sem receita líquida positiva aparecem sem base de cálculo. Tabelas e tooltips preservam os valores decimais exatos; as coordenadas dos gráficos são aproximações visuais. O botão de relatório usa organização e período do cabeçalho, com o exemplo **Dashboard de resultados** do Reports.

## Custos de estoque e produção

Em **Custos de estoque/produção**, confira as saídas elegíveis da organização. Preparar um reconhecimento preenche a origem e o valor de avaliação já registrado no Estoque. Escolha uma classificação compatível, destinação (custo de venda, perda operacional ou fora do resultado), competências e centros, confira a prévia e confirme. A soma das apropriações deve corresponder ao custo congelado. Apenas um reconhecimento ativo é permitido por movimento.

Compras, transferências, estornos e consumo capitalizado não constituem automaticamente despesa. Movimentos identificados pelo contrato como consumo produtivo ou envase são informativos e não podem ser apropriados novamente como gasto. Não há cálculo presumido de CMV nem associação automática entre uma saída e uma venda. O reconhecimento não movimenta caixa ou estoque.

O Estoque é opcional. Quando indisponível, a cobertura de custos depende de revisão manual e ajustes documentados. A integração possui limite explícito de 2.000 movimentos da organização e recusa excedentes, sem truncar valores silenciosamente.

## Conferência, fechamento e reabertura

Em **Conferência e fechamento**, selecione a competência. A conferência considera origens pendentes até o fim do mês, inclusive anteriores. Classifique e reconheça ou documente sua exclusão do resultado antes de fechar. Origens futuras não bloqueiam o mês anterior.

O administrador declara a cobertura de receitas, custos, tributos e ajustes e registra as evidências. O fechamento guarda DRE, conferência, declarações, autor, motivo e checksum SHA-256 em uma versão imutável. Ele bloqueia novos reconhecimentos e estornos que atinjam a competência. É um fechamento gerencial com cobertura declarada, sujeito à revisão contábil.

Novos títulos ou movimentos retroativos podem surgir depois do fechamento. Eles aparecem como pendência e o resultado passa a indicar fechamento com pendências; o snapshot anterior permanece intacto. Reabra explicitamente, com motivo, corrija as apropriações e faça novo fechamento. A versão anterior e a reabertura continuam disponíveis no histórico. Repetir a mesma solicitação não cria outro evento nem reabre uma versão posterior.
