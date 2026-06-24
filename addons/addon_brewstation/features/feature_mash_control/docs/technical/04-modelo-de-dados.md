# 04 — Modelo de Dados (Feature Mash Control)

> 12 entidades, escopo CRUD (sem motor de controle em tempo real —
> ver `BACKLOG.md`, Fase 6).

```mermaid
erDiagram
    tesseract_brewstation_mashctrl_plant ||--o{ tesseract_brewstation_mashctrl_plant_vessel : "tem"
    tesseract_brewstation_mashctrl_plant_vessel ||--o{ tesseract_brewstation_mashctrl_plant_mapping : "mapeia"
    tesseract_brewstation_mashctrl_recipe ||--o{ tesseract_brewstation_mashctrl_session : "usada em"
    tesseract_brewstation_mashctrl_plant ||--o{ tesseract_brewstation_mashctrl_session : "usada em"
    tesseract_brewstation_mashctrl_session ||--o{ tesseract_brewstation_mashctrl_session_step : "tem"
    tesseract_brewstation_mashctrl_session ||--o{ tesseract_brewstation_mashctrl_session_log : "gera"
    tesseract_brewstation_mashctrl_session ||--o{ tesseract_brewstation_mashctrl_session_alarm : "gera"
    tesseract_brewstation_mashctrl_layout ||--o{ tesseract_brewstation_mashctrl_widget : "tem"
    tesseract_brewstation_mashctrl_rule ||--o{ tesseract_brewstation_mashctrl_rule_log : "histórico"

    tesseract_brewstation_mashctrl_recipe {
        int id PK
        string name
        text recipe_data "JSON"
    }
    tesseract_brewstation_mashctrl_plant {
        int id PK
        string name
        float capacity_liters
    }
    tesseract_brewstation_mashctrl_session {
        int id PK
        string name
        string status
        int recipe_id FK
        int plant_id FK
    }
    tesseract_brewstation_mashctrl_session_step {
        int id PK
        int session_id FK
        float pid_kp "parâmetro, não loop ativo"
    }
    tesseract_brewstation_mashctrl_rule {
        int id PK
        int sensor_function_id FK "cross-Feature -> device_manager"
        int actor_function_id FK "cross-Feature -> device_manager"
        string condition_operator
    }
```

## Colunas não óbvias

| Tabela | Coluna | Descrição |
|---|---|---|
| `..._session_step` | `pid_kp`/`pid_ki`/`pid_kd` | Só **parâmetros configurados** — o loop de controle PID que de fato os usaria em tempo real não foi portado (decisão registrada) |
| `..._rule` | `sensor_function_id`/`actor_function_id` | FK **cross-Feature** para `DeviceFunction` (`feature_device_manager`) — permitido por serem do mesmo Addon |
| `..._recipe` | `recipe_data` | JSON serializado como texto — sem schema fixo |
| (todas) | `is_deleted`/`deleted_at` | Soft-delete padrão (skill 02) |

## FK entre módulos

`BrewPlantMapping.device_function_id`, `DashboardWidget.device_function_id`,
`AutomationRule.sensor_function_id`/`actor_function_id` — todas FK
cross-Feature para `feature_device_manager`, dentro do mesmo Addon
(`addon_brewstation`). Skill 02 permite explicitamente esse caso desde
a Fase 6.
