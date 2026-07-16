# 05 — Casos de Uso (Feature Mash Control)

## UC01 — Cadastrar receita
- **Ator**: usuário com `mash_recipes.create`

## UC02 — Cadastrar planta e tanques
- **Ator**: usuário com `brew_plants.create`/`brew_plant_vessels.create`
- **Fluxo**: planta → tanque → mapeamento pra uma Função do
  device_manager (referência fraca, cross-Addon)

## UC03 — Acompanhar uma sessão de brassagem
- **Ator**: usuário com `brew_sessions.*`
- **Fluxo**: gerar sessão a partir de uma receita (copia a timeline de
  Etapas como `pending`) → operar via Dashboard (ver UC07) ou tela de
  Sessão → logs → alarmes

## UC04 — Criar regra de automação
- **Ator**: usuário com `automation_rules.create`
- **Fluxo**: escolhe sensor (Função), condição, ator (Função), ação —
  ambos resolvidos por referência fraca contra `addon_device_manager`
- **Execução**: motor event-driven (`automation_engine.py`) — reage a
  cada `device_manager.actor.value_changed` publicado no EventBus,
  sem polling. Cada disparo grava em `AutomationRuleLog` (valor,
  ação, sucesso/erro)

## UC05 — Importar receita externa (BrewFather/BeerSmith/BeerXML) — novo
- **Ator**: usuário com `mash_recipes.import`
- **Pré-condição**: integração de origem configurada (ex.:
  `feature_brew_father` com `env_keys` preenchidos)
- **Fluxo principal**: escolhe origem → sistema importa receita e
  ingredientes → cada ingrediente é resolvido contra `addon_estoque`
  (automático se já mapeado antes, senão vai pra pendência) → usuário
  revisa pendências de-para (mapeia pra Material existente ou cadastra
  um novo) → receita salva como nova versão
- **Fluxo alternativo**: nenhum ingrediente pendente → import
  totalmente automático, sem intervenção
- **Permissão RBAC**: `mash_recipes.import`, `ingredient_mapping.resolve`

## UC06 — Editar receita → nova versão automática
- **Ator**: usuário com `mash_recipes.edit`
- **Fluxo principal**: edita receita existente e salva → sistema cria
  nova linha (`versao` + 1), nunca sobrescreve a versão anterior →
  grava snapshot em `RecipeHistory`
- **Fluxo alternativo**: usuário consulta histórico → compara duas
  versões lado a lado (lê `RecipeHistory` ou as próprias linhas
  versionadas de `MashRecipe`+`RecipeIngredient`)
- **Permissão RBAC**: `mash_recipes.edit`, `mash_recipes.view_history`

## UC07 — Operar uma sessão pelo card de Etapa do Dashboard — novo
- **Ator**: usuário com `dashboard_layouts.update`
- **Pré-condição**: Dashboard com widget `step_card`, vinculado a uma
  Planta com sessão `active`
- **Fluxo principal**: primeira etapa `pending` vira `active` sozinha
  na primeira leitura do card → operador acompanha rampa/hold →
  clica "Concluir e Avançar" (disponível a qualquer momento, não só
  quando o tempo acaba) → próxima etapa vira `active`
- **Fluxo alternativo — voltar**: operador clica "Voltar" → etapa
  atual volta a `pending`, etapa anterior reativa com timer reiniciado
- **Fluxo alternativo — editar a receita em operação**: operador abre
  "Gerenciar Etapas" → adiciona/edita/remove `RecipeStep` → clica
  "Ressincronizar com a sessão" → `BrewSessionStep` `pending` são
  criados/atualizados/removidos conforme a receita; etapa já
  `active`/`completed`/`skipped` nunca é tocada
- **Permissão RBAC**: `dashboard_layouts.update`, `recipe_steps.create`/`update`/`trash` (pro sub-fluxo de editar receita)

## UC08 — Montar um Dashboard (paleta + painel + tubulação) — novo
- **Ator**: usuário com `dashboard_widgets.create`/`dashboard_layouts.update`
- **Fluxo principal**: modo edição → arrasta ícone da paleta pro
  canvas → widget nasce solto (`vessel_id`/`device_function_name`
  nulos) → clica no widget → painel lateral abre → escolhe o vínculo
  → salva
- **Fluxo alternativo — tubulação**: com Planta vinculada, botão
  "Tubulação" → escolhe origem/destino/atuador de fluxo → linha
  aparece no canvas → seleciona a linha → arrasta trechos pra curvar,
  pontas pra reancorar, `Delete` num ponto selecionado pra remover
- **Caso especial — recirculação**: origem == destino → nasce com uma
  alcinha padrão pra fora do tanque, em vez de reta escondida atrás
  do próprio widget
- **Permissão RBAC**: `dashboard_widgets.create`, `dashboard_widgets.update`, `dashboard_widgets.trash`
