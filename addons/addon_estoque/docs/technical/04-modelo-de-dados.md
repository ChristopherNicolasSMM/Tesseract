# 04 — Modelo de Dados (Addon Estoque)

```mermaid
erDiagram
    MATERIAL ||--o{ COMPOSICAO : "e_pai_de"
    MATERIAL ||--o{ COMPOSICAO : "e_componente_de"
    MATERIAL ||--o{ MOVIMENTACAO : "possui"
    MATERIAL ||--|| SALDO : "possui"

    MATERIAL {
        int id PK
        string external_id UK "UUID, skill 02 - regra de PK externa"
        string nome
        string categoria "materia_prima | embalagem | kit | outro"
        string unidade_medida
        float peso
        float volume_calculado
        string unidade_medida_volume_calculado
        float volume_real
        string unidade_medida_volume_real
        string formato_fisico
        boolean ativo
        datetime created_at
        datetime updated_at
        boolean is_deleted
        datetime deleted_at
    }
    COMPOSICAO {
        int id PK
        int material_pai_id FK
        int material_componente_id FK
        float quantidade
        datetime created_at
    }
    MOVIMENTACAO {
        int id PK
        int material_id FK
        string tipo_movimentacao "entrada | saida | ajuste"
        float quantidade
        float custo_unitario
        float custo_total
        string lote_fornecedor
        date data_validade
        datetime data_movimentacao
        int usuario_id FK "tesseract_user.id - sempre permitido, skill 02"
        string observacoes
        datetime created_at
    }
    SALDO {
        int id PK
        int material_id FK
        float quantidade_atual
        float custo_medio
        float valor_total_estoque
        float estoque_minimo
        float estoque_maximo
        string status "calculado, hybrid property"
        datetime ultima_atualizacao
    }
```

## Tabelas — nome completo e descrição de negócio

| Tabela real | Descrição |
|---|---|
| `tesseract_estoque_material` | Identidade de qualquer coisa estocável. `categoria` livre por ora. `volume_calculado` = teórico; `volume_real` = medido/declarado — podem divergir, campos e unidades separadas. |
| `tesseract_estoque_composicao` | Auto-relacionamento (BOM). FK real, mesmo Addon (skill 02). |
| `tesseract_estoque_movimentacao` | Ledger imutável — correção é lançamento de ajuste, nunca update/delete. |
| `tesseract_estoque_saldo` | Cache materializado 1:1 com `material`. |

**Soft-delete**: `material` segue padrão CrudGen (`is_deleted`/
`deleted_at`). `movimentacao` **não tem soft-delete** — é ledger
contábil.

## Referenciado (fracamente) por outros Addons

| Addon/Feature consumidor | Coluna | Resolvido por |
|---|---|---|
| `addon_brewstation` / `feature_mash_control` (`RecipeIngredient`, `IngredientMapping`) | `material_id` | `material_lookup` |
| `addon_brewstation` / `feature_ingredientes` (Malte/Lupulo/Levedura) | `material_id` | `material_lookup` |
| `addon_brewstation` / `feature_envase` (`ItemEnvase`) | `material_id` | `material_lookup` |

Ver `addons/addon_brewstation/docs/technical/04-modelo-de-dados.md` e
`addons/addon_brewstation/features/feature_mash_control/docs/technical/04-modelo-de-dados.md`
para o lado espelhado.
