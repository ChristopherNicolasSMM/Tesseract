# 04 — Modelo de Dados (Addon BrewStation)

> O núcleo do Addon (`root/`) não tem tabela própria ainda. O ER
> completo de cada Feature vive em `features/*/docs/technical/04-modelo-de-dados.md`.

Resumo de tabelas por Feature:

| Feature | Tabelas | Prefixo |
|---|---|---|
| `feature_yeast_bank` | 8 | `tesseract_brewstation_yeastbank_*` |
| `feature_device_manager` | 4 | `tesseract_brewstation_dvm_*` |
| `feature_mash_control` | 12 | `tesseract_brewstation_mashctrl_*` |

Total: 24 tabelas de domínio no Addon.
