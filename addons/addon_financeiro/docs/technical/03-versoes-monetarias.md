# Versionamento monetário 1.2.0

Modelo `MonetaryPolicyVersion`, tabela `tesseract_financeiro_policy_version`.
FK RESTRICT para MonetaryPolicy do mesmo addon. A configuração inicial é
logicamente v1; revisões são v2 em diante e não duplicam o registro inicial.
A moeda-base e a organização vêm da política inicial, sem campo mutável de
moeda/organização na revisão. Não há backfill nem mudança de contratos legados.

## Serviço e concorrência

`create_policy_version(data, actor=...)` recebe exatamente organization_code,
expected_version (inteiro positivo, versão anterior lida), decimal_places
(inteiro 0–6), rounding (HALF_UP/HALF_EVEN), valid_from (AAAA-MM-DD) e reason
(1–200 caracteres). Autor (1–120) vem do chamador autenticado. Retorna Result
201/422/409. Ausência de política ou organização inativa é 422.

Latest version é lida para controlar criação concorrente, não para escolher
política de cálculo. Expected diferente é 409; unique(policy_id,version_number)
impede duas revisões com o mesmo número, inclusive após precheck desatualizado.
IntegrityError/erro SQL fazem rollback e devolvem conflito, sem repetir a operação
silenciosamente. Não alterar precisão/arredondamento é 422. Valid_from deve ser
>= data da revisão anterior, quando houver. Primeira revisão tem data explícita;
não inferimos validade histórica da criação da configuração inicial.

Eventos ORM bloqueiam update/delete; SQL direto/bulk não é API suportada e não
há triggers. Modelo usa annotations e endpoints padrão; nenhum menu customizado
ou mudança de CrudGen/Core foi introduzido. Serviço usa commit próprio; ainda
não deve participar de uma movimentação de estoque que exija commit compartilhado.

`resolve_selected_policy(organization_code, policy_version_id=None,
operation_date=None)` retorna exatamente o DTO original quando ID é null/omitido.
Com ID inteiro positivo, valida pertencimento e operação >= valid_from. Snapshot
preserva id/currency_code/organization_code/created_at da política inicial e
sobrescreve decimal_places/rounding; acrescenta version_id, version_number,
valid_from, reason, created_by e version_created_at. O ID original é distinto do
ID de revisão. Nenhuma consulta depende de "versão mais recente" para calcular.
Revisões anteriores seguem selecionáveis após cadastrar novas.

`quantize_amount` ganhou apenas kwargs opcionais policy_version_id e
operation_date. O contrato posicional/DTO original e seus limites permanecem.
JSON de preview/confirm_conversion aceita campo adicional opcional
policy_version_id. Float/bool/string/inexistente/ID de outra organização são
rejeitados; null equivale ao payload antigo. Operação anterior à validade é 422.
Os snapshots antigos permanecem byte a byte no banco; sem versão no DTO eles são
apresentados como v1. Criar revisão não muda reenvio idempotente de conversão
anterior. A seleção de outra revisão na mesma chave é conflito de conteúdo.

## API e telas

GET/POST `/api/financeiro/policy-versions`, login + admin. GET paginado em 20
registros, aceita page e organization_code, retorna items/total/pages. DTO inclui
id de revisão, policy_id original, organização/base, versão, precisão, data,
motivo e autoria. POST não aceita created_by nem currency_code.
GET `/financeiro/policy-versions/` requer policy_versions.list; POST requer admin.
A tela preserva campos e expectativa antiga em erro, sem promover automaticamente
uma revisão rejeitada. Ao selecionar outra organização, a expectativa oculta
acompanha a última versão vista; init em erro mantém o valor enviado.

## Schema

Migration e15a2b76d340, parent d04f1a65c239. Definição independente do ORM vivo,
valida PK/FK/tipos/tamanhos/nullability/CHECK/unique composta em tabelas existentes;
aceita create_all seguido da cadeia Alembic. Downgrade remove só tabela vazia.
Sem upgrade de dependências no projeto; requisitos reproduzidos em ambiente
isolado de testes. A alteração de base continua bloqueada estruturalmente,
aguardando definição dos saldos organizacionais/legado. Nada reprecifica Estoque.
