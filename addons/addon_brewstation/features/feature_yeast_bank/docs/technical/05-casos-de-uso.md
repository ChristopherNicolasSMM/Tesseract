# 05 — Casos de Uso (Feature Yeast Bank)

## UC01 — Cadastrar cepa

- **Ator**: Usuário com `yeast_strains.create`
- **Pré-condição**: autenticado
- **Fluxo principal**: `POST /api/brewstation/yeast-strains/` com `name` (obrigatório)
- **Fluxo alternativo**: `name` vazio → erro de validação (`@required`)
- **Permissão**: `yeast_strains.create`

## UC02 — Listar/consultar cepas

- **Ator**: Usuário com `yeast_strains.list`/`yeast_strains.detail`
- **Fluxo principal**: `GET /api/brewstation/yeast-strains/` (lista,
  exclui deletadas) ou `GET /.../{id}` (detalhe)
- **Permissão**: `yeast_strains.list` / `yeast_strains.detail`

## UC03 — Editar cepa

- **Ator**: Usuário com `yeast_strains.update`
- **Pré-condição**: cepa existe, não está na lixeira
- **Fluxo principal**: `PUT /api/brewstation/yeast-strains/{id}`
- **Fluxo alternativo**: cepa na lixeira → `400` ("não é possível editar")
- **Permissão**: `yeast_strains.update`

## UC04 — Lixeira (trash/restore/delete_permanent)

- **Ator**: Usuário com a permissão correspondente
- **Fluxo principal**: `trash` → `restore` → (opcional) `delete_permanent`
- **Fluxo alternativo**: `delete_permanent` numa cepa que não está na
  lixeira → `400`
- **Permissão**: `yeast_strains.trash` / `.restore` / `.delete_permanent`

## UC05 — Recalcular viabilidade (implementado)

- **Ator**: usuário com `yeast_bank_items.recalculate_viability`
- **Fluxo principal**: `/brewstation/yeast-bank-tools/recalculate-viability`
  → botão "Recalcular agora" → recalcula TODOS os itens do banco em
  lote (não é uma ação por cepa — usa os parâmetros de cada cepa
  relacionada)
- **Lógica**: ver `services/viability_engine.py` — prioridade de
  referência (histórico real > estimado > starter > valor inicial da
  cepa), modelo linear ou exponencial conforme `YeastStrain.viability_model`
- **Status**: itens com status `discarded`/`contaminated`/etc. são
  ignorados; itens sem nenhuma referência disponível ficam marcados
  como `no_reference` no resultado
- **Permissão**: `yeast_bank_items.recalculate_viability` (corrigido
  da Fase 5 — estava por engano em `yeast_strains`, a ação opera
  sobre `YeastBankItem`, não sobre a cepa)
