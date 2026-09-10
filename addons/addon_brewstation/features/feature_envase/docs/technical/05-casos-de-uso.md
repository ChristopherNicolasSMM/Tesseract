# 05 — Casos de Uso (Feature Envase)

## UC01 — Registrar Envase de um Lote

- **Ator**: usuário com `envase.create` (ou `envases.create`, ver
  permissão real gerada)
- **Pré-condição**: Lote (`BrewSession`) existente; Material
  resultante cadastrado em `addon_estoque` com `volume_real`
  preenchido e Composição definida
- **Fluxo principal**: acessa Envase → Novo → escolhe Lote, escolhe o
  Material resultante (produto acabado) e informa a quantidade em
  litros → salva → sistema calcula quantas unidades isso representa
  (`litros / volume_real`) e dá baixa automática em cada componente da
  Composição do Material resultante
- **Fluxo alternativo A**: lote ainda não teve o consumo de insumo da
  receita confirmado → sistema confirma automaticamente antes de
  prosseguir (ver UC02) — nunca bloqueia o Envase por isso
- **Fluxo alternativo B**: Material resultante sem `volume_real`
  preenchido → erro explícito (`VolumeRealNaoConfiguradoError`),
  Envase não é criado
- **Fluxo alternativo C**: Material de embalagem (componente) sem
  saldo suficiente → mesmo comportamento de `addon_estoque` (pendência
  em aberto, ver `01-visao-geral.md`) — hoje não bloqueia, só deixa o
  saldo negativo
- **Permissão RBAC**: `envases.create`

## UC02 — Confirmar Ingredientes (consumo de insumo da receita)

- **Ator**: usuário com `brew_sessions.update`
- **Pré-condição**: Lote (`BrewSession`) com receita vinculada
- **Fluxo principal**: na tela do Lote, clica em "Confirmar
  Ingredientes" → sistema dá baixa de cada `RecipeIngredient`
  resolvido (com `material_id` preenchido) contra o estoque real,
  captura o custo médio de cada um no momento, grava
  `BrewSession.insumos_baixados_em`/`custo_total_insumos`
- **Fluxo alternativo**: lote já confirmado antes → botão não aparece
  mais (tela mostra o custo já congelado); chamar a função de novo é
  idempotente, não desconta duas vezes
- **Fluxo alternativo**: usuário pula esse passo e vai direto pro
  Envase → UC01 dispara essa confirmação sozinho, como fallback
- **Permissão RBAC**: `brew_sessions.update` (esta rota mora em
  `feature_mash_control`, não em `feature_envase`, mas é parte do
  mesmo fluxo de negócio — ver `feature_mash_control/docs/technical/05-casos-de-uso.md`)

## UC03 — Consultar Custo de Industrialização de um Envase

- **Ator**: qualquer usuário com acesso de leitura
- **Pré-condição**: Envase já registrado (UC01)
- **Fluxo principal**: chama
  `calcular_custo_industrializacao_envase(envase_id)` → sistema
  retorna o custo da parte cerveja (rateado do lote) + custo dos
  componentes de embalagem (via Composição × custo médio de cada um)
- **Observação**: não é uma tela própria ainda — hoje é só a função de
  service, sem UI dedicada (ver pendência em `01-visao-geral.md`)
