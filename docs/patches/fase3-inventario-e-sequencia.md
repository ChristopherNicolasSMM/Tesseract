# Fase 3 — inventário e sequência

Levantamento de 07/10/2026 sobre `65c42f4`. Primeiro pacote: reconciliação
documental e plano de execução. Não altera runtime, models, templates gerados
ou migrations. Não inclui `docs/imgs/logo.png`, alteração preexistente.
Não foram encontrados AGENTS.md no workspace examinado.

## Base e alcance da evidência

Histórico conferido: `fbb227e` (receita/planta/Brewfather), `d94f581`
(YeastBank), `65c42f4` (recebimento). Neste checkout os hashes coincidem com
as referências de geração. Em outro checkout comparar conteúdo, não exigir
esses hashes. Os três pacotes estão aplicados e validados localmente pelo
usuário, incluindo os testes do último pacote, conforme abertura da fase 3.
151 casos de estoque e 177 de integrações são resultados do ciclo anterior;
não foram reexecutados por este pacote documental.

A revisão leu os seis documentos indicados, models de cotação/pedido,
serviço central de estoque, hooks de pedido/itens/unidades e percurso CRUD
de itens. Não é auditoria completa de todos os addons, permissões ou bancos.
Ausência de proteção no trecho examinado é evidência para investigação,
não substitui reprodução pela API e formulário.

## Pendências reais e critérios — levantamento inicial

A tabela preserva as evidências do início da fase. O acompanhamento da entrega
funcional ao final atualiza C1/C2 como implementados no escopo descrito,
com aplicação e testes locais confirmados pelo usuário; não reabrir os defeitos já tratados por esta lista.

| ID / natureza | Evidência atual | Impacto / prioridade | Dependências | Migration | Critério de conclusão |
| --- | --- | --- | --- | --- | --- |
| D1 — defeito documental | Consolidação dizia aguardar validação; continuidade dizia estoque não executado; fechamento do recebimento aguardava validação | Planejamento repetia trabalho concluído / imediata | Confirmação do usuário e histórico | Não | Estados atuais reconciliados; registros antigos identificados como históricos |
| C1 — lacuna de proteção por leitura | `root/services/estoque_service.py::receber_pedido_compra` lê confirmado e faz entradas sem reserva/releitura exclusiva; `_get_or_create_saldo` também não reserva saldo | Recebimentos simultâneos e atualizações concorrentes podem conflitar / alta | Política por SQLite e PostgreSQL; serviço central; testes em conexões independentes | A determinar após desenho; não presumir necessidade | Mesmo pedido recebido uma vez; materiais compartilhados sem perda de saldo/custo; falha desfaz todas as entradas |
| C2 — lacuna de proteção por leitura | `item_pedido_compra_service_hooks.py::pai_apply_fields` recalcula fator/quantidade/subtotal a cada save; CRUD de itens não verifica status do pai na edição/lixeira/restauração | Snapshot pode mudar após compromisso ou recebimento / alta | Matriz de estados e operações; overrides/template CrudGen para erros e manutenção | Provavelmente não, confirmar no pacote | Reproduzir por serviço/API/formulário; proteger snapshots e referências; erro amigável/rollback; edição legítima em rascunho preservada |
| U1 — lacuna por leitura | `material_unidade_service_hooks.py` testa fator > 0 e base = 1; atualiza `Material.unidade_medida` quando base, sem conferir ledger/saldo nesse hook | Mudança da semântica de saldo/histórico; finitude do fator merece teste / alta | Inventariar hooks do material, conversões e referências antes de concluir alcance | A determinar | Não reinterpretar históricos/saldos; fatores inválidos rejeitados; troca de base segura ou recusada; PCT e ITEM/UN explícitos |
| F1 — melhoria proposta | `root/model/cotacao.py` e `pedido_compra.py` não possuem moeda/taxa; `financas-cambio-proposta.md` é proposta | Valores estrangeiros não têm contrato econômico representável / após C1/C2 | Decidir moeda de referência, precisão, data/fonte e fronteira pública do financeiro | Sim se adicionados campos persistentes | Seleção de moeda; conversão explícita exigida; snapshot original/convertido/taxa/data preservado; nunca paridade presumida |
| Y1 — decisão funcional | Auditoria YeastBank registra ausência de Material, consumo físico e cultura filha; correção validada mantém esse limite | Rastreabilidade/custo de culturas indisponíveis / após estoque | Unidade física, genealogia, inoculação, descarte/estorno e custo; serviço central | Provável, desenho pendente | Eventos laboratoriais separados dos físicos; movimentos idempotentes; custo histórico; rollback composto |
| P1 — melhoria adiada | Docstring do recebimento e model PedidoCompra definem recebimento sempre total por decisão anterior | Atendimento parcelado indisponível / condicionado à necessidade | Quantidade restante, cancelamento, preço/fator congelados e estorno | Provável | Contrato aprovado e testes de parcelas/repetição; não mudar total implicitamente |
| Q1 — verificação pendente | Requirements fixam Flask 3.1.3, Flask-SQLAlchemy 3.1.1 e SQLAlchemy 2.0.51; versões anteriores já usadas no ciclo; migrations existentes | Compatibilidade/depreciações / por escopo | Banco instalado, cadeia Alembic, ambiente real | Não para levantamento; depende da correção | Inventário de warnings executados e compatibilidade; upgrade somente com necessidade e testes |
| A1 — decisão/verificação | Continuidade mantém PID contínuo e proveniência física como radar; pacote de automação existente não prova hardware | Origem confiável e controle físico / após contratos de execução | Dispositivos, origem/event IDs, falhas/reconexão e bancada | A determinar | Software testado separadamente de hardware; origem rastreável e execução definida |
| UX1 — verificação por escopo | Manuais e roteiros existentes; sete menus ocultados, acessos avançados preservados; painel YeastBank sem paginação server-side | Legibilidade, navegação e escala / incremental | annotations/CrudGen, RBAC e dados representativos | Não para docs/temas; confirmar demais mudanças | Temas/combos/URLs conferidos, permissões preservadas; ocultar apenas cobertura demonstrada |

