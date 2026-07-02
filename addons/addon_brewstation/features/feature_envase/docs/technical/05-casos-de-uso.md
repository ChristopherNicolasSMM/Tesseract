# 05 — Casos de Uso (Feature Envase)

## UC01 — Registrar Envase de um Lote
- **Ator**: usuário com `envase.create`
- **Pré-condição**: Lote (`BrewSession`) existente
- **Fluxo principal**: acessa Envase → Novo → escolhe Lote, informa
  quantidade em litros e os Materiais de embalagem usados (com
  quantidade cada) → salva → sistema dá baixa automática no estoque
  desses Materiais
- **Fluxo alternativo**: Material de embalagem sem saldo suficiente →
  mesmo comportamento de alerta de `addon_estoque` (UC-02 lá)
- **Permissão RBAC**: `envase.create`
