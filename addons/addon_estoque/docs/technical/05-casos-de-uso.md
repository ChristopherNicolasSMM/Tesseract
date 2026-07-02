# 05 — Casos de Uso (Addon Estoque)

## Ator: Usuário (operador de estoque)

### UC-01 — Cadastrar Material
- **Pré-condição**: permissão `materiais.create`
- **Fluxo principal**: acessa Materiais → Novo → preenche nome,
  categoria, unidade de medida, campos físicos opcionais (peso,
  volume_calculado, volume_real, formato_fisico) → salva
- **Fluxo alternativo**: categoria "kit"/"composto" → direcionado a
  montar a Composição (materiais componentes + quantidade)
- **Permissão RBAC**: `materiais.create`

### UC-02 — Registrar Movimentação de Estoque
- **Pré-condição**: Material já cadastrado; permissão
  `movimentacoes.create`
- **Fluxo principal**: acessa Movimentações → Nova → escolhe Material,
  tipo (entrada/saída/ajuste), quantidade, custo (se entrada) → salva
  → sistema atualiza Saldo automaticamente
- **Fluxo alternativo**: quantidade de saída maior que saldo atual →
  sistema alerta, mas não bloqueia (**decisão ainda em aberto**)
- **Permissão RBAC**: `movimentacoes.create`

### UC-03 — Consultar Saldo e Forçar Recálculo
- **Pré-condição**: permissão `saldo.view`
- **Fluxo principal**: acessa Saldo → filtra por Material/categoria →
  visualiza quantidade_atual, custo_medio, valor_total
- **Fluxo alternativo**: clica "Recalcular" → reprocessa a partir do
  ledger (mecanismo ainda não desenhado)
- **Permissão RBAC**: `saldo.view`, `saldo.recalculate`

## Ator: Addon externo (via service público)

### UC-04 — Consultar/Buscar Material (leitura programática)
- **Pré-condição**: Addon consumidor declara `"requires": ["estoque"]`
  no próprio manifesto
- **Fluxo principal**: chama `material_lookup.get_material(material_id)`
  ou `material_lookup.buscar_material_por_termo(texto)` → recebe dado
  primitivo (nunca o objeto ORM)
- **Sem tela própria** — interação código-a-código
