# 03 — Fluxos (Addon Estoque)

## Fluxo 1 — Cadastro de Material + entrada de estoque (caminho feliz)

```mermaid
sequenceDiagram
    participant User as Usuário
    participant UI as Tela Materiais
    participant Svc as material_service
    participant DB as tesseract_estoque_material

    User->>UI: Cadastra novo Material (nome, categoria, unidade_medida...)
    UI->>Svc: create_material(dados)
    Svc->>DB: INSERT material
    DB-->>Svc: material.id

    User->>UI: Registra movimentação de entrada (compra)
    UI->>Svc: registrar_movimentacao(material_id, tipo="entrada", quantidade, custo_unitario, lote_fornecedor)
    Svc->>Svc: grava em tesseract_estoque_movimentacao (ledger, imutável)
    Svc->>Svc: recalcula tesseract_estoque_saldo (quantidade_atual += quantidade, custo_medio ponderado)
    Svc-->>UI: saldo atualizado
```

## Fluxo 2 — Consumo por Addon externo (leitura via service público)

```mermaid
sequenceDiagram
    participant Ext as Addon externo (ex.: addon_brewstation)
    participant Lookup as material_lookup (service público)
    participant DB as tesseract_estoque_material / _saldo

    Ext->>Lookup: get_material(material_id) OU buscar_material_por_termo(texto)
    Lookup->>DB: SELECT
    DB-->>Lookup: dados de Material/Saldo
    Lookup-->>Ext: retorno (nunca o objeto ORM em si — só dado primitivo)
```

`buscar_material_por_termo` existe especificamente pro fluxo de
resolução de ingrediente de `feature_mash_control` (importação de
receita externa, tentativa de casar descrição textual com Material já
cadastrado). Espelha a mesma regra de fronteira já usada em
`device_manager` (skill 05, seção 6): cross-Addon nunca enxerga ORM de
outro módulo, só o retorno do service público.

## Interação com o `EventBus` — pendência

Ainda não há publicação de evento via `core/event_bus.py` — o desenho
atual usa só chamada direta e síncrona ao service público. Se no
futuro algum Addon quiser reagir a mudança de estoque sem polling
(ex.: alerta de estoque mínimo), o evento seguiria a convenção da
skill 00 (`estoque.saldo.abaixo_do_minimo`) — não desenhado ainda.
