# 05 — Casos de Uso (Feature Ingredientes)

## UC01 — Cadastrar Malte/Lúpulo/Levedura
- **Ator**: usuário com `malte.create`/`lupulo.create`/`levedura.create`
- **Fluxo**: busca ou cadastra o `Material` correspondente em
  `addon_estoque` → preenche specs próprias → salva
- **Fluxo alternativo**: `Material` já vinculado a outro registro do
  mesmo tipo → sistema alerta (1 Material : 1 spec, por tipo)

## UC02 — Definir Preço Padrão de um tipo de insumo
- **Ator**: usuário com `preco_padrao_insumos.update`
- **Pré-condição**: nenhuma — as 3 linhas (`malte`/`lupulo`/`levedura`)
  já existem por seed no boot
- **Fluxo principal**: acessa Preço Padrão de Insumo → edita o valor e
  a unidade de um tipo → salva
- **Efeito**: passa a valer na próxima Simulação/Cálculo de
  Precificação (`feature_envase`) que precisar de preço para um
  Material desse tipo sem `Saldo` real ainda
- **Permissão RBAC**: `preco_padrao_insumos.update`
