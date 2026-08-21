# 04 — Modelo de Dados (Feature Yeast Bank)

> ER completo — as 8 entidades originais do BrewStation foram
> migradas na Fase 5/5b. A 9ª entidade, `Container`, entrou na Fase 14
> (skill 19 — `docs/skills/19-proposta-reestruturacao-yeast-bank-container.md`)
> como nível intermediário entre Dispositivo e Item do Banco.
>
> **Correção de nome de tabela nesta revisão**: as entidades abaixo
> chamadas `Container`/`Dispositivo`/`Leitura` usam os nomes de tabela
> curtos reais do código (`container`/`storage_device`/`reading`) — a
> versão anterior deste diagrama usava `device` (nunca existiu como
> nome curto real; foi renomeado para `storage_device` na Fase 6 para
> não colidir com `DeviceMetadata` de `feature_device_manager`, skill
> 02, mas o diagrama nunca tinha sido corrigido).

```mermaid
erDiagram
    tesseract_brewstation_yeastbank_strain ||--o{ tesseract_brewstation_yeastbank_bank_item : "tem"
    tesseract_brewstation_yeastbank_storage_device ||--o{ tesseract_brewstation_yeastbank_reading : "registra"
    tesseract_brewstation_yeastbank_storage_device ||--o{ tesseract_brewstation_yeastbank_container : "contém"
    tesseract_brewstation_yeastbank_container ||--o{ tesseract_brewstation_yeastbank_bank_item : "armazena"
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
    tesseract_brewstation_yeastbank_storage_device {
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
    tesseract_brewstation_yeastbank_container {
        int id PK
        string name
        string container_type
        int device_id FK
        bool is_deleted
    }
    tesseract_brewstation_yeastbank_bank_item {
        int id PK
        int strain_id FK
        int container_id FK
        string storage_type
        string storage_slot
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
| `..._container` | `container_type` | Caixa/Estante/Prateleira/Outro (`@enum_field`) — unidade física dentro do dispositivo, nunca virtual (skill 19) |
| `..._container` | `device_id` | Obrigatório (`NOT NULL`) — todo Container pertence a exatamente 1 Dispositivo |
| `..._bank_item` | `container_id` | Obrigatório desde a skill 19 — substituiu `storage_device_id` (removido); o dispositivo do item é sempre resolvido via `item.container.device`, nunca por FK direta |
| `..._bank_item` | `storage_slot` | Desde a skill 19, significa posição **dentro do Container** (ex.: "gaveta 2"), não mais posição solta no dispositivo inteiro |
| `..._bank_item` | `estimated_viability_pct` | Viabilidade **estimada do item físico** — diferente dos parâmetros de modelo da cepa; é o valor calculado ao longo do tempo |
| `..._bank_item` | `label_text` | Renomeado de `label` (BrewStation original) para não colidir com o decorator `@label` das anotações |
| `..._starter_log` | `action_on_bank_item` | Ação sugerida/confirmada sobre o item de origem (ex.: descartar, manter) — texto livre, sem enum ainda |
| `..._cell_count_history` | FKs (`strain_id`/`bank_item_id`/`starter_id`) | Todas **opcionais** de propósito — um registro pode ser um cálculo livre, não necessariamente vinculado |
| `..._bank_event` | `metadata_json` | Texto livre (JSON serializado manualmente) — sem JSONB nativo nesta fase |
| `..._bank_config` | (toda a tabela) | Pensada como singleton (1 linha), mas modelada como tabela normal — CrudGen não tem conceito de singleton ainda |

## Regra de soft-delete

Todas as 9 tabelas seguem `is_deleted`/`deleted_at` (skill 02).

## FK entre módulos

Todas as FKs desta Feature são **dentro da própria Feature** — nenhuma
aponta para fora do `yeast_bank`, nenhuma para outro Addon (skill 02
proíbe FK entre Addons diferentes). Confirmado funcionando mesmo com o
mecanismo de renomeação de tabela (prefixo aplicado depois da
declaração do model) — ver `BACKLOG.md`, Fase 5b, para o teste que
validou isso antes de migrar tudo.
