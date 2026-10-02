# Workspace 2B — detalhes e estorno de envase

## Entrega e limites

O número do envase na aba Sessões abre seus detalhes localmente, mantendo a
planta e o lote selecionados. A consulta mostra volume, data, tipo, produto,
componentes, custos registrados e IDs das saídas originais. Para cancelados,
mostra motivo, operador, horário e pares saída → entrada. A leitura não chama
simulação, confirmação de ingredientes nem movimentação de estoque.

O estorno exige motivo de 1 a 1000 caracteres (após retirar espaços), usa
`window.__tesseractConfirm`, desabilita o botão durante confirmação/envio e
submete com o helper AJAX existente. O serviço `estornar_envase` continua
sendo a única execução do estorno: movimentações centrais, reserva
condicional de status e rollback. Agora também grava um log no lote dentro
da mesma transação, inclusive quando chamado pelas rotas já existentes.
Repetir um pedido cancelado retorna erro de negócio sem nova devolução e
preserva primeiro motivo/operador/horário. Não estorna ingredientes nem
altera o custo registrado, status, receita, timers ou etapas do lote.

Envases legados sem snapshot continuam consultáveis e exigem reconciliação
manual para estorno. O snapshot vazio significa que não havia embalagens
consumidas; permite cancelar sem fabricar movimentos. Não reconstrói saídas
pela composição/preço atual. Os IDs de materiais permanecem os históricos.

**Não exige `db upgrade`.** Nenhum campo, tabela ou revisão nova. Controllers
CRUD gerados não foram editados. Detalhe e estorno tradicionais permanecem
acessíveis; não oculta menus nesta entrega. Precificação e seu alinhamento
aos custos/snapshots continuam pendentes, assim como dashboards avançados
e etapas seguintes do planejamento.

## Aplicação

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-envase-detalhes-estorno-2b.patch
```

## Rotas e permissões

- Página: `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_LOTE>&envase_id=<ID_ENVASE>`.
- Fragmento: `/brewstation/plant-workspace/<ID_PLANTA>/tab/sessions?session_id=<ID_LOTE>&envase_id=<ID_ENVASE>`.
- Ação: `POST /brewstation/plant-workspace/<ID_PLANTA>/sessions/<ID_LOTE>/envases/<ID_ENVASE>/reverse` com `motivo`.

A consulta do fragmento exige `brew_sessions.list`; a seleção de envase exige
adicionalmente `envases.list` e `envases.detail`. O POST exige essas três
permissões e `envases.update`, usuário autenticado, planta/lote/envase ativos
e todos os vínculos corretos. Atualização do lote não é necessária porque
nenhum dado do lote é alterado por esse estorno.

Envase explícito inválido, apagado ou de outro lote retorna 404. Detalhe sem
permissão retorna 403; o formulário não aparece sem atualização de envase.
O POST responde JSON e sua UI permanece nos detalhes do mesmo lote. Falhas
inesperadas retornam mensagem genérica sem expor informações internas.

## Testes

Focados nos novos casos e na regra de estorno existente:

```powershell
python -m pytest tests/test_plant_workspace.py tests/test_feature_envase.py -k "estorno or envase_detalhes or envase_legado" -q
```

Regressão recomendada para a entrega:

```powershell
python -m pytest tests/test_plant_workspace.py tests/test_feature_envase.py tests/test_addon_estoque.py tests/test_dashboard_runtime.py -q
```

Casos novos: consulta repetida sem escrita, retorno ao lote histórico,
permissões, pertencer à planta/lote, apagados, parâmetro inválido, motivo
vazio/longo, legado sem snapshot, preservação de custo/lote/snapshot,
repetição sem devolução adicional, rollback quando o log falha. Os testes
existentes verificam falha na segunda devolução e integridade do ledger.

Executado neste ambiente (Python 3.12/Linux): **448 passed, sem warnings**,
em 495,72s na regressão indicada, mais **1 passed** em 2,37s para o caso
adicional de legado/seleção inválida/URL direta, acrescentado após a coleta
da regressão. Sintaxe Python/JSON, templates Jinja, JavaScript (`node --check`)
e `git diff --check` verificados. Patch aplicado por `git am --keep-cr` em
checkout isolado com árvore final idêntica. Teste visual em navegador e
validação da entrega no Windows continuam pendentes.

## Roteiro visual

1. Abra Sessões no workspace; escolha um lote antigo e clique em um envase.
   Confira que permanece na aba/planta/lote e vê dados e custos registrados.
2. Feche detalhes e reabra. Abra também a URL direta com os três IDs; confira
   a seleção correta. Alterne Dashboard/Sessões e verifique navegação normal.
3. Em um envase de teste com snapshot, informe o motivo e clique em estornar.
   Cancele o modal: nada muda. Confirme em nova tentativa: veja toast,
   cancelamento, motivo/operador/horário, devoluções e log na sessão.
4. Confira entradas de embalagem no ledger e saldo; o consumo/custo de
   ingredientes e dados operacionais do lote devem permanecer iguais.
5. Recarregue: não há segundo botão de estorno; o histórico continua visível.
   Confira um legado sem snapshot: aviso de reconciliação, sem formulário.
6. Teste usuário sem `envases.update`: detalhes legíveis sem ação. Teste sem
   `envases.detail`: lista sem links de detalhes; URL direta não dá acesso.
7. Confira leitura e contraste nos temas claro/escuro e tela estreita. A
   tabela de snapshot deve rolar horizontalmente sem esconder o formulário.

Usar lote/envase de teste para a etapa de confirmação, pois o estorno real
cancela o registro e devolve suas embalagens.
