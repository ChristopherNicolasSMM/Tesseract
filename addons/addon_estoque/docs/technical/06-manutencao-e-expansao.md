# 06 — Manutenção e Expansão (Addon Estoque)

## Adicionar campo a uma entidade existente / criar entidade nova

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema), seções
"Como adicionar um campo a um model existente" e "Como criar uma nova
entidade (do zero) via CrudGen" — aplicam-se diretamente aqui. Os
controllers deste Addon (`Material` e os 4 lookups) já seguem o padrão
genérico (campos derivados de `__table__.columns` em runtime), então
adicionar campo não exige regenerar nada — só editar o model e (se a
tabela já tiver dado real) rodar a migration.

## Planejado, não iniciado — expansão cadastral futura

Registrado nesta sessão (decisão do Christopher: documentar agora,
implementar só quando necessário — ver `BACKLOG.md`):

- **Mais campos em `Fabricante`** — hoje é só `nome` (lookup mínimo).
  Quais campos exatamente (CNPJ, contato, site, etc.) ainda não foi
  decidido — não presumir nenhum antes da conversa de arquitetura
  correspondente.
- **Cadastro de Fornecedores** — ainda não modelado. Em aberto: é uma
  entidade nova dentro de `addon_estoque` (mesmo Addon, já que
  fornecedor é conceito de estoque/compras) ou um Addon próprio
  (`addon_compras`, se o sistema de compras abaixo justificar
  isolamento)? Essa decisão deve vir **antes** de qualquer model —
  afeta prefixo de tabela (skill 02) e onde a FK pode existir.
- **Sistema de Compras** — nenhum escopo definido ainda (pedido de
  compra, cotação, recebimento, vínculo com `Movimentacao` tipo
  `entrada`?). Provável candidato a **Addon novo** (`addon_compras`),
  dado o tamanho do domínio — mas isso também é uma decisão em aberto,
  não assumida aqui.

**Regra ao retomar este item**: seguir o mesmo processo já usado para
a ampliação de `Material` desta sessão — decisão primeiro (perguntas
estruturadas, sem gerar código), schema revisado, só then
implementação. Não pular direto pra model.
