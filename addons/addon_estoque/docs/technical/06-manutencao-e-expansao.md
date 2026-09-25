# 06 — Manutenção e Expansão (Addon Estoque)

## Adicionar campo a uma entidade existente / criar entidade nova

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema), seções
"Como adicionar um campo a um model existente" e "Como criar uma nova
entidade (do zero) via CrudGen" — aplicam-se diretamente aqui. Os
controllers deste Addon já seguem o padrão genérico (campos derivados
de `__table__.columns` em runtime), então adicionar campo não exige
regenerar nada — só editar o model e (se a tabela já tiver dado real)
rodar a migration.

## Onde vive cada tipo de lógica neste Addon

| Precisa de... | Vai em... |
|---|---|
| CRUD simples de uma entidade nova (lookup, cadastro) | `*_service.py` gerado pelo CrudGen — sem lógica própria |
| Regra que atravessa mais de uma entidade (ex.: gerar Movimentacao a partir de um Pedido) | `estoque_service.py` (não-CrudGen, ver skill 05 §2.3 para o mesmo padrão em `device_manager`) |
| Ação que não é CRUD, chamada de um botão específico (ex.: "Enviar Pedido", "Receber") | Hook do controller da entidade (`*_hooks.py`) chamando `estoque_service.py` — nunca lógica de negócio direto no hook |
| Leitura por outro Addon | `*_lookup.py` — só `material_lookup.py` é exposto para fora hoje |

## Expansão cadastral e de compras — histórico (skills 23, 24, 25)

Três rodadas de arquitetura ampliaram este Addon a partir do desenho
original (só Material/Composição/Movimentação/Saldo):

- **Skill 23** — taxonomia completa (`Fabricante`/`Origem`/
  `TipoProduto`/`Categoria`, com `Categoria` classificando dentro de um
  `TipoProduto`), `MaterialUnidade` (fracionamento com fator de
  conversão), `Fornecedor`/`Transportadora`/`Endereco` (com vínculos
  próprios), e o sistema de compras (`PedidoCompra`/
  `ItemPedidoCompra`) com a ação "receber" gerando `Movimentacao`
  automaticamente.
- **Skill 24** — sistema de cotação (RFQ): `ProcessoCotacao`/`Cotacao`/
  `ItemProcessoCotacao`/`ItemCotacao`, com a correção arquitetural
  pós-Fase 6.3 de mover o "item pedido" para `ItemProcessoCotacao`
  (definido uma vez) em vez de repeti-lo em cada `Cotacao`.
- **Skill 25** — ações em massa na lista de Materiais (Movimentar
  Estoque, Criar Cotação, Criar Pedido, Modificação em Massa).

Decisão raiz que atravessa as três: tudo dentro do próprio
`addon_estoque`, nunca um Addon `addon_compras` separado — FK real
entre `Fornecedor`/`PedidoCompra`/`Movimentacao` só é permitida
(skill 02) porque estão no mesmo Addon.

## Extensões previsíveis a partir daqui

- **Recebimento parcial de `PedidoCompra`** — hoje é sempre total
  (`receber_pedido_compra()` gera Movimentação para 100% dos itens de
  uma vez). Se isso virar necessidade real, o ponto de entrada é essa
  função — decidir se `ItemPedidoCompra` ganha uma coluna
  `quantidade_recebida` (parcial acumulado) ou se o pedido passa a
  poder ter mais de um "recebimento" vinculado.
- **Fluxo de aprovação formal** — hoje não existe (ver `03-fluxos.md`).
  Se necessário, começa por decidir se é um papel/permissão nova
  (`pedido_compras.aprovar`) ou uma coluna de estado adicional entre
  `enviado` e `confirmado`.
- **Bloqueio de saída sem saldo suficiente** — hoje `Movimentacao` do
  tipo `saida` não valida contra `Saldo.quantidade_atual` antes de
  aceitar. Se virar regra de negócio real, o ponto é
  `estoque_service.registrar_movimentacao()`.
- **Evento no EventBus** para mudança de saldo/recebimento de pedido —
  nenhum publicado hoje (ver `03-fluxos.md`, seção final).
- **Conversões de unidade mais complexas** — hoje `MaterialUnidade`
  guarda o código selecionado do catálogo via `@weak_ref`; o conteúdo
  da embalagem é representado pelo fator específico do Material.
  Conversões que dependam de condições além desse fator exigiriam
  modelagem própria e revisão dos serviços de compra e movimentação.