Os caminhos abreviados de compras/unidades são relativos a
`addons/addon_estoque/`. Não se afirma que C1, C2 ou U1 já foram reproduzidos
em concorrência ou corrigidos neste patch.

Busca nos controllers manuais `plant_workspace.py`, `dashboard_runtime.py`
e `recipe_timeline.py` não encontrou `.query.get(` ou `.get_or_404(` nesta
rodada. Não repetir a correção antiga por nome; capturar warnings da execução
antes de escolher depreciações em outros pontos. Não há proposta de upgrade
amplo nem verificação online de novas versões neste pacote.

## Sequência recomendada

1. **Reconciliação e inventário** — este pacote documental, sem migration.
2. **Compras e recebimento protegido** — reunir C1/C2: reprodução, matriz de
   estados, preservação de snapshots, manutenção do pedido/item e concorrência.
   Manter recebimento total, serviço central e legado sem snapshot. Uma decisão
   sobre campos administrativos editáveis pode ser necessária; não bloquear
   o levantamento e reproduções por essa decisão. Não alterar gerados à mão.
3. **Unidades e contratos de saldo** — U1, fatores finitos, proteção de base e
   referências; conferir interação com o pacote 2 e custos de ingredientes.
4. **Moedas/câmbio e fronteira financeira** — desenhar F1 antes de schema/UI.
   Não incluir conversão automática ou diferenças de pagamento no estoque.
5. **YeastBank físico** — Y1 com contrato de quantidade, genealogia e custo.
   Não transformar criação/remoção de evento laboratorial em baixa/devolução.
6. **Automação/hardware e escala de UX** — A1/UX1 conforme necessidade concreta.

Q1 acompanha cada pacote: warnings e migrations do escopo, sem campanha de
upgrade independente. P1 continua adiado até necessidade funcional; não é
dependência para a correção de recebimento total. Ordem pode mudar se uma
reprodução comprovar risco mais urgente.

## Aplicação e verificação deste pacote

