# 03 — Fluxos (Feature Brew Father)

Fluxo completo (parse da API + resolução de ingrediente) documentado
em `features/feature_mash_control/docs/technical/03-fluxos.md`
("Sequência: importação de receita + resolução de ingrediente") — não
duplicado aqui pra evitar dessincronia entre os dois documentos.

Responsabilidade exclusiva desta Feature: consultar a API BrewFather e
converter o payload pro formato de entrada que
`ingredient_resolution_service` espera (descrição + quantidade +
unidade por ingrediente).

## Sequência: sincronização seletiva (skill 27, 2026-09-01)

Este fluxo é exclusivo desta Feature (não existe equivalente em
`feature_mash_control`) — a API do BrewFather não expõe filtro por
tag/pasta no servidor, então a seleção acontece inteiramente aqui.

```mermaid
sequenceDiagram
    participant User as Usuário
    participant UI as Tela "Receitas Disponíveis"
    participant Sync as sync_service
    participant Client as brewfather_client
    participant Recipe as tesseract_brewstation_mashctrl_recipe
    participant Resolve as ingredient_resolution_service

    User->>UI: Abre "Selecionar Receitas pra Sincronizar"
    UI->>Sync: listar_receitas_disponiveis()
    Sync->>Client: list_recipes_basico()
    Client-->>Sync: lista crua (id, name, style, type) — sem detalhe
    loop para cada receita da lista
        Sync->>Recipe: existe MashRecipe com esse origem_receita_id? (ativa/apagada/nenhuma)
    end
    Sync-->>UI: lista + status (nova/já importada/apagada — pendente de reimportar)

    User->>UI: Marca algumas, clica "Sincronizar selecionadas"
    UI->>Sync: sincronizar_selecionadas([id1, id2, ...])
    loop só pras marcadas
        Sync->>Client: get_recipe_normalizado(id)
        Client-->>Sync: receita completa, normalizada
        Sync->>Resolve: resolve ingredientes, grava MashRecipe
    end
    Sync-->>UI: log (BrewFatherSync) com quantidade processada/erro
```

O status "apagada — pendente de reimportar" depende da correção feita
na skill 25 (`_importar_receita` passou a filtrar `is_deleted=False`
na deduplicação) — sem ela, uma receita apagada nunca seria
reimportada de verdade, mesmo marcada de novo aqui.
