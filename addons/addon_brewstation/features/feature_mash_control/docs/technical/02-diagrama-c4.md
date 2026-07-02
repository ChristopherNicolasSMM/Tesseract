# 02 — Diagrama C4 (Feature Mash Control — Componente)

```mermaid
C4Component
    title feature_mash_control — Componentes

    Component(recipe, "MashRecipe", "Model", "Receita canonica - origem_receita, origem_receita_id, versao")
    Component(recipe_ingr, "RecipeIngredient", "Model", "Linha de ingrediente - material_id (referencia fraca)")
    Component(recipe_map, "IngredientMapping", "Model", "Cache de-para: origem+descricao -> material_id")
    Component(recipe_hist, "RecipeHistory", "Model", "Snapshot JSON por versao criada")
    Component(resolve_svc, "ingredient_resolution_service", "Python service", "Resolve ingrediente contra addon_estoque, reaproveitavel por futuros importadores")
    Component(plant, "BrewPlant/Vessel/Mapping", "Model", "Estrutura fisica")
    Component(session, "BrewSession/Step/Log/Alarm", "Model", "Execucao de uma brassagem (Lote)")
    Component(dashboard, "DashboardLayout/Widget", "Model", "Layout visual")
    Component(rule, "AutomationRule/Log", "Model", "Definicao de regra")

    Container_Boundary(devicemanager_ext, "addon_device_manager") {
        Component(devicefunc_lookup, "device_function_lookup", "Service publico")
    }
    Container_Boundary(estoque_ext, "addon_estoque") {
        Component(material_lookup, "material_lookup", "Service publico")
    }

    Rel(plant, devicefunc_lookup, "referencia fraca (cross-Addon)")
    Rel(rule, devicefunc_lookup, "referencia fraca (cross-Addon)")
    Rel(dashboard, devicefunc_lookup, "referencia fraca (cross-Addon)")
    Rel(resolve_svc, material_lookup, "chamada sincrona: buscar_material_por_termo()")
    Rel(recipe_ingr, resolve_svc, "usa na importacao")
    Rel(recipe_map, resolve_svc, "consultado antes de perguntar ao usuario")
    Rel(recipe, recipe_ingr, "possui")
    Rel(recipe, recipe_hist, "gera snapshot a cada nova versao")
    Rel(session, recipe, "usa uma versao")
```

## Correção desta rodada

As `Rel` pra `addon_device_manager` eram descritas como "FK
cross-Feature" no diagrama anterior — **estava desatualizado**: desde
a promoção de `device_manager` a Addon independente (skill 05), a
relação real é referência fraca via service público
(`device_function_lookup`), sem FK. O código já refletia isso; só o
diagrama não tinha acompanhado.