Base: checkout contendo os três últimos pacotes, conteúdo equivalente a
`65c42f4`. Sem `flask db upgrade`. Sem alteração de URL, menu ou comportamento.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-reconciliacao-inventario.patch
```

Validação proporcional: integridade de links Markdown locais nos documentos
alterados, `git diff --check`, geração `git format-patch`, aplicação em checkout
isolado da base, igualdade de árvores e `git apply --reverse --check`.
Não requer pytest, pois só altera documentação. Não atribuir a este patch os
resultados Python/JS históricos. Resultados finais da aplicação são informados
na entrega após executados; esta seção descreve o procedimento.

Conferência documental: continuidade deve mostrar o ciclo encerrado; relatório
de auditoria deve distinguir achados antigos das lacunas restantes. Os manuais
operacionais permanecem aplicáveis ao runtime entregue; este patch não adiciona
operações nem certifica todos os manuais. Conferência visual opcional do runtime
existente (host/IDs da instalação):

- `/brewstation/plant-workspace/`: navegar abas e manter contexto.
- `/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe&recipe_id=<ID_RECEITA>`:
  receita usada exige revisão; conferir temas/seletores sem alterar históricos.
- `/brewstation/yeast-bank/painel`: permissões e viabilidade existentes.
- `/estoque/materials`, `/estoque/movimentacaos`, `/estoque/saldos`: conferir
  consulta do histórico; este pacote não exige novo recebimento para validação.

Limites: sem nova execução funcional, PostgreSQL, banco instalado, hardware,
Brewfather remoto ou inspeção em navegador. Nenhuma frente futura foi marcada
como implementada por constar neste inventário.


## Entrega funcional seguinte — compras/recebimento protegido

C1/C2 implementados no escopo de pedido/item, reserva de recebimento e saldo
compartilhado, após reprodução de quatro defeitos. Aplicação e testes locais
confirmados pelo usuário. Ver [entrega e limites](fase3-compras-recebimento-protegido.md).
U1 implementado no pacote seguinte, aguardando validação local; C1/C2 não certificam geração RFQ concorrente,
numeração automática ou PostgreSQL. Recebimento parcial continua adiado.


## Entrega U1 — unidades e conversões protegidas

Seis defeitos reproduzidos: fator infinito, troca de base com saldo, troca de
material da conversão, lixeira com uso, código duplicado e desativação da base
usada. Corrigidos por hooks/serviço manual, com proteção do pai e reserva da
mesma linha Material usada pelo ledger. Sem migration. Ver
[fase3-unidades-conversoes-protegidas.md](fase3-unidades-conversoes-protegidas.md).
Implementado e testado no ambiente de geração; aplicação/validação local pendentes.

Ordem seguinte: (1) revisão de depreciações Query.get por escopo e contratos de
migrations, sem upgrade amplo; (2) desenho de moeda/câmbio, condicionado a
moeda-base, precisão e fonte/data decididas; (3) YeastBank físico, condicionado
a unidade física, genealogia e estorno. Recebimento parcial permanece adiado.
Automação/hardware requer levantamento próprio e ensaio físico separado.


## Compatibilidade — revisão pontual seguinte

Query.get dos controllers indicados já estava corrigido; não reabrir. Corrigida
a depreciação efetiva de db.get_engine no ambiente Alembic, sem migration ou
upgrade. Cadeia verificada em SQLite temporário; compatibilidade do banco
instalado e reprodução integral das versões fixadas continuam pendentes. Ver
[fase3-compatibilidade-migrations.md](fase3-compatibilidade-migrations.md).
Aplicação e validação local deste novo pacote pendentes.

A seleção RBAC ampliada também comprovou Query.get na API manual Core de
usuários. Os quatro acessos por ID e duas leituras do teste foram atualizados;
permissões, validações, status HTTP e desativação da sessão permanecem cobertos.


## Administração Core — continuidade da revisão por escopo

Reproduzidos avisos em quatro controllers manuais: usuários, Roles, transações
e regras de campo. Os 17 lookups e leituras dos testes associados foram
atualizados para Session.get, preservando contratos. Sem migration/upgrades.
Ver [evidências e roteiro](fase3-administracao-core-sqlalchemy.md). Aplicação e
validação local pendentes; pacotes anteriores de unidades e compatibilidade
continuam aguardando confirmação local. OData/Designer/Model Builder exigem
própria seleção de contratos antes da próxima revisão de depreciações.


## Ferramentas e integrações Core — revisão seguinte

Aplicação do pacote administrativo confirmada pelo usuário; testes locais
ainda pendentes de confirmação. O pacote seguinte cobre 29 lookups manuais
de OData, Designer, Model Builder e Playground, incluindo as pontes entre
serviços. Três testes desatualizados foram reproduzidos: contagem do pipeline
e referência à documentação consolidada. Sem migration/upgrades. Ver
[fase3-integracoes-ferramentas-core.md](fase3-integracoes-ferramentas-core.md).
Aplicação e validação local do novo pacote pendentes. Câmbio e YeastBank
físico continuam condicionados a desenho funcional; reprodução integral
de dependências e PostgreSQL permanece verificação pendente.


## Decisões financeiras e fundação de organizações

Usuário confirmou moeda-base por organização, financeiro antes da integração
a compras e identidade de organização no Core. O pacote seguinte implementa
essa identidade, com migration a71c8d32f906 e sem atribuição automática dos
dados antigos. Ver [escopo e sequência](fase3-organizacoes-core.md).
Aplicação do pacote anterior de ferramentas confirmada; testes locais ainda
pendentes de confirmação. Financeiro/conversão e contexto organizacional do
estoque permanecem implementação futura, em ordem de dependência.


## Financeiro inicial, cadastro ampliado e GetCEP

Organizações Core aplicadas e validadas pelo usuário; primeira organização
criada. Novo pacote unifica fundação monetária, dados legais/endereço principal,
responsáveis e consulta CEP em plugin sem tabelas. Migration b82d9e43a017,
sem moeda/vínculos inferidos para o legado. Aplicação/validação local deste
novo pacote pendentes. Ver [escopo e sequência](fase3-financeiro-organizacoes-getcep.md).
Câmbio, contexto organizacional do estoque e títulos permanecem posteriores.


## Correção após conferência local — financeiro/organizações/GetCEP

Usuário apontou CEP sem consulta/mensagem, cadastro/lista fora do padrão,
perda de valores ao salvar e menu financeiro fora do padrão de addon. Entrega
inicial não é considerada funcionalmente validada. Correção restaura padrões
Core e descoberta automática AddonBase, preserva formulários em erro/omissão
e reforça inicialização/URL/estado do GetCEP. Sem nova migration. Ver
[fase3-financeiro-cadastro-getcep-correcao.md](fase3-financeiro-cadastro-getcep-correcao.md).
Câmbio e etapas seguintes permanecem posteriores à validação desta correção.

## Câmbio — continuidade após validação do corretivo

Em 08/10/2026 o usuário confirmou aplicação e validação do corretivo de
organizações/Financeiro/GetCEP. O pacote seguinte entrega taxas direcionais,
simulação e histórico idempotente de conversão. Política inicial mantém contrato
imutável; versionamento de base/escala/arredondamento e contexto organizacional
de compras/estoque permanecem pendentes. Ver [câmbio](fase3-financeiro-cambio.md).
Esta nova entrega aguarda aplicação/conferência local. Não atribui moeda/base/
organização a materiais ou saldos legados; não liga custos ao estoque global.

## Revisões explícitas de política — continuidade do câmbio

Em 08/10/2026 o usuário confirmou aplicação/validação do pacote de câmbio.
Entrega seguinte: versões append-only de precisão/arredondamento, com data,
motivo/autoria e escolha explícita nas conversões. Política inicial/v1 e
snapshots anteriores preservados; sem promoção automática à última revisão.
Migration e15a2b76d340. Ver [roteiro/evidências](fase3-financeiro-versoes-politicas.md).
Aplicação desta nova entrega pendente. Mudança de moeda-base aguarda tratamento
de saldos/contexto organizacional. Compras/estoque e títulos permanecem próximos.


## Continuação — catálogo compartilhado e contexto de compras (08/10/2026)

Decisão do usuário: catálogo compartilhado, com compras/saldos/custos separados
por organização. O pacote preparatório registra vínculos explícitos de
processos/pedidos, sem reatribuir documentos ou saldos legados. Recebimentos
organizacionais e geração organizacional aguardam a etapa de ledger/saldos e
propagação atômica. Inclui a correção UTF-8 do teste JavaScript de versões.
Ver [aplicação e limites](fase3-compras-contexto-organizacional.md).


## Continuação — ledger organizacional e recebimento (08/10/2026)

Entregue ledger/saldo Decimal por organização, mantendo o saldo global sem
atribuição. Pedidos vinculados exigem avaliação monetária congelada antes do
recebimento; processos vinculados propagam a organização em geração atômica.
Câmbio e políticas são consumidos por serviços públicos, sem FK entre addons.
Mantidos recebimento total e ausência de rateio do frete. Moeda/Decimal desde
a criação dos documentos e contextos organizacionais do BrewStation ainda
são etapas seguintes. Ver [aplicação, URLs e limites](fase3-estoque-organizacional-recebimento.md).

## Continuação — cadastro monetário explícito (09/10/2026)

Após validação do ledger/recebimento, entregue cadastro imutável de moeda e
valores Decimal das cotações/pedidos, em uma confirmação manual complementar
às telas estruturais existentes. Moeda, quantidades/preços exatos e fator
original são herdados atomicamente no pedido e consumidos na avaliação e no
recebimento. Comparação exata na mesma moeda; moedas/fatores incompatíveis
bloqueiam seleção/geração até contrato de conversão explícita. Documentos
legados e avaliações anteriores permanecem sem reatribuição. Migration
`b48d5e09a673`. Ver [aplicação e limites](fase3-compras-moeda-decimal.md).
