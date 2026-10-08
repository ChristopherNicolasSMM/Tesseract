# Fase 3 — contexto organizacional de compras e correção UTF-8

Base: patch de versões monetárias `73a8dd1`. Este pacote inclui a correção
reportada no teste `test_real_template_js_preserves_conflict_expectation`:
`subprocess.run` decodifica explicitamente a saída UTF-8 do Node. O texto
`6 cenários` permanece no teste; a codificação padrão do Windows não participa
da leitura. A correção não modifica o JavaScript de produção.

## Decisão e alcance

Catálogo de materiais compartilhado, com compras, saldos e custos separados
por organização. A separação de saldos/custos ainda é a próxima etapa.
O saldo atual permanece global, 1:1 com Material; este pacote cria somente
um vínculo organizacional explícito, auditável e imutável para documentos.
Não muda quantidades, custos, moeda ou propriedade de históricos existentes.

Vincular um pedido exige rascunho e ausência de vínculo com itens de cotação
já convertidos. Vincular um processo exige estado aberto/comparado e nenhum
convite de cotação existente, inclusive arquivado. Portanto, cadastre a
organização antes de convidar fornecedores ou enviar um pedido. Cotações
novas pertencem ao contexto de seu processo; não podem mudar de processo
quando o processo de origem ou destino estiver vinculado.

**Nesta etapa, pedidos vinculados não podem ser recebidos no saldo global e
processos vinculados não podem gerar pedidos.** A tela apresenta esse limite
antes do vínculo definitivo. Documentos sem contexto continuam no fluxo
legado, sem organização ou BRL presumidos. Use os novos vínculos para preparar
novos documentos, não para migrar operações em andamento.

O vínculo guarda código e nome da organização no momento do registro, autor
e data; alterações no cadastro Core não reescrevem esse snapshot. Usa o
resolver público do Core, sem consultas às tabelas de outro módulo. Não
consulta tabelas do Financeiro nem presume uma política ou versão monetária.
Repetir o mesmo vínculo retorna o registro existente; outra organização gera
409. Novos vínculos exigem organização ativa. O histórico de uma organização
inativada continua consultável. Exclusão definitiva do vínculo/documento é
bloqueada; arquivamento do documento continua disponível.

## Aplicação

Aplicar após os patches de câmbio e versões monetárias. Com a aplicação
parada e na raiz do repositório, usando o ambiente virtual habitual:

```powershell
git status --short
git am --keep-cr .\tesseract-fase3-compras-contexto-organizacional-utf8.patch
python run.py db upgrade
python -m pytest tests/test_purchase_organization_context.py tests/test_financeiro_policy_versions.py -q
```

A migration `f26b3c87e451`, filha de `e15a2b76d340`, cria
`tesseract_estoque_purchase_context`. Não preenche vínculos legados. Valida
schema existente para instalações que executaram `create_all` antes de
Alembic, com FKs locais, unicidade por documento e CHECK de exatamente um
pai. Downgrade com vínculos existentes é recusado para preservar histórico.
Não é necessário regenerar CRUD, alterar transações ou gerar permissões:
as telas usam as permissões de atualização já existentes de cada documento.

## Acesso e validação funcional

Com sessão autenticada e permissão de atualização, acessar:

- Pedido: `/estoque/pedido-compras/<id>/contexto-organizacional`.
- Processo: `/estoque/processo-cotacaos/<id>/contexto-organizacional`.

GET abre o formulário. POST de formulário registra o vínculo e redireciona.
As mesmas URLs aceitam POST JSON `{"organization_code":"A"}` e GET com
`Content-Type: application/json` para consultar. O formulário inclui token CSRF se esse recurso estiver configurado na
aplicação; autenticação e permissões seguem o padrão das rotas existentes. Não existem novos
menus globais. As rotas são extensões dos blueprints existentes, com guarda
para múltiplas instâncias de aplicação no mesmo processo. Nenhum service,
controller ou template gerado foi editado.

1. Criar pedido em rascunho, acessar a URL e selecionar a organização.
2. Reabrir: conferir autor/data/nome e ausência de formulário de troca.
3. Repetir com a mesma organização: obter 200, sem duplicação; outra: 409.
4. Confirmar o pedido e tentar receber: recusa sem movimento ou saldo novo.
5. Criar processo sem cotações, vincular, cadastrar fornecedores e tentar
   gerar pedidos: recusa, sem pedidos gerados.
6. Conferir que pedidos/processos legados continuam sem contexto e seguem
   os fluxos anteriores.

## Próxima etapa

Criar ledger/saldos organizacionais, com Decimal e política monetária explícita;
propagar o contexto de RFQ para pedidos de forma atômica; registrar moeda,
conversão e snapshots antes de habilitar recebimento organizacional. Nenhum
saldo global será atribuído automaticamente a uma empresa. A migração desses
saldos dependerá de decisão explícita e reconciliação com o ledger existente.


## Verificação automatizada da entrega

Python 3.12.14, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51,
Alembic 1.18.4 e Node. Com `LegacyAPIWarning` tratado como erro:

- Contexto organizacional + versões monetárias: **31 passaram**.
- Recebimento, geração e concorrência selecionados nas suítes de Estoque e
  integridade de compras: **17 passaram**, 173 fora dessa seleção.
- Idempotência e compatibilidade de migrations: **10 passaram**, incluindo
  criação via ORM antes do upgrade, upgrade real completo e downgrade vazio.

Os testes incluem dois vínculos concorrentes em conexões independentes,
conflito/repetição, rollback de falha induzida, histórico imutável, HTML/JSON,
negação sem sessão, bloqueio de recebimento/geração organizacional e
preservação dos fluxos legados. Execução no Linux/SQLite; não é certificação
visual do navegador nem execução nativa no Windows/PostgreSQL.


## Atualização posterior

O bloqueio preparatório descrito acima é o estado deste pacote na sua entrega.
A continuação [estoque e recebimento organizacionais](fase3-estoque-organizacional-recebimento.md)
habilita geração com propagação atômica e recebimento mediante avaliação
monetária explícita, sem atribuir os saldos legados. Consulte esse roteiro para
o comportamento da aplicação após instalar a continuação.
