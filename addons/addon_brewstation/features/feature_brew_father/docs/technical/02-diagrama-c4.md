# 02 — Diagrama C4 (Feature Brew Father — Componente)

```mermaid
C4Component
    title feature_brew_father - Componentes (pos skill 27)

    Component(client_basico, "brewfather_client.list_recipes_basico", "Python function", "GET /v2/recipes cru, sem normalizar - so pra listagem")
    Component(client_detail, "brewfather_client.get_recipe_normalizado", "Python function", "detalhe de 1 receita, normalizado")
    Component(client_all, "brewfather_client.get_recipes", "Python function", "compoe os dois acima, usado so por sync_recipes()")
    Component(sync_svc, "sync_service.sync_recipes", "Python service", "importa TODAS as receitas de uma vez")
    Component(sync_listar, "sync_service.listar_receitas_disponiveis", "Python service", "skill 27 - listagem enxuta + status (nova/ja importada/apagada)")
    Component(sync_seletiva, "sync_service.sincronizar_selecionadas", "Python service", "skill 27 - importa so os ids marcados")
    Component(log, "BrewFatherSync", "Model", "Log de sincronizacao - status, erro, raw_data")
    Component(recipe_ext, "MashRecipe/RecipeIngredient", "Model (outra Feature)", "feature_mash_control")
    Component(resolve_ext, "ingredient_resolution_service", "Service (outra Feature)", "feature_mash_control")

    Rel(sync_svc, client_all, "busca todas as receitas")
    Rel(sync_listar, client_basico, "so a listagem enxuta, sem detalhe")
    Rel(sync_listar, recipe_ext, "cruza com origem_receita_id ja conhecidos")
    Rel(sync_seletiva, client_detail, "so das receitas marcadas")
    Rel(sync_svc, resolve_ext, "chama apos parse - resolve ingredientes")
    Rel(sync_seletiva, resolve_ext, "idem, por receita selecionada")
    Rel(resolve_ext, recipe_ext, "grava com origem_receita=BrewFather")
    Rel(sync_svc, log, "registra resultado da sincronizacao")
    Rel(sync_seletiva, log, "registra resultado (mesmo tipo_sync=recipes)")
```
