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

## UC05 — Recalcular viabilidade (ainda não implementado)

- **Ator**: Usuário com `yeast_strains.recalculate_viability`
- **Status**: permissão já sincronizada (Camada 2, `@permission` no
  model), **lógica de cálculo ainda não portada** — fica para a Fase
  5b, quando `YeastBankItem` (onde a viabilidade *estimada* realmente
  vive) for migrado.
