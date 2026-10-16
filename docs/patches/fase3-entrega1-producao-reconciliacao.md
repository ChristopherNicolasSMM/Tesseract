# Financeiro — entrega 1 de 3: produção e reconciliação organizacional

Base: `4035407`. Reúne as etapas 1 e 2 aprovadas em 16/10/2026.
Entrega 2: contas/caixa, categorias e centros de custo, pagar/receber e liquidações
(etapas 3–6). Entrega 3: fluxo de caixa, conciliação e relatórios (7–8).
Refatorações amplas serão avaliadas depois dessas três entregas.

## Aplicação

```powershell
git am --keep-cr .\tesseract-financeiro-entrega1-producao-reconciliacao.patch
python run.py db upgrade
python -m pytest tests/test_production_organization.py tests/test_organization_stock.py tests/test_organization_transfers.py tests/test_organization_recipe_preview.py tests/test_purchase_pricing.py -q
```

Reinicie o servidor. Migration `c59f7a23d861`, parent `e59f6ab8d704` (blocos de relatórios já presentes na base), cria
somente vínculo e snapshot de consumo do lote. Sem backfill. Upgrade verifica
tabelas preexistentes; downgrade bloqueado se houver histórico produtivo.

## Operação

1. Financeiro: organizações ativas com moedas e políticas já cadastradas.
2. Estoque → Reconciliar estoque legado (`/estoque/saldos/reconciliar-legado`).
   Selecione material, organização, quantidade na unidade-base, moeda e valor
   **total** da avaliação, data, taxa direcionada quando estrangeira, referência
   e justificativa. IDs de taxa/versão são os apresentados nas telas financeiras.
   Vazio em versão seleciona a configuração inicial, nunca a última automaticamente.
3. Clique **Conferir prévia**. Confira saldo original e montante convertido.
   **Confirmar reconciliação** retira do legado e entra na organização na mesma
   transação. Alteração do saldo/ledger ou dos dados exige nova prévia.
   Repita por organização/material se a distribuição for parcial.
4. Na sessão de brassagem, abra **Organização e confirmação do lote** no workspace,
   ou `/brewstation/brew-sessions/<id>`. Vincule organização, data do consumo e
   versão monetária. O vínculo é imutável e idempotente; receitas/lotes continuam
   compartilhados até essa escolha explícita. Lotes com consumo/envase histórico
   não podem receber atribuição retroativa.
5. Confirme ingredientes. Linhas do mesmo material são agregadas; todos os
   materiais e o snapshot são confirmados juntos. Não completa falta com outra
   organização ou saldo legado. Repetição não duplica baixas.
6. Informe volume real do lote antes do primeiro envase. Produto acabado usa
   unidade-base UN/ITEM e volume por unidade. Envase exige unidades inteiras e
   não pode ultrapassar o volume do lote. O primeiro envase congela a base de
   volume, inclusive após estorno. Para corrigir base, não editar histórico.
7. Envase baixa embalagens e dá entrada no produto acabado na mesma organização.
   O custo é ingredientes rateados pelo volume real + embalagens efetivamente
   consumidas. O último envase absorve o resíduo do arredondamento. Novos envases
   não recalculam custos anteriores. A chave UUID identifica repetição de POST.

## Fronteiras e histórico

A API pública `registrar_movimentacao` exige organização em novas escritas.
Movimentação manual, chamadas em massa e recebimento de pedido antigo sem vínculo
são recusados; preparar compras com organização/cadastro monetário/avaliação.
O contrato privado `_registrar_movimentacao_legada` serve exclusivamente à
reconciliação e ao estorno rastreável dos envases históricos. Não é API de
novas integrações. Saldos/movimentos antigos permanecem consultáveis.

A reconciliação não presume moeda nem reutiliza automaticamente o custo Float
antigo. O operador avalia o montante explicitamente e informa sua origem na
justificativa. Snapshot guarda saldo, última movimentação, valores informados,
conversão, política, autor e ID de saída legada. Quantidades que o legado Float
não consegue representar/retirar exatamente são rejeitadas, sem arredondamento
silencioso. Os históricos antigos não são reescritos.

Estorno organizacional retira o produto e devolve embalagens pelos movimentos
originais, sem devolver ingredientes do lote. Se o produto já foi consumido ou
seu custo médio mudou de modo incompatível, recusa com rollback e exige
reconciliação explícita; não inventa uma diferença financeira. Envases antigos
mantêm o estorno histórico já existente. Nenhum estorno cria títulos financeiros.

Serviços entre addons usam DTOs e a API de Estoque; tabelas produtivas referenciam
somente a sessão do próprio BrewStation. Políticas/códigos organizacionais são
referências fracas. Vínculo e consumo têm guardas ORM de imutabilidade; SQL direto
não é uma operação suportada. Reserva escrita do lote/material serializa
operações; não há certificação de PostgreSQL/Windows nesta entrega.

O custo autoritativo produtivo e de estoque é Decimal em texto/snapshot. Campos
Float antigos do lote e da precificação continuam como compatibilidade de
apresentação; a precificação organizacional calcula em Decimal e conserva os
montantes exatos em `base_calculo_snapshot.exact_amounts`. Quantidades da receita,
BOM e volumes ainda vêm dos cadastros Float existentes; não recupera precisão
já perdida. Esta entrega não altera unidades nem fatores históricos.

## API e permissões

- POST `/brewstation/brew-sessions/<id>/organizacao`: organization_code,
  operation_date e policy_version_id (inteiro/null); requer brew_sessions.update
  e movimentacaos.create. Confirmação também exige movimentacaos.create.
- GET/POST `/estoque/saldos/reconciliar-legado`: saldos.list e movimentacaos.create.
  JSON com os campos do formulário; action=preview retorna `preview.preview_token`;
  action=confirm exige esse preview_token. Sucesso de criação 201, repetição 200,
  erro 422. Nenhum autor é aceito no payload: vem da sessão autenticada.
- Estoque → Estoque por organização, Transferir entre organizações e Reconciliar
  estoque legado usam o registro de menus existente do addon. Histórico legado
  tem nome explícito. Nenhum controller/service/template gerado foi regenerado.

## Validação

Resultados da execução constam na entrega. Testes novos cobrem vínculo e rejeição
de reatribuição, saldo isolado, agregação, idempotência, falha no segundo material,
prévia pura/desatualizada, falha de entrada da reconciliação, entrada do produto,
rateio congelado, excesso de volume, embalagens insuficientes, estorno, preços,
permissões e migração. Os testes organizacionais existentes que montam saldos
históricos passaram a usar explicitamente o contrato privado de preparação legada.

### Resultado conferido

123 casos distintos passaram: 19 da entrega, 38 de estoque organizacional,
25 de transferências, 9 de prévia de receita e 32 de cadastro monetário de
compras. Os casos novos foram executados em conjunto e por grupos durante as
correções, incluindo concorrência real com duas conexões SQLite. Renderização
HTML de formulários/histórico e sintaxe JavaScript da tela real conferidas.
Sem inspeção visual de temas em navegador nem certificação de Windows/PostgreSQL.

Cadeia Alembic completa aplicada com código 0 em esquema inicializado por
create_all; uma única head `c59f7a23d861`. Banco completamente vazio sem o
bootstrap Core ainda encontra a limitação preexistente de migrations antigas
(`NoSuchTableError: tesseract_user`); isso não é uma nova instalação automatizada.
Upgrade repetido das tabelas novas e downgrade com histórico foram verificados.

Patch conferido por git am --keep-cr em checkout isolado de `4035407`, com
comparação da árvore final e verificação reversa. Nenhuma publicação remota.
