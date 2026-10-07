# Contratos e fronteiras — financeiro inicial

Addon `financeiro`, tabelas `tesseract_financeiro_currency` e
`tesseract_financeiro_monetary_policy`; templates, serviços e controller manuais.
Models têm annotations e o registro segue AddonBase/ModuleManager. Nenhum
artefato existente gerado pelo CrudGen foi editado ou regenerado.

## API administrativa

- GET/POST `/api/financeiro/currencies`: `code`, `name`, `decimal_places`.
- GET/POST `/api/financeiro/policies`: `organization_code`, `currency_code`, `rounding`.
- JSON inválido: 422; unicidade/conflito/erro de banco: 409, com rollback.
- Só `admin`; escritas PUT/PATCH/DELETE não existem.

Referência fraca por código imutável ao Core, resolvida pelo serviço público;
sem FK entre addons. A política exige organização ativa e moeda cadastrada.
Unicidade de organização no banco impede dois cadastros iniciais, inclusive
inserções concorrentes. Nenhuma operação movimenta estoque. Inativação da
organização bloqueia resolução operacional, preservando política existente.
Não há ainda contexto financeiro por usuário, segregação ou isolamento tenant.

## Serviço público

`resolve_policy(organization_code)` devolve cópia da configuração.
`quantize_amount(amount, organization_code)` aceita texto decimal com ponto
ou Decimal, retorna `amount` em texto e snapshot `policy` (id, código da
organização, código de moeda, casas, arredondamento, criação). Float/bool,
NaN/infinito e notação exponencial em texto são rejeitados. Limites explícitos:
18 dígitos inteiros, 12 fracionários, saída conforme escala 0–6 e contexto
Decimal de precisão 40. Magnitude >= 10^18, inclusive após arredondar, é erro.
Valores negativos são suportados para futuros créditos; não constitui
permissão para quantidade ou custo de estoque negativos.

Isto é quantização de montante, não conversão cambial nem precisão do preço
unitário de insumos. O catálogo não verifica registro ISO em serviço externo,
aceita o código informado pelo administrador e não fornece lista automática.
Nunca deduzir moeda de símbolo, país, User.empresa ou material legado.

O serviço não expõe alteração/exclusão da configuração. Eventos ORM bloqueiam
update/delete de Currency/MonetaryPolicy. Escritas SQL diretas/bulk externas
não são uma API suportada e não têm esse guard; não foram criados triggers.
Não há auditoria de autoria nem versões monetárias completas nesta etapa.

## Utilitário de documentos

`addons.addon_financeiro.root.services.document_validator.DocumentValidator`
exporta a classe compartilhada de `core.document_validation`; Core não importa
Financeiro. Métodos `cnpj`, `cpf`, `cep`, `email`, `phone` devolvem valor
normalizado ou lançam ValueError. Máscaras aceitas são estritas; caracteres
arbitrários não são simplesmente removidos. CNPJ numérico/alfanumérico segue
DV módulo 11 com valor ASCII menos 48. E-mail verifica formato básico; telefone
8–15 dígitos, com `+` opcional; não confirma conta/linha. CEP só verifica formato.
Validadores legados do Core permanecem compatíveis; nova classe não muda
silenciosamente os contratos de todos os cadastros antigos.

## Organizações ampliadas

Perfil opcional em `tesseract_organization`: endereço principal brasileiro,
dados legais e de contato. CNPJ canônico único (14 caracteres), NULL opcional.
Código/ID preexistentes preservados. `tesseract_organization_contact` referencia
Core Organization com RESTRICT; sem exclusão física nas rotas. PUT de perfil
omisso preserva valores; string vazia/NULL limpa campo opcional. Estado ativo
é booleano estrito. Dados são validados antes de atribuir ao ORM/commit.

GET/PUT `/api/admin/organizations/<id>` incorpora perfil e contatos ao DTO.
POST `/api/admin/organizations/<id>/contacts` cria responsável; PUT
`/api/admin/organizations/<id>/contacts/<contact_id>` edita/inativa. ID de
responsável de outra organização é 404. Autorização admin também nas telas.
Dados pessoais só devem ser expostos por chamadores autorizados; não há
consulta pública de documentos ou cadastro de responsáveis.

## Migration e compatibilidade

Revision `b82d9e43a017`, parent `a71c8d32f906`. Exige `python run.py db upgrade`.
Novas colunas nullable, sem backfill, moeda, vínculos ou default Brasil.
Tabelas novas são criadas também quando o addon estiver ausente no checkout
que executa a migration; nenhuma leitura financeira será ativada sem o addon.
A revisão anterior passa a aceitar colunas adicionais sem deixar de validar
o contrato original; necessário para create_all atual seguido da cadeia antiga.
A nova revisão valida colunas, tipos, tamanhos, nullable, PK, unique, FK e
CHECK dos alvos já criados antes de alterar. Schema divergente interrompe com
erro, sem adaptação implícita. Upgrade online SQLite conferido; geração SQL
offline e execução PostgreSQL/Windows não foram certificadas.

Downgrade só remove estruturas sem dados financeiros/responsáveis/perfil.
Mesmo sem operações financeiras, moedas cadastradas bloqueiam downgrade,
para não destruir configuração. Organização existente com perfil NULL é
preservada ao voltar a revisão anterior. Não executar downgrade como estorno.

## Fontes do contrato externo

- [Receita — manual do DV CNPJ](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).
- [ViaCEP — formato, erros e limites de uso](https://viacep.com.br/).
