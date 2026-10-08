# Fase 3 — estoque organizacional e recebimento monetário

Base: `d554903`, patch de contexto organizacional validado pelo usuário.
A decisão continua: materiais compartilhados; compras, saldos e custos por
organização. Este pacote habilita a geração de pedidos vinculados e o
recebimento organizacional que estavam bloqueados na etapa preparatória.

## Entrega

- Ledger imutável e saldo por `(organization_code, material_id)`, separados
  dos registros globais existentes. Um material pode ter estoque em várias
  organizações, inclusive com moedas-base diferentes.
- Decimal em quantidades, valores e cálculo. Persistência textual exata em
  SQLite e PostgreSQL: a afinidade NUMERIC do SQLite converteria valores em
  REAL e perderia precisão. Valores são serializados como texto decimal nas
  APIs; não há nova biblioteca nem requisito de instalação nativa.
- Movimentação central com organização explícita, entrada/saída/ajuste e
  idempotência. Saídas e ajustes negativos exigem saldo da própria organização
  e usam seu custo. Saldo global/outras organizações não cobrem uma saída.
- Avaliação monetária definitiva do pedido confirmado: moeda original, data,
  taxa direcional e versão de política explícita quando selecionada. A
  política inicial continua sendo a opção de compatibilidade; nenhuma versão
  mais recente é escolhida automaticamente.
- Recebimento total com ledger, saldos e status em uma transação. Quantidade,
  preço/fator persistidos, moeda, taxa, política, valor convertido, lote e
  validade ficam registrados no histórico. Nenhuma taxa posterior reprecifica
  uma entrada.
- RFQ gera pedidos/itens/vínculos/referências em uma única transação, inclusive
  no fluxo legado. Processos vinculados propagam a organização de origem.
  Falha de item ou fornecedor desfaz todos os pedidos daquela geração.
- Telas e endpoints HTML/JSON para consultar saldos/histórico e congelar a
  avaliação. As rotas estendem os blueprints existentes com as permissões já
  usadas pelo Estoque; nenhum arquivo gerado pelo CrudGen foi editado.

Os serviços do Estoque consomem contratos públicos do Financeiro e Core.
Não consultam tabelas financeiras ou de organizações diretamente e não criam
FK entre addons. Importar Estoque não importa modelos do Financeiro. Com
Financeiro desativado, consultas históricas e movimentos globais continuam
funcionando; operações monetárias organizacionais exigem ativação explícita.

## Aplicação

Com a aplicação parada, checkout limpo e ambiente virtual habitual ativo,
na raiz do projeto, após o patch de contexto organizacional:

```powershell
git status --short
git am --keep-cr .\tesseract-fase3-estoque-organizacional-recebimento.patch
python run.py db upgrade
python -m pytest tests/test_organization_stock.py tests/test_purchase_organization_context.py tests/test_purchase_integrity.py tests/test_addon_estoque.py tests/test_financeiro_foundation.py tests/test_financeiro_exchange.py tests/test_financeiro_policy_versions.py tests/test_financeiro_ui_integrity.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py -q
```

Reiniciar a aplicação. A migration `a37c4d98f562`, filha de `f26b3c87e451`,
cria `tesseract_estoque_organization_balance`,
`tesseract_estoque_organization_movement` e
`tesseract_estoque_order_valuation`. Valida schemas existentes antes de
qualquer DDL, incluindo instalações que executaram `create_all` antes de
Alembic. Não preenche ou modifica saldo, movimento ou documento legado.
Downgrade com dados em qualquer uma dessas tabelas é recusado antes de
apagar qualquer tabela.

## URLs para validar

| Página | URL | Permissão |
| --- | --- | --- |
| Saldo/histórico da organização | `/estoque/saldos/por-organizacao?organization_code=A` | `saldos.list` |
| Registrar movimento organizacional | POST `/estoque/saldos/por-organizacao/movimentar` | `movimentacaos.create` |
| Vínculo do pedido | `/estoque/pedido-compras/<id>/contexto-organizacional` | `pedido_compras.update` |
| Avaliação do pedido | `/estoque/pedido-compras/<id>/avaliacao-monetaria` | `pedido_compras.update` |
| Vínculo do processo | `/estoque/processo-cotacaos/<id>/contexto-organizacional` | `processo_cotacaos.update` |

