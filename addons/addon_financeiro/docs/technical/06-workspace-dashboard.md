# Workspace financeiro — primeira entrega da consolidação

Base `437896e`; sem tabelas ou migração Alembic adicionais. A organização de
navegação não altera contratos POST/JSON, caches de saldo, movimentos ou snapshots.

`root/controller/workspace.py` fornece `/financeiro/`, shell compartilhado,
visões permitidas, contexto de sessão e URLs canônicas. O dispatcher GET chama
as views registradas e decoradas; não replica operações monetárias. Formulários
POST continuam apontando para seus controllers existentes. O contexto é passado
na query string e não acrescido ao payload estrito dos serviços. Um filtro GET
limpa paginação; navegação entre áreas preserva organização e período. Conta
não é propagada a títulos, configurações ou transferências.

O detalhe verifica título versus organização selecionada; contas consultadas
são verificadas na organização. Cada área/visão exige suas permissões de origem,
e escritas continuam administrativas. Dashboard exige leitura de movimentos e
títulos; nomes/saldos por conta e contagens de conciliação têm exibição condicionada
às respectivas permissões. Não há consolidação de moedas de organizações diferentes.

`workspace_service.dashboard(options)` retorna somente DTOs e strings monetárias.
Usa Decimal em contexto de precisão 64 e contratos existentes de fluxo e título.
Saldos seguem a data de operação até date_to; pendências são atuais. Janelas
[referência, referência + N dias). Limites: intervalo 366 dias, 10.000 registros
por fonte e 10.000 parcelas, sem truncamento silencioso. A paginação e os filtros
nas consultas de composição são aplicados antes da apresentação.

O shell deriva de core/base.html e as telas operacionais derivam do shell;
sem iframes nem cópia dos serviços. O script usa ApexCharts já fornecido pelo
Core; números de gráficos servem apenas à apresentação. Tooltips e tabelas
preservam strings exatas, inclusive montantes além da precisão de Number.
Rótulos de gráficos são escapados e a mudança de tema acompanha data-theme.

## Menu declarativo, com descoberta padrão

ModuleBase.get_transactions continua gerando transações por models e acrescenta
`manifest_workspaces(manifest,module_name=...)`. O campo opcional `workspaces`
contém code, label, endpoint, icon e permission_required opcionais. O endpoint
precisa estar registrado; entradas inválidas falham no boot. Não altera addons
sem esse campo nem overrides existentes. Financeiro não sobrescreve registro
de modelos, registro de rotas ou catálogo automático.

O manifesto Financeiro declara TX_WORKSPACE_FINANCEIRO. Os 13 atalhos anteriores
ficam inativos por deprecated_transactions, escopado ao próprio módulo. Os
códigos/permissões e endpoints antigos permanecem disponíveis. O Reports desativa
somente seu subgrupo de emissões Financeiro e seus quatro atalhos; IDE e fontes
de emissão permanecem operacionais e ligadas por botões contextuais.

A entrada do workspace é autenticada; sem permissões financeiras, retorna 403.
Usuários com acesso parcial entram na primeira visão autorizada. A entrada do
menu não concede permissão de leitura/escrita. A infraestrutura atual não possui
permissão OR no catálogo; o acesso a dados é validado pelas views e pelo dispatcher.

Relatórios recebem organização e datas; não anunciam aplicação de filtros de
busca, conta ou pendência que a fonte não implementa. O Reports permanece dono
do renderer/modelos publicados. APIs financeiras anteriores são preservadas.

## Próximas entregas

Competência, grupos de resultado, apropriações e DRE são a entrega 2. Dashboard
de resultados e integração de custos disponíveis compõem a entrega 3. Não há
aba de DRE vazia nem dados contábeis inferidos nesta primeira consolidação.
