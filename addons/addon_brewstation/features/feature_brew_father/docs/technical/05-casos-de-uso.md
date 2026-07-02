# 05 — Casos de Uso (Feature Brew Father)

## UC01 — Sincronizar com BrewFather
- **Ator**: usuário com `bf_sync.execute`
- **Pré-condição**: `BREWFATHER_USER_ID`/`BREWFATHER_API_KEY`
  configurados (`env_keys`)
- **Fluxo principal**: escolhe escopo (Receitas/Lotes/Inventário/Tudo)
  → sistema busca na API e delega a `ingredient_resolution_service`
  (`feature_mash_control`) → receita salva com
  `origem_receita="BrewFather"`
- **Fluxo alternativo**: erro de rede/API → log de sincronização
  registra `status="erro"`
- **Permissão RBAC**: `bf_sync.execute`, `bf_sync.view_log`
