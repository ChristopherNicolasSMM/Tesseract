# Precificação 2C.1 — custos registrados

## Problema e resultado

O motor recalculava os ingredientes pelo preço atual mesmo após confirmação
do lote; embalagens eram lidas somente de ItemEnvase, que não recebe os
registros novos baseados na composição. A precificação agora:

- Usa `custo_total_insumos` quando `insumos_baixados_em` está preenchido.
  Zero registrado é válido; ausência de custo em lote confirmado bloqueia
  novo cálculo até conferência. Não fabrica linhas históricas de ingredientes.
- Usa `componentes_snapshot` para embalagens, inclusive snapshot vazio.
  Custo de linha/unitário ausente bloqueia, sem substituir por preço atual.
  Persistência de linha identifica `origem_preco=registrado`.
- Mantém estimativa por preço atual/padrão antes da confirmação e fallback
  ItemEnvase para legados sem snapshot. Ingredientes ignorados não entram.
  Vínculo ausente, preço ausente, conversão não confiável e ausência de
  itens de embalagem legados sinalizam estimativa incompleta.
- Rejeita lote apagado e envase inexistente, apagado, cancelado ou de outro
  lote na simulação/cálculo; vínculo posterior também valida o lote ativo.
  Troca de vínculo de cálculo já associado a outro envase é rejeitada.
- Usa getters públicos do estoque para saldo/unidade-base/material.
- Abre precificação pelo detalhe do envase, com combos padrão preenchidos e
  retorno à mesma sessão/envase. A URL explícita inválida retorna 404.
- Mostra origem e escopo do custo na tela; nomes/unidades renderizados nas
  linhas são escapados. Simular não escreve, salvar grava apenas cálculo.

**Limite deliberado:** continua usando ingredientes do **lote inteiro** mais
embalagens do envase selecionado. Não é preço unitário ou rateio por envase.
A consolidação do rateio (2C.2) permanece pendente e terá de respeitar a regra
existente de industrialização, conferida no próximo incremento. Não altera
percentuais/fórmulas fiscais existentes. Cálculos já salvos não são refeitos
ou apagados depois do estorno; associar um envase não recalcula esses valores.
As flags da resposta são metadados da execução atual, não novas colunas nem
classificação retroativa de cálculos antigos.

## Aplicação e banco

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-precificacao-custos-registrados-2c1.patch
```

**Não exige `db upgrade`.** Somente acrescenta valor na annotation enum do
String(20) já existente, sem mudar schema. Controllers/services/templates de
precificação são manuais. Sem alteração da regra de movimentação, snapshots,
timers, status/etapas do lote, confirmação de ingredientes ou menus.
2B foi validado pelo usuário; 2C.1 aguarda sua validação local.

## Rotas

- Lote: `/brewstation/precificacao-envase/?lote_id=<ID_LOTE>`.
- Contexto de envase: `/brewstation/precificacao-envase/?lote_id=<ID_LOTE>&envase_id=<ID_ENVASE>`.
- Detalhes/retorno: `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_LOTE>&envase_id=<ID_ENVASE>`.
- API existente: POST `/api/brewstation/precificacao-envase/simular`,
  `/calcular` e `/<ID_CALCULO>/vincular-envase`.

Permissões existentes mantidas: `envases.list` na tela/simulação e
`envases.create` ao salvar/vincular. O servidor valida pertencimento/status
mesmo que um combo forneça um envase incompatível. Nenhuma consulta/salvamento
confirma ingredientes ou movimenta estoque.

## Testes

```powershell
python -m pytest tests/test_precificacao_envase.py tests/test_feature_envase.py tests/test_plant_workspace.py -q
```

Testes novos cobrem custo congelado zero/positivo, ausência de custo
registrado, snapshot prevalecendo sobre ItemEnvase/preço atual, snapshot
vazio/incompleto, estimativa legada/ingrediente ignorado/pendência, bloqueio
de envase inválido e lote apagado, ausência de movimentações adicionais e
preenchimento/retorno contextual. Valores salvos permanecem históricos.

Executado em Python 3.12/Linux, sem warnings: **82 passed** na seleção de
precificação/envase/retorno existente; **2 passed** nos testes de contexto e
retorno; após acrescentar a proteção de lote apagado no vínculo, suíte final
de precificação: **23 passed** em 22,08s. A suíte inteira de workspace não
foi reexecutada neste incremento. Sintaxe Python/JSON/JS, templates Jinja e
`git diff --check` verificados; aplicação por `git am --keep-cr` em checkout
isolado com árvore final idêntica. Testes visuais e validação no Windows
continuam pendentes.

## Roteiro visual

1. Abra um lote ainda não confirmado na precificação e simule. Confira
   “estimativa” e eventual aviso de incompletude; nenhuma baixa deve ocorrer.
2. Em lote confirmado, simule e confira que o total coincide com o custo
   registrado em Sessões. O resultado explica que não há detalhe histórico
   por material disponível para esse total.
3. Nos detalhes de envase registrado, use “Abrir precificação com este envase”.
   Ambos os combos devem vir preenchidos. Confira embalagens/custos iguais
   ao snapshot e “Registrado no envase”. Retorne aos mesmos detalhes.
4. Abra um legado sem snapshot: identifique embalagens como estimativa atual.
   Cancelado não deve oferecer esse atalho e sua URL explícita é rejeitada.
5. Calcular e Salvar grava somente precificação; saldo, ledger, confirmação
   de ingredientes, lote e snapshot devem permanecer iguais.
6. Confira a indicação de lote completo/sem rateio e a legibilidade nos temas
   claro/escuro. Validação visual no navegador permanece local.
