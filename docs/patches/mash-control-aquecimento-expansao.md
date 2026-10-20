# Expansão de aquecimento — plano e entrega 1

## Etapas definidas antes da implementação (2026-10-20)

1. **Equipamentos e apresentação (esta entrega):** fontes principais/auxiliares por recipiente;
   sensor principal explícito; perfil de uso do recipiente (mostura, fervura, água quente/HLT e
   sparge); alvo e volume planejados de água de lavagem; widget Aquecimento no editor existente;
   configurações na aba Planta do workspace. Preservar dashboards e mapeamentos antigos.
2. **Regras e solicitações (entrega 2 implementada):** demanda acima de X% por tempo mínimo, distância ao alvo,
   histerese, ciclo de solicitação/resposta do operador e auditoria. Avaliação no servidor,
   independente do navegador. Sem dados reais de demanda, mostrar indisponibilidade.
3. **Telemetria e controle (futura):** demanda PID, potência limitada, override e retorno do
   equipamento com origem/data/qualidade; arbitragem por controlador local/externo. Sem novo
   loop PID no navegador. Automação do gás depende de supervisão/corte locais apropriados.

## Escopo e critérios da entrega 1

- Reutilizar Tanques (`hlt` já existe), Mapeamentos, Device Manager e o editor do dashboard;
  não abrir novos menus/CRUDes dispersos. Novo widget `heating` associado a um recipiente.
- Cadastrar uma ou várias fontes: nome, tipo, principal/auxiliar, modo manual/solicitação,
  função de dispositivo opcional e potência nominal opcional. Nesta entrega nenhuma fonte
  nova envia comandos de aquecimento; o widget é informativo/configurável.
- O fogareiro GLP com piloto sem supervisão é representado como manual/solicitação;
  cadastro e tela não comprovam chama ou proteções físicas.
- Sensor principal é escolhido por mapeamento válido do próprio recipiente; sensores
  adicionais continuam nos mapeamentos. Não alterar automaticamente vínculos legados.
- HLT/sparge usa o mesmo widget. Temperatura alvo e volume planejados são parâmetros
  de preparação, não medições nem automação de transferência. Fluxo/vazão/nível são
  mapeamentos opcionais; não inventar litros reais a partir de volume planejado.
- Proteções futuras (chama, gás, nível mínimo, fluxo e sobretemperatura) aparecem como
  não configuradas/sem confirmação até haver implementação específica. Não são permissões
  de acionamento.
- Seleção, criação e edição de widgets/fontes verificam planta, recipiente e permissões no
  servidor. HTML usa escapes; JS usa textContent para dados de usuário. Sem FK entre addons.
- Migration aditiva preserva dados; nenhum equipamento/regra será ativado automaticamente.

## Validação e publicação

Testar configuração e isolamento de plantas, perfis HLT/sparge, seleção do sensor, widget
no editor/snapshot, ausência de comandos físicos, migração e regressões do dashboard/workspace.
Publicar após checks; informar `db upgrade`, comandos de teste, commit e limitações reais.

## Implementação da entrega 1

- Configuração JSON versionada no tanque, protegida contra escrita pelo CRUD genérico.
- Serviço dedicado com validação de referências, limites, exclusividade da fonte principal,
  bloqueio durante sessões ativas/pausadas e conflito de versão com rollback.
- Cadastro no workspace existente e widget `heating` na paleta do dashboard. Sensor
  principal também aplicado ao widget Tanque; nenhum vínculo legado é regravado.
- Migration `b04e7c98d216` após `a93dbe671ca5`; upgrade aditivo e downgrade bloqueado
  se houver configuração para preservar.
- [Manual](../manual/08-aquecimento-hlt-sparge.md) e
  [contrato técnico](../technical/08-aquecimento-hlt-sparge.md).

## Verificação registrada

- 19 testes novos de aquecimento aprovados, incluindo HLT/sparge independente da etapa.
- 15 testes JavaScript aprovados (`node --test tests/js/*.cjs`).
- HTML real do dashboard renderizado e seus quatro scripts inline verificados com `node --check`.
- Grafo Alembic com head único `b04e7c98d216`; testes de upgrade/repetição, preservação
  de registros, definição incompatível e bloqueio de downgrade com dados aprovados.
- Na regressão, o teste `test_workspace_lote_mostra_pendencias_custo_registrado_e_envases_corretos`
  falha esperando “Estimativa incompleta”. Mesma falha reproduzida no commit base
  `0c610ac`, sem esta implementação; pendência separada no backlog.
- Execução local em Linux/SQLite. Não executados Windows, hardware Raspberry Pi ou
  comandos físicos. Chromium ausente no ambiente; a validação de interface foi por
  renderização HTML, sintaxe dos scripts e testes DOM, sem sessão de navegador real.

As comparações adicionais reproduziram outras 26 falhas preexistentes no mesmo
commit base (preparação/envase/estorno e contexto do lote), além da falha do resumo
de custos: 27 reproduções confirmadas. O fluxo atual de estoque exige organização
em cenários ainda montados pelos testes legados sem esse contexto. A expansão não
altera esses fluxos; a revisão foi registrada separadamente no backlog.

Resultado consolidado (casos únicos dos três módulos): **340 aprovados e 27 falhas**,
todas as falhas reproduzidas no commit base. Nenhuma falha nova identificada na
comparação. Dashboard: 111 aprovados; aquecimento: 19 aprovados; workspace: 210
aprovados e 27 falhas preexistentes. JavaScript: 15 aprovados.

## Continuidade

A entrega 2 está descrita no [roteiro de regras e solicitações](mash-control-aquecimento-entrega2.md).
Manual e contrato técnico foram atualizados para refletir as entregas 1 e 2.
A descrição e os resultados da entrega 1 acima são o registro histórico daquela validação.
