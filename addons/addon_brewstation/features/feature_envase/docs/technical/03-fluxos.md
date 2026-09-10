# 03 — Fluxos (Feature Envase)

## Caminho feliz: registro de Envase → Composição → baixa síncrona

```mermaid
sequenceDiagram
    participant User as Usuário
    participant UI as Tela Envase
    participant EnvSvc as envase_estoque_service
    participant IngSvc as ingredient_consumption_service (feature_mash_control)
    participant Lookup as material_lookup (addon_estoque)
    participant Envase as tesseract_brewstation_env_envase
    participant EstSvc as estoque_service (addon_estoque)
    participant Saldo as tesseract_estoque_saldo

    User->>UI: Registra envase do Lote X (Material resultante + litros)
    UI->>EnvSvc: registrar_envase(lote_id, material_resultante_id, quantidade_litros)
    EnvSvc->>Lookup: get_material(material_resultante_id)
    Lookup-->>EnvSvc: volume_real (obrigatório — sem ele, VolumeRealNaoConfiguradoError)

    alt lote.insumos_baixados_em is None
        EnvSvc->>IngSvc: confirmar_consumo_ingredientes(lote_id)
        Note over EnvSvc,IngSvc: fallback — nunca deixa um Envase<br/>acontecer sem custo de insumo rastreado
        IngSvc-->>EnvSvc: custo_total_insumos gravado em BrewSession
    end

    EnvSvc->>Envase: INSERT envase (lote_id, material_resultante_id, quantidade_litros, ...)
    EnvSvc->>Lookup: get_composicao(material_resultante_id)
    Lookup-->>EnvSvc: [{material_componente_id, quantidade}, ...]

    loop para cada componente da Composição
        EnvSvc->>EnvSvc: quantidade_total = componente.quantidade * (litros / volume_real)
        EnvSvc->>EstSvc: registrar_movimentacao(material_componente_id, "saida", quantidade_total)
        EstSvc->>Saldo: atualiza quantidade_atual
    end

    EnvSvc-->>UI: envase confirmado, unidades_geradas, componentes_baixados
```

`ItemEnvase` não é mais criado em nenhum passo deste fluxo — os
componentes vêm inteiramente da Composição do Material resultante.

## Cálculo de custo de industrialização (sob demanda, não no registro)

```mermaid
sequenceDiagram
    participant User as Usuário/API
    participant EnvSvc as envase_estoque_service
    participant Envase as tesseract_brewstation_env_envase
    participant Lookup as material_lookup (addon_estoque)

    User->>EnvSvc: calcular_custo_industrializacao_envase(envase_id)
    EnvSvc->>Envase: soma quantidade_litros de todos os Envases do mesmo lote_id
    Note over EnvSvc: custo_cerveja = (BrewSession.custo_total_insumos / litros_do_lote)<br/>* quantidade_litros deste Envase
    EnvSvc->>Lookup: get_composicao(material_resultante_id)
    loop para cada componente
        EnvSvc->>Lookup: get_saldo(material_componente_id) -> custo_medio
        Note over EnvSvc: custo_linha = quantidade_total * custo_medio
    end
    EnvSvc-->>User: {custo_cerveja, custo_componentes, custo_total_industrializacao, detalhe_componentes}
```

Este cálculo não grava nada — pode ser chamado quantas vezes quiser,
a qualquer momento depois do Envase existir (mesmo raciocínio de
"cálculo separado de commit" já usado em
`ingredient_consumption_service.calcular_custo_insumos_receita()`).
