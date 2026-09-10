# 05 — Casos de Uso (Feature Brew Father)

## UC01 — Sincronizar todas as receitas do BrewFather

> **Correção (auditoria 2026-09-01)**: a versão anterior deste UC
> descrevia "escolhe escopo (Receitas/Lotes/Inventário/Tudo)" — isso
> nunca existiu no código real. `sync_service.py` só implementa
> `sync_recipes()` (receitas); não há sincronização de lotes ou
> inventário. Corrigido abaixo pra refletir o que existe de fato.

- **Ator**: usuário autenticado (rota `brewfather_syncs.sincronizar`)
- **Pré-condição**: `BREWFATHER_USER_ID`/`BREWFATHER_API_KEY`
  configurados (`env_keys`); `BREWFATHER_ENABLED=true`
- **Fluxo principal**: clica "Sincronizar Tudo" → sistema busca todas
  as receitas na API e delega a `ingredient_resolution_service`
  (`feature_mash_control`) → cada receita salva com
  `origem_receita="BrewFather"`
- **Fluxo alternativo**: erro de rede/API → log de sincronização
  (`BrewFatherSync`) registra `status="erro"`
- **Permissão RBAC**: `brewfather_syncs.create`

## UC02 — Sincronizar receitas selecionadas (skill 27, 2026-09-01)
- **Ator**: usuário autenticado
- **Pré-condição**: mesma do UC01
- **Fluxo principal**: acessa "Selecionar Receitas pra Sincronizar" →
  sistema lista as receitas disponíveis (sem gastar chamada de
  detalhe) com um selo de status em cada uma → usuário marca algumas →
  clica "Sincronizar selecionadas" → só o detalhe completo das
  marcadas é buscado e importado
- **Fluxo alternativo**: receita marcada já tinha sido apagada no
  Tesseract → reimportada como nova versão (depende da correção da
  skill 25 no filtro de deduplicação — ver `04-modelo-de-dados.md`)
- **Permissão RBAC**: `brewfather_syncs.list` (listar),
  `brewfather_syncs.create` (sincronizar)
