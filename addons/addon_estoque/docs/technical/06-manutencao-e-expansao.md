# 06 — Manutenção e Expansão (Addon Estoque)

## Adicionar campo a uma entidade existente / criar entidade nova

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema), seções
"Como adicionar um campo a um model existente" e "Como criar uma nova
entidade (do zero) via CrudGen" — aplicam-se diretamente aqui. Os
controllers deste Addon (`Material` e os 4 lookups) já seguem o padrão
genérico (campos derivados de `__table__.columns` em runtime), então
adicionar campo não exige regenerar nada — só editar o model e (se a
tabela já tiver dado real) rodar a migration.

## Expansão cadastral — desenho fechado, ver skill 23

O item que estava registrado aqui como "planejado, não iniciado"
(mais campos em `Fabricante`, Fornecedores, Sistema de Compras) foi
decidido em sessão de arquitetura própria — ver
`docs/skills/23-proposta-expansao-addon-estoque.md` para o desenho
completo (taxonomia `TipoProduto`×`Categoria`, fracionamento via
`MaterialUnidade`, `Fornecedor`/`Transportadora`/`Endereco`, sistema
de compras via `PedidoCompra`/`ItemPedidoCompra`). Decisão raiz:
**tudo dentro do próprio `addon_estoque`**, sem Addon novo.

Execução em 4 fases (skill 23, seção 7) — este documento é atualizado
a cada fase entregue, não de uma vez só.
