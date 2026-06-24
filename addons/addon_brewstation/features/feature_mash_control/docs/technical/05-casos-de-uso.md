# 05 — Casos de Uso (Feature Mash Control)

## UC01 — Cadastrar receita
- **Ator**: usuário com `mash_recipes.create`

## UC02 — Cadastrar planta e vasilhames
- **Ator**: usuário com `brew_plants.create`/`brew_plant_vessels.create`
- **Fluxo**: planta → vasilhame → mapeamento pra uma Função do device_manager

## UC03 — Acompanhar uma sessão de brassagem
- **Ator**: usuário com `brew_sessions.*`
- **Fluxo**: criar sessão (vinculada a receita+planta) → registrar
  passos → logs → alarmes
- **Limitação atual**: avanço de status é manual — sem motor de
  processo automático

## UC04 — Criar regra de automação (definição apenas)
- **Ator**: usuário com `automation_rules.create`
- **Fluxo**: escolhe sensor (Função), condição, ator (Função), ação
- **Limitação atual**: a regra fica registrada, mas **nenhum motor
  avalia o sensor continuamente** — execução fora do escopo desta fase
