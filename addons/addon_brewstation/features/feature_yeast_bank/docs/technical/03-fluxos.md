# 03 — Fluxos (Feature Yeast Bank)

## Caminho feliz: recalcular viabilidade

```mermaid
flowchart TD
    A[POST /brewstation/yeast-bank-tools/recalculate-viability] --> B[Para cada YeastBankItem]
    B --> C{Status descartado/contaminado?}
    C -->|Sim| D[Pula — marca skipped]
    C -->|Não| E[Busca melhor referência]
    E --> F{Achou referência?}
    F -->|Não| G[Marca no_reference]
    F -->|Sim| H[Aplica modelo linear ou exponencial]
    H --> I[Grava estimated_viability_pct + metadados de referência]
    I --> J[commit]
```

## Prioridade de referência (dentro de "Busca melhor referência")

```mermaid
flowchart LR
    A[Histórico real] -->|não achou| B[Histórico estimado]
    B -->|não achou| C[Starter]
    C -->|não achou| D[Valor inicial da cepa]
    D -->|não achou| E[Sem referência]
```

Todas as consultas excluem registros com `contamination_detected=True`.
