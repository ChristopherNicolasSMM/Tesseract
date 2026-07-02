# 05 — Casos de Uso (Feature Mash Control)

## UC01 — Cadastrar receita
- **Ator**: usuário com `mash_recipes.create`

## UC02 — Cadastrar planta e vasilhames
- **Ator**: usuário com `brew_plants.create`/`brew_plant_vessels.create`
- **Fluxo**: planta → vasilhame → mapeamento pra uma Função do
  device_manager (referência fraca, cross-Addon)

## UC03 — Acompanhar uma sessão de brassagem
- **Ator**: usuário com `brew_sessions.*`
- **Fluxo**: criar sessão (vinculada a receita+planta) → registrar
  passos → logs → alarmes
- **Limitação atual**: avanço de status é manual — sem motor de
  processo automático

## UC04 — Criar regra de automação (definição apenas)
- **Ator**: usuário com `automation_rules.create`
- **Fluxo**: escolhe sensor (Função), condição, ator (Função), ação —
  ambos resolvidos por referência fraca contra `addon_device_manager`
- **Limitação atual**: a regra fica registrada, mas nenhum motor
  avalia o sensor continuamente — execução fora do escopo desta fase

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

## UC06 — Editar receita → nova versão automática — novo
- **Ator**: usuário com `mash_recipes.edit`
- **Fluxo principal**: edita receita existente e salva → sistema cria
  nova linha (`versao` + 1), nunca sobrescreve a versão anterior →
  grava snapshot em `RecipeHistory`
- **Fluxo alternativo**: usuário consulta histórico → compara duas
  versões lado a lado (lê `RecipeHistory` ou as próprias linhas
  versionadas de `MashRecipe`+`RecipeIngredient`)
- **Permissão RBAC**: `mash_recipes.edit`, `mash_recipes.view_history`
