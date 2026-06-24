# 04 — Modelo de Dados (Feature Yeast Bank)

> ER completo — as 8 entidades originais do BrewStation foram
> migradas na Fase 5/5b.

```mermaid
erDiagram
    tesseract_brewstation_yeastbank_strain ||--o{ tesseract_brewstation_yeastbank_bank_item : "tem"
    tesseract_brewstation_yeastbank_device ||--o{ tesseract_brewstation_yeastbank_reading : "registra"
    tesseract_brewstation_yeastbank_device ||--o{ tesseract_brewstation_yeastbank_bank_item : "armazena (opcional)"
    tesseract_brewstation_yeastbank_bank_item ||--o{ tesseract_brewstation_yeastbank_starter_log : "origina"
    tesseract_brewstation_yeastbank_strain ||--o{ tesseract_brewstation_yeastbank_cell_count_history : "referencia (opcional)"
    tesseract_brewstation_yeastbank_bank_item ||--o{ tesseract_brewstation_yeastbank_cell_count_history : "referencia (opcional)"
    tesseract_brewstation_yeastbank_starter_log ||--o{ tesseract_brewstation_yeastbank_cell_count_history : "referencia (opcional)"
    tesseract_brewstation_yeastbank_bank_item ||--o{ tesseract_brewstation_yeastbank_bank_event : "gera (opcional)"
    tesseract_brewstation_yeastbank_strain ||--o{ tesseract_brewstation_yeastbank_bank_event : "gera (opcional)"
    tesseract_brewstation_yeastbank_starter_log ||--o{ tesseract_brewstation_yeastbank_bank_event : "gera (opcional)"

    tesseract_brewstation_yeastbank_strain {
        int id PK
        string name
        string family
        string viability_model
        float daily_viability_loss_pct
        bool is_deleted
    }
    tesseract_brewstation_yeastbank_device {
        int id PK
        string name
        string device_type
        float current_temperature_c
        bool is_deleted
    }
    tesseract_brewstation_yeastbank_reading {
        int id PK
        int device_id FK
        datetime recorded_at
        float temperature_c
    }
    tesseract_brewstation_yeastbank_bank_item {
        int id PK
        int strain_id FK
        int storage_device_id FK
        string storage_type
        string status
        float estimated_viability_pct
        bool is_deleted
    }
    tesseract_brewstation_yeastbank_starter_log {
        int id PK
        int bank_item_id FK
        string status
        bool contamination_detected
    }
    tesseract_brewstation_yeastbank_cell_count_history {
        int id PK
        int strain_id FK
        int bank_item_id FK
        int starter_id FK
        float cells_per_ml
        float viability_percent
    }
    tesseract_brewstation_yeastbank_bank_event {
        int id PK
        int bank_item_id FK
        int strain_id FK
        int starter_id FK
        string event_type
    }
    tesseract_brewstation_yeastbank_bank_config {
        int id PK
        int expiry_master_days
        int expiry_work_days
    }
```

## Colunas não óbvias

| Tabela | Coluna | Descrição de negócio |
|---|---|---|
| `..._strain` | `status` | Estado **estratégico** da cepa (ex.: `active`, `discontinued`) — não confundir com `is_deleted` |
| `..._strain` | `viability_model` | Algoritmo de decaimento (hoje só `linear_decay_default`; cálculo real ainda não portado) |
| `..._bank_item` | `estimated_viability_pct` | Viabilidade **estimada do item físico** — diferente dos parâmetros de modelo da cepa; é o valor calculado ao longo do tempo |
| `..._bank_item` | `label_text` | Renomeado de `label` (BrewStation original) para não colidir com o decorator `@label` das anotações |
| `..._starter_log` | `action_on_bank_item` | Ação sugerida/confirmada sobre o item de origem (ex.: descartar, manter) — texto livre, sem enum ainda |
| `..._cell_count_history` | FKs (`strain_id`/`bank_item_id`/`starter_id`) | Todas **opcionais** de propósito — um registro pode ser um cálculo livre, não necessariamente vinculado |
| `..._bank_event` | `metadata_json` | Texto livre (JSON serializado manualmente) — sem JSONB nativo nesta fase |
| `..._bank_config` | (toda a tabela) | Pensada como singleton (1 linha), mas modelada como tabela normal — CrudGen não tem conceito de singleton ainda |

## Regra de soft-delete

Todas as 8 tabelas seguem `is_deleted`/`deleted_at` (skill 02).

## FK entre módulos

Todas as FKs desta Feature são **dentro da própria Feature** — nenhuma
aponta para fora do `yeast_bank`, nenhuma para outro Addon (skill 02
proíbe FK entre Addons diferentes). Confirmado funcionando mesmo com o
mecanismo de renomeação de tabela (prefixo aplicado depois da
declaração do model) — ver `BACKLOG.md`, Fase 5b, para o teste que
validou isso antes de migrar tudo.
