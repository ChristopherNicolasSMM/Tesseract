# Contrato de tesouraria 1.3.0

Modelos no próprio Financeiro: FinancialAccount, FinancialCategory,
FinancialCostCenter, FinancialTitle, FinancialInstallment, FinancialSettlement,
FinancialReversal, FinancialCancellation e FinancialMovement. Tabelas
`tesseract_financeiro_treasury_*`. Nenhuma FK entre addons. Money é String(64)
com bind/result Decimal, evitando a passagem NUMERIC → REAL do SQLite.

`treasury_service` é a API de domínio. Escritas retornam Result (201/200, 422
para validação, 409 para conflito de banco) e possuem uma unidade transacional.
Não chamar serviços de escrita dentro de outra transação que precise controlar
commit. As prévias executam somente SELECT, sem flush, commit ou bloqueio de
linhas. Não garantem disponibilidade futura.

## Cadastros

`create_catalog(kind,data,actor=...)`, kinds accounts/categories/cost-centers.
Todos exigem organization_code e name. Categoria: direction PAYABLE/RECEIVABLE.
Conta: kind BANK/CASH, opening_balance, opening_date e policy_version_id
(inteiro/null); bank_name, branch, account_number opcionais. Conta opera na
base resolvida da organização. A abertura é um movimento, não saldo editável.

`edit_catalog(kind,id,data,actor=...)`: expected_version (int), name e is_active
(bool); dados bancários opcionais para contas. Versão é comparada após reserva
de escrita. Não altera organização/moeda/direção/abertura. Nomes únicos dentro
da organização. Sem hard delete. Títulos e baixas guardam nomes e classificação
em snapshots; renomear o cadastro não reclassifica histórico.

## Títulos

`create_title` e `preview_title`: organization_code, kind PAYABLE/RECEIVABLE,
reference, counterparty, currency_code, amount, issue_date, first_due,
installment_count (1–120), category_id, cost_center_id, rate_id,
policy_version_id e idempotency_key. purchase_order_id é opcional.
Autor não é campo de payload. Valores como texto decimal, nunca float/bool,
sem expoente, NaN/infinito ou vírgula; limites monetários existentes <10^18.
Montantes manuais precisam caber exatamente na escala da moeda original.
Categoria e centro precisam estar ativos e pertencer à organização; categoria
precisa corresponder ao tipo. Empréstimos sem classificação não são inferidos.

A soma das parcelas originais é o total original; a soma das avaliações na base
é o total convertido. Parcela final absorve o resíduo. Datas mensais são ancoradas
no dia do primeiro vencimento. DTO de detalhe inclui parcelas, saldo original
pendente, saldo-base pendente, estado e baixas/estornos. Cancelamento é um evento
separado, permitido somente sem baixas ativas. Título cancelado permanece com
montantes históricos e status CANCELLED; consumidores devem excluir esse estado
das projeções, em vez de presumir que cancelamento seja recebimento/pagamento.

Unique(organization_code,idempotency_key) e unique(source_reference) protegem
duplicação, inclusive na origem de compra. Reenvio idêntico devolve o histórico,
inclusive após baixa/cancelamento, sem reativação. Conflitos de conteúdo não são
repetidos silenciosamente. Reserva de categoria/centro permite releitura do
vencedor em criações equivalentes concorrentes.

## Compra opcional

`treasury_purchase_contract` consulta somente o DTO público de Estoque
`consultar_obrigacao_pedido(order_id,reserve=False)`. A criação pede reserva do
pedido; prévia e tela fazem somente leitura. Estoque valida estado, contexto e
preços congelados e devolve total exato, moeda, fornecedor e snapshot de itens e
frete. Financeiro não importa ORM de Compras nem cria movimentos de estoque.
O total original da obrigação é arredondado uma vez na escala original pela
política selecionada; só então é convertido. Total exato, total monetário e
conversão ficam preservados. Fonte ausente/inativa ou incompatível é recusada.

## Baixa e estorno

`settle(installment_id,data,actor=...)` / `preview_settlement`: account_id,
principal, interest, fine, discount, operation_date, rate_id, policy_version_id,
idempotency_key, notes (texto/null). Principal positivo, demais não negativos,
na escala original congelada, desconto <= principal. Conta ativa, mesma
organização e moeda-base. Conta não admite cheque especial. Reservas: título
primeiro, conta depois; bloqueios também cobrem baixas de títulos diferentes
na mesma conta. Saldo aberto vem de eventos ativos, sem somar texto via SQL.

Snapshot guarda as conversões de principal, juros, multa, desconto e caixa,
classificação congelada, conta, custo-base liberado da obrigação, diferença
cambial e resíduo de arredondamento. O último principal da parcela libera seu
resíduo-base exato. Diferença cambial = principal convertido na baixa − valor-base
liberado; positivo significa perda no pagar e ganho no receber. Não altera custo
histórico de mercadoria. Não é um razão contábil de partidas dobradas.

`reverse(settlement_id,{reason,operation_date,idempotency_key},actor=...)` cria
um evento único e movimento inverso exato. Sem nova taxa/quantização. Não pode
anteceder a baixa. Saldo insuficiente para devolver recebimento desfaz o estorno.
Repetições idênticas são idempotentes. Referência nova não estorna a mesma baixa
duas vezes. `cancel_title(title_id,{reason},actor=...)` preserva o título.

Ledger e eventos têm guardas ORM de update/delete. SQL direto/bulk não é uma API
suportada; não há triggers. Cache de saldo segue a ordem dos IDs do ledger;
operações retrodatadas não reescrevem balance_after de movimentos anteriores.
Categorias/centros inativados não impedem liquidar títulos históricos válidos.

## HTTP

HTML: /financeiro/contas/, /categorias/, /centros-custo/, /titulos/,
/titulos/<id>, /liquidacoes/, /lancamentos/. Endpoints `<plural>.list` e
annotations entregam menus/ícones/permissões pela descoberta padrão, sem override
de AddonFinanceiro.get_transactions/register_routes/register_models.

API administrativa em `/api/financeiro/treasury`:

- GET/POST /catalogs/{accounts|categories|cost-centers}; PATCH /catalogs/<kind>/<id>.
- GET/POST /titles; POST /titles/preview; GET /titles/<id>; POST /titles/<id>/cancel.
- POST /installments/<id>/preview e /installments/<id>/settle.
- GET /settlements; POST /settlements/<id>/reverse.
- GET /movements (filtro account_id opcional).

Listas aceitam organization_code e page, páginas de 20 itens. Títulos aceitam
kind. Consultas HTML exigem `<plural>.list`; APIs/escritas exigem admin. Não existe
segregação tenant por usuário: autorização e visibilidade seguem o Financeiro
anterior. Payloads estritos e erros de formulário preservam os valores enviados.

## Migração

Revision d60a8c34e972, parent c59f7a23d861. Definições independentes do ORM vivo,
validação de todo schema preexistente antes de qualquer DDL. Sem backfill, saldo
inicial, título automático ou atribuição histórica. Upgrade suporta create_all
seguido da cadeia Alembic. Downgrade só quando todas as nove tabelas estão vazias.
Sem nova dependência. Ver roteiro da entrega para validações e aplicação.
