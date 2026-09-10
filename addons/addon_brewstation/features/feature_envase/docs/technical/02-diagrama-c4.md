# 02 — Diagrama C4 (Feature Envase — Componente)

```mermaid
C4Component
    title feature_envase - Componentes (pos skill 26)

    Component(envase, "Envase", "Model", "lote_id, material_resultante_id, quantidade_litros, data_envase, tipo_envase, status")
    Component(item, "ItemEnvase", "Model (historico)", "envase_id, material_id, quantidade - sem INSERT novo desde skill 26")
    Component(svc_env, "envase_estoque_service", "Python service", "registrar_envase(), calcular_custo_industrializacao_envase()")
    Component(session_ext, "BrewSession", "Model (outra Feature)", "feature_mash_control - insumos_baixados_em, custo_total_insumos")
    Component(svc_ing_ext, "ingredient_consumption_service", "Python service (outra Feature)", "feature_mash_control - confirmar_consumo_ingredientes()")
    Component(lookup_ext, "material_lookup", "Service publico (outro Addon)", "addon_estoque - get_material(), get_composicao()")
    Component(mov_ext, "estoque_service", "Service publico (outro Addon)", "addon_estoque - registrar_movimentacao()")

    Rel(envase, session_ext, "lote_id -> FK real, cross-Feature")
    Rel(envase, lookup_ext, "material_resultante_id -> referencia fraca, cross-Addon")
    Rel(svc_env, svc_ing_ext, "chamada direta (mesmo Addon, Features diferentes) - fallback se insumo ainda nao confirmado")
    Rel(svc_env, lookup_ext, "get_material() (volume_real) + get_composicao() (componentes)")
    Rel(svc_env, mov_ext, "chamada sincrona: registrar_movimentacao(saida) - um por componente resolvido")
```

`ItemEnvase` não aparece mais como destino de nenhuma relação a partir
de `envase_estoque_service` — fica desenhado no diagrama só pra deixar
claro que a tabela existe (dado histórico), não porque o service atual
escreve nela.
