# 02 — Diagrama C4 (Addon BrewStation — Componente)

```mermaid
C4Component
    title addon_brewstation — Features

    Container_Boundary(brewstation, "addon_brewstation") {
        Component(yeastbank, "feature_yeast_bank", "8 entidades", "Cepas, itens do banco, leituras, motor de viabilidade")
        Component(mashcontrol, "feature_mash_control", "15 entidades", "Receitas, plantas, sessoes, dashboards, regras, ingredientes de receita")
        Component(brewfather, "feature_brew_father", "0 tabela propria", "Sync service + log - grava em MashRecipe/BrewSession")
        Component(ingredientes, "feature_ingredientes", "3 entidades", "Malte/Lupulo/Levedura - specs complementares a Material")
        Component(envase, "feature_envase", "2 entidades", "Evento de empacotamento de um Lote")
    }

    Container_Boundary(devicemanager_ext, "addon_device_manager") {
        Component(devicefunc_lookup, "device_function_lookup", "Service publico")
    }
    Container_Boundary(estoque_ext, "addon_estoque") {
        Component(material_lookup, "material_lookup", "Service publico")
    }

    Rel(envase, mashcontrol, "FK real cross-Feature: lote_id -> BrewSession.id")
    Rel(brewfather, mashcontrol, "chama ingredient_resolution_service, grava com origem_receita=BrewFather")
    Rel(mashcontrol, devicefunc_lookup, "referencia fraca cross-Addon (nao mais FK cross-Feature)")
    Rel(mashcontrol, material_lookup, "referencia fraca cross-Addon - resolucao de ingrediente")
    Rel(ingredientes, material_lookup, "referencia fraca cross-Addon")
    Rel(envase, material_lookup, "chamada sincrona - baixa de estoque")
```

Ver C4 do Sistema (`docs/technical/02-diagrama-c4.md` da raiz) para o
nível Container completo, incluindo o Core — **ainda não atualizado**
com as caixas de `addon_estoque` e a promoção de `addon_device_manager`
(pendência).

## Correção desta rodada

O diagrama anterior mostrava `feature_device_manager` como componente
interno deste Addon com `Rel` de "FK cross-Feature". Isso ficou
desatualizado desde a promoção a Addon independente (skill 05) — o
código já usava referência fraca; só este diagrama não tinha
acompanhado.
