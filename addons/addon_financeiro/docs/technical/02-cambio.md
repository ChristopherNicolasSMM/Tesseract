# Contrato público de câmbio 1.1.0

Serviço `root/services/exchange_service.py`:

- `create_rate(data, actor=...)`: Result 201/422/409. Campos exatos:
  organization_code, source_currency, target_currency, rate, valid_on, source,
  rate_type. Destino obrigatório = base da política inicial da organização ativa.
  Tipo MANUAL/CONTRACTUAL; origem e destino diferentes e previamente cadastrados.
- `preview_conversion(data)`: DTO ou ValueError; sem commit. Campos exatos:
  organization_code, source_currency, amount, operation_date, rate_id. `rate_id`
  é inteiro positivo para moeda estrangeira, null para moeda-base.
- `confirm_conversion(data, actor=...)`: mesmos campos + reference e
  idempotency_key. Result 201 na criação, 200 no reenvio idêntico, 409 em conflito,
  422 em dado inválido. Unique(organization_code,idempotency_key) protege
  duplicação concorrente; IntegrityError faz rollback e verifica o vencedor.

JSON deve enviar montantes/taxas como texto decimal. Serviço Python aceita
Decimal também, rejeitando float/bool, NaN/infinito, vírgula, expoente textual,
mais de 18 dígitos inteiros ou 12 fracionários. Taxa > 0. SQL armazena taxa em
texto canônico para não passar por float do SQLite. Contexto de produto 64
algarismos; até 24 casas no produto, um só arredondamento pela política da base.
Magnitude de produto e saída < 10^18. Zero negativo é normalizado. Nenhuma
inversão, triangulação, taxa de outro dia ou paridade é inferida.

Snapshot JSON inclui organização, moeda/valor original, moeda/valor convertido,
produto, data, cópia completa de taxa e política. Rounding HALF_UP/HALF_EVEN é
herdado da política inicial. Taxas iguais podem coexistir: o ID escolhido é a
referência explícita. Alterar taxa ou política por SQL externo não é operação
suportada. Eventos ORM rejeitam update/delete; não há triggers de banco.

API (login + admin):

- GET/POST `/api/financeiro/rates`
- POST `/api/financeiro/conversions/preview`
- GET/POST `/api/financeiro/conversions`

GET aceita organization_code e page (20 por página), retorna items/total/pages.
Autor vem de current_user.username; payload não aceita created_by. GET de telas
usa exchange_rates.list/monetary_conversions.list. Não há segregação tenant:
permissões administrativas/de lista dão acesso ao histórico de organizações.
Serviços são internos confiáveis; chamadores respondem por autorização.

Migration d04f1a65c239, parent c93e0f54b128 (Reports já no repositório), cria
somente exchange_rate e conversion. Sem backfill ou mudança na política inicial.
Aceita create_all antes de upgrade, valida schema antes de DDL e bloqueia
downgrade com qualquer histórico. A migration usa definições próprias para não
importar ORM vivo; reaproveita validador da fundação e valida unique composta.
Integração com compras/recebimento exigirá unidade transacional compartilhada:
confirm_conversion nesta etapa faz commit próprio e não deve ser chamada no
meio de um lançamento de estoque. Nenhum consumidor de Estoque foi ligado ainda.

Políticas versionadas, contexto organizacional de compras/estoque e integração
cotação/pedido/recebimento continuam próximos pacotes. Não trocar silenciosamente
a política inicial pela última versão ou reinterpretar saldos globais legados.

## Continuidade 1.2.0

Preview/confirm aceitam policy_version_id opcional, sem mudança do payload/DTO
legado. A política selecionada segue o contrato de
[versionamento explícito](03-versoes-monetarias.md). A versão inicial continua
sendo usada quando o campo for omitido ou null; não escolher a última implicitamente.
