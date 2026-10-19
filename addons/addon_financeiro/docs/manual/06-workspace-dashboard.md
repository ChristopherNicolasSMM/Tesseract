# Workspace financeiro e dashboard operacional

Abra Financeiro > Workspace financeiro, em `/financeiro/`. A entrada principal
passa a apresentar Visão geral. As áreas disponíveis respeitam suas permissões;
quem tem somente leitura de títulos entra diretamente em Títulos.

## Contexto e navegação

Escolha organização, data inicial e data final/referência e clique em Aplicar
contexto. A escolha permanece nas demais áreas e no retorno das operações,
até ser alterada. O contexto é guardado na sessão do navegador; não altera o
cadastro da organização nem as regras monetárias. A data inicial padrão é o
primeiro dia do mês; a final é hoje, no fuso America/Sao_Paulo.

- **Visão geral:** saldos, movimentos, pendências, projeção e agenda.
- **Títulos:** a pagar/receber, detalhe, parcelas, baixas, estornos e histórico.
- **Caixa e bancos:** contas, fluxo, lançamentos e transferências.
- **Conciliação:** importação, vínculos e desfazimentos no mesmo contexto.
- **Configurações:** categorias, centros, moedas, políticas, versões e câmbio.

As telas compartilham a navegação e o layout do Core; não usam iframes. As URLs
antigas continuam acessíveis e apresentam o mesmo workspace. A lista de
atalhos separados foi substituída por uma entrada de workspace; as permissões
anteriores continuam sendo usadas.

## Entenda os períodos

A lista padrão de títulos filtra **emissão**. Os filtros Todos em aberto,
Vencidos e Próximos 30 dias consultam as pendências atuais das parcelas,
independentemente da emissão. O vencimento é comparado à data final escolhida.
Uma parcela no próprio dia da referência ainda não é considerada vencida.

Baixas, lançamentos e transferências são consultados pela **data da operação**.
Cadastros e configurações não são limitados pelo período. Moedas são globais;
políticas e taxas são filtradas pela organização. A seleção de conta está
nas visões bancárias; previsões continuam disponíveis apenas por organização.

## Dashboard

Os cartões abrem a composição em listas filtradas. Saldo até a data final
soma os movimentos até essa data, incluindo aberturas e transferências.
Entradas/saídas e movimentação líquida excluem aberturas e transferências
internas; incluem o efeito monetário dos estornos. Não representam lucro/DRE.
O saldo cadastrado da conta pode incluir movimentos posteriores à referência.

Pendências representam o **estado atual** das parcelas, convertido pelo valor
contábil base congelado; não reconstituem a posição histórica na data escolhida.
As janelas de 7, 15 e 30 dias incluem a referência e excluem seu limite final.
A agenda apresenta vencidos e os próximos 30 dias; cada documento abre seu
detalhe. Títulos cancelados e parcelas sem saldo não entram nas pendências.

Os gráficos mostram saldo realizado/projetado, entradas/saídas mensais e
pagamentos líquidos por categoria/centro. Estornos de pagamentos reduzem a
respectiva classificação. Aberturas e transferências não compõem esses gastos.
Valores exatos permanecem disponíveis nas tabelas; os gráficos são visuais.
As cores acompanham os temas do Core. Conciliação tem indicadores próprios,
visíveis a quem possui a permissão correspondente.

## Operar sem perder o contexto

Em Títulos, abra o documento, confira parcelas e registre ou estorne a baixa.
A resposta mantém organização e período. Pagamentos e recebimentos possuem
link para o título de origem. Em Caixa e bancos, escolha a conta para consultar
seus lançamentos ou conciliar. Transferências utilizam duas contas da organização
e mantêm confirmação/estorno atômicos. Erros preservam o formulário e o histórico.

Relatório da organização / período abre a emissão do Reports com esses filtros
preenchidos. Busca, filtros de pendência e conta não são aplicados silenciosamente
a relatórios que não os suportam. O botão identifica o escopo organizacional.
A emissão possui retorno ao Financeiro e continua exigindo modelo publicado.
Sem Reports ativo, o workspace continua funcionando e não mostra esse botão.

DRE e resultados entrarão nas próximas entregas, com competência e classificação
próprias. Esta entrega não cria classificação contábil presumida para o legado.