Não há menu financeiro duplicado nem transação inserida manualmente. As
extensões usam o registro já sobrescrito pelo AddonEstoque, mantendo seu
padrão existente e guardas contra registro duplicado entre `create_app`s.
A página de vínculo do pedido liga para a avaliação, que liga para o saldo e
para a Entrada de Mercadoria existente. Autenticação e permissões são
reutilizadas; os formulários incluem token CSRF se a aplicação o disponibiliza.

### Recebimento pela tela

1. Configurar uma organização e sua política monetária no Financeiro.
2. Criar pedido em rascunho, vincular organização e cadastrar itens.
3. Confirmar o pedido pelo fluxo existente; seus itens ficam congelados.
4. Na avaliação monetária, escolher a moeda em que os preços originais estão
   expressos, data e taxa. Na moeda-base, selecionar “Sem taxa”. Em outra
   moeda, a taxa precisa pertencer à organização, ao par e à data exatos.
5. Pré-visualizar os valores. O formulário mantém a seleção para confirmar.
   Congelar a avaliação definitiva. Repetir os mesmos parâmetros é
   idempotente; parâmetros diferentes são recusados.
6. Voltar ao pedido e usar Entrada de Mercadoria, com lote/validade opcionais.
   A tela existente usa a avaliação congelada e atualiza somente o saldo da
   organização. Um pedido não pode ser recebido duas vezes.
7. Consultar o estoque por organização e verificar quantidade, moeda-base,
   valor e histórico. Conferir que o saldo global não mudou.

Avaliação e recebimento são dois passos intencionais. A avaliação persistida
não registra estoque. Se o recebimento falhar, ela permanece para nova
tentativa; nenhum movimento, saldo ou status parcial é confirmado.

### Geração a partir de cotação

Vincular o processo antes de convidar fornecedores, conforme o contrato
validado anteriormente. Cadastrar cotações, marcar vencedores e usar Gerar
Pedido. Todos os pedidos herdam a organização do processo, continuam em
rascunho e não movimentam estoque. Após revisão/confirmação, cada pedido
segue a avaliação monetária e o recebimento acima. Chamadas programáticas
organizacionais devem informar `actor`; rotas autenticadas usam o usuário da
sessão. Nenhum autor ou organização é inferido de um documento anterior.

### API de movimento manual

POST JSON na rota de movimentação, com permissão de criação:

```json
{
  "organization_code": "A",
  "material_id": 1,
  "tipo_movimentacao": "entrada",
  "quantidade": "2",
  "custo_unitario": "1.005",
  "source_currency": "BRL",
  "operation_date": "2026-10-09",
  "rate_id": null,
  "policy_version_id": null,
  "idempotency_key": "entrada-manual-001",
  "observacoes": "Entrada conferida"
}
```

Quantidades/custos devem ser texto decimal com ponto, até 18 dígitos inteiros
(magnitude inferior a 10^18) e 12 fracionários. Float/bool/NaN/infinito são
recusados. Entrada e ajuste positivo exigem custo explícito, inclusive zero.
Saída usa quantidade positiva; ajuste negativo usa quantidade negativa.
Em ambos, custo/moeda original/taxa devem ser null ou omitidos no JSON.
`receipt:` é prefixo reservado para chaves de recebimento. O mesmo pedido
não pode criar recebimentos manuais por esta API.

Repetir a mesma chave e os mesmos dados retorna 200 com o movimento e o
saldo originais daquela operação, mesmo que o saldo atual já tenha mudado.
Nova operação retorna 201; dados inválidos/conflitos retornam 422, sem
alteração. As chaves são únicas por organização. GET com
`Content-Type: application/json` na consulta retorna saldo/histórico, paginados
em 50 registros, com `page` e `has_next`.

API em processo: `registrar_movimentacao` conserva a assinatura legada e
adiciona parâmetros opcionais de organização/moeda/taxa/data/versão/autor e
idempotência. `consultar_saldo(material_id, organization_code='A')` consulta
somente o saldo organizacional; omissão mantém a consulta global.

