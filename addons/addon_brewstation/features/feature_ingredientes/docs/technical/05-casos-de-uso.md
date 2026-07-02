# 05 — Casos de Uso (Feature Ingredientes)

## UC01 — Cadastrar Malte/Lúpulo/Levedura
- **Ator**: usuário com `malte.create`/`lupulo.create`/`levedura.create`
- **Fluxo**: busca ou cadastra o `Material` correspondente em
  `addon_estoque` → preenche specs próprias → salva
- **Fluxo alternativo**: `Material` já vinculado a outro registro do
  mesmo tipo → sistema alerta (1 Material : 1 spec, por tipo)
