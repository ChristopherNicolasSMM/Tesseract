# 04 — Modelo de Dados (Feature Envase)

```mermaid
erDiagram
    ENVASE ||--o{ ITEM_ENVASE : "contem"

    ENVASE {
        int id PK
        int lote_id FK "FK real -> feature_mash_control.session.id, cross-Feature"
        float quantidade_litros
        date data_envase
        string tipo_envase
        string status
        datetime created_at
    }
    ITEM_ENVASE {
        int id PK
        int envase_id FK
        int material_id "SEM FK - addon_estoque"
        float quantidade
    }
```

Tabelas reais: `tesseract_brewstation_env_envase`,
`tesseract_brewstation_env_item`.

`lote_id` é FK real porque `feature_mash_control` é do mesmo Addon
(skill 02 permite FK cross-Feature). `material_id` é referência fraca
porque `addon_estoque` é Addon diferente.