## Precisão e limites mantidos

A conversão é aplicada ao total original de cada item, calculado por
quantidade de compra × preço, e arredondada pela política selecionada. A
quantidade física vem da quantidade × fator aplicado congelado no pedido,
nunca do fator atual do cadastro. O valor de estoque é a soma dos valores
convertidos; saídas reduzem o valor proporcionalmente, com arredondamento da
política escolhida, e a última saída drena o resíduo completo. Nunca produz
quantidade/valor negativo. O custo médio exibido usa 12 casas e HALF_EVEN;
essa precisão de apresentação não reescreve o valor contabilizado nem o
snapshot monetário.

Os cabeçalhos/itens antigos de compras/cotações ainda armazenam preços e
quantidades em Float. A avaliação usa um adaptador explícito dos valores
persistidos, via `Decimal(str(valor))`, e recusa dados inválidos ou fora da
precisão suportada. Não recupera precisão já perdida na gravação antiga.
A moeda escolhida na avaliação é explícita; não presumir que todo preço
legado seja BRL. O frete continua fora do custo de estoque, sem rateio nesta
etapa, e é indicado como excluído no snapshot/tela. Recebimento permanece
total; parcelamento e estorno de compra não foram incluídos.

Integrações que omitem organização, incluindo os consumidores existentes do
BrewStation, continuam no ledger global. Nenhuma carga inicial ou saldo
global é distribuído automaticamente. A migração de saldos legados exige
reconciliação explícita, com origem e aprovação do usuário. Este pacote não
cria contas a pagar/receber, pagamentos, impostos, notas fiscais ou PDV.

## Próximas entregas

1. Moeda/precisão Decimal desde o cadastro de cotação e pedido, preservando
   documentos históricos e as avaliações já congeladas.
2. Seleção organizacional nos consumidores do BrewStation e reconciliação
   explícita de saldos legados, conforme o domínio de cada fluxo.
3. Obrigações financeiras, parcelas, liquidação e diferença cambial de
   pagamento, com contrato próprio para esse novo módulo.

## Verificação desta entrega

Ambiente: Python 3.12.14, Flask 3.1.3, Flask-SQLAlchemy 3.1.1,
SQLAlchemy 2.0.51, Alembic 1.18.4 e pytest 9.1.1. `pip check` sem conflitos.
`LegacyAPIWarning` tratado como erro nas execuções abaixo:

- **218 casos de regressão passaram**: Estoque, integridade de compras,
  contexto organizacional, idempotência e compatibilidade de migrations.
- **147 casos financeiros passaram**: fundação, câmbio, versões monetárias e
  integridade das telas, incluindo o JavaScript real com decodificação UTF-8.
- **38 casos novos passaram**, em execuções incrementais: precisão textual
  longa no SQLite; organizações com moedas-base diferentes; idempotência;
  reconciliação de quantidade/valor; taxa e política congeladas; rollback de
  vários itens e de commit; geração atômica; manutenção de histórico após
  cancelamento; concorrência em conexões independentes; permissões; HTML/JSON;
  parâmetros e valores de formulários preservados; importação sem ativar
  Financeiro; proteção contra recebimento parcial por chamada direta.
- Após os ajustes finais, **12 casos existentes de manutenção** e **6 casos
  de interface/integração** foram reexecutados e passaram. Eles já pertencem
  às contagens anteriores; não são somados novamente.

Total de **403 casos distintos** nas suítes selecionadas. Os testes de
migration incluem upgrade real do zero/de schema ORM atual e downgrade até a
base sem dados organizacionais, além da recusa de downgrade com dados.
Aplicação do `git format-patch` via `git am --keep-cr` conferida em checkout
isolado da base, com árvore resultante idêntica e verificação reversa.
Execução Linux/SQLite; aparência nos temas, execução nativa Windows e banco
PostgreSQL dependem da validação local. Não é execução de toda a suíte do
repositório nem auditoria dos consumidores que continuam no fluxo legado.
