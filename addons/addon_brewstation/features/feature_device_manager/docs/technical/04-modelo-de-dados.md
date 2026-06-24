# 04 — Modelo de Dados (Feature Device Manager)

```mermaid
erDiagram
    tesseract_brewstation_dvm_device ||--o{ tesseract_brewstation_dvm_actor : "tem portas"
    tesseract_brewstation_dvm_function ||--o{ tesseract_brewstation_dvm_actor : "define função de"
    tesseract_brewstation_dvm_device ||--o{ tesseract_brewstation_dvm_emulated_device : "pode ser emulado"

    tesseract_brewstation_dvm_function {
        int id PK
        string name
        string category
        string data_type
    }
    tesseract_brewstation_dvm_device {
        int id PK
        string external_id "UUID, exposto externamente"
        string name
        string device_type
        string protocol
        float current_temperature_c
    }
    tesseract_brewstation_dvm_actor {
        int id PK
        string external_id "UUID"
        int device_id FK
        int function_id FK
        string port_name
        string actor_type
    }
    tesseract_brewstation_dvm_emulated_device {
        int id PK
        int device_id FK
        bool is_running
        string emulation_mode
        json functions_config
    }
```

## Colunas não óbvias

| Tabela | Coluna | Descrição |
|---|---|---|
| `..._device`/`..._actor` | `external_id` | UUID gerado automaticamente — usado em integrações externas (MQTT, etc.), nunca como PK (skill 02, "Regra de PK externa") |
| `..._actor` | `plugin_name`/`plugin_entity_id` | Referência fraca a entidade de outro módulo — nunca FK direta entre Addons (skill 02) |
| `..._emulated_device` | `functions_config` | JSON — corrigido em relação ao original (que usava `default={}` mutável compartilhado entre instâncias) |

## FK entre módulos

Todas internas a esta Feature. `feature_mash_control` referencia
`DeviceFunction` (FK cross-Feature, mesmo Addon — permitido).
