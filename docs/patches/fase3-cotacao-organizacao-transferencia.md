# Fase 3 — organização na cotação e transferência entre organizações

Arquivo: `tesseract-fase3-cotacao-organizacao-transferencia.patch`.
Base: patch `tesseract-fase3-compras-moeda-decimal.patch` (`beb1703`). O usuário
informou que esse patch ainda estava em validação local ao solicitar este
ajuste. A nova entrega depende de sua aplicação e não o substitui.

## Aplicação

Na raiz do Tesseract, com o patch monetário anterior aplicado:

```powershell
git am --keep-cr .\tesseract-fase3-cotacao-organizacao-transferencia.patch
python -m pytest tests/test_quotation_organization_area.py tests/test_organization_transfers.py tests/test_purchase_organization_context.py tests/test_organization_stock.py tests/test_purchase_pricing.py tests/test_purchase_integrity.py tests/test_addon_estoque.py tests/test_financeiro_policy_versions.py::test_real_template_js_preserves_conflict_expectation -q
```

Reinicie a aplicação. **Sem nova migration**: os movimentos pareados usam
o ledger organizacional já existente. O upgrade `b48d5e09a673` do patch
anterior deve estar concluído; se ainda não foi executado, rode
`python run.py db upgrade` para aquela entrega.

Aplicação conferida com `git am --keep-cr` em checkout da base, árvore final
idêntica e verificação reversa sem erros. Os testes usam SQLite/Flask e Node
com DOM mínimo; não constituem teste visual em navegador ou certificação
de Windows/PostgreSQL nativos.

## Organização dentro da cotação

Abra `/estoque/processo-cotacaos/<id>` usando o ID real do processo.
**Organização compradora** aparece no cabeçalho e no modal **Responder Preços**.
Selecione uma organização cadastrada e ativa e confirme o vínculo. Na interface,
convidar um novo fornecedor exige essa confirmação. Não se presume um código
`A`, a primeira organização da lista ou a empresa do usuário.

O vínculo é do processo e vale para todos os fornecedores/cotações desse
processo. Os pedidos gerados herdam automaticamente o código/nome congelados
da organização, como no serviço já existente. Cotações de fornecedores do
mesmo processo não recebem organizações divergentes. Depois de confirmar,
a área exibe a organização em leitura; não permite trocar o vínculo.

Novo comportamento explícito: um processo ainda aberto/comparado pode receber
vínculo mesmo com convites existentes, desde que **todas as cotações estejam em
rascunho**, sem cotações/itens arquivados, sem vencedores selecionados e sem
pedidos gerados. Assim é possível preencher a organização dentro de uma cotação
em andamento. Cotações enviadas/respondidas/recusadas e históricos permanecem
protegidos; crie outro processo para novo vínculo nesses casos. Nenhum saldo,
moeda ou preço é reatribuído automaticamente ao fazer esse vínculo explícito.

A lista de fornecedores ganhou o acesso **Moeda e valores**, para o cadastro
monetário já entregue. A área é montada pelo JavaScript existente e um fragmento
manual; nenhum controller/service/template gerado pelo CrudGen foi alterado.
Erros preservam a seleção no formulário. As APIs legadas continuam disponíveis
para documentos sem organização; não há backfill nem exigência retroativa.

GET `/estoque/processo-cotacaos/<id>/organizacao-cotacao` retorna JSON com
`data` do vínculo (ou null), `html` e `modal_html` escapados pelo template.
POST recebe somente `{"organization_code":"CODIGO_REAL"}` e usa o mesmo
serviço de vínculo das demais telas. GET exige `processo_cotacaos.detail`;
POST também exige `processo_cotacaos.update`. Repetição com o mesmo vínculo
é idempotente; tentar outra organização retorna conflito.

## Transferência no estoque

Abra `/estoque/saldos/por-organizacao` e clique em **Transferir entre
organizações**, ou vá diretamente para `/estoque/saldos/transferir`.

1. Selecione origem e destino diferentes e ativas; clique em **Carregar moedas
   e políticas**.
2. Selecione o material compartilhado e informe quantidade positiva na sua
   unidade-base, data, políticas monetárias e referência única da transferência.
3. Para moedas-base diferentes, selecione uma taxa explícita da organização
   **destino**, no par moeda-base da origem → moeda-base do destino, na mesma
   data. Não há inversão, última taxa automática ou paridade presumida.
4. Confirme. A saída e a entrada são gravadas em uma única transação, com
   atualização dos dois saldos. Se algum lado falhar, nenhum é confirmado.

A saída usa o custo médio contábil do saldo da origem e a política selecionada
da origem. Transferência de todo o saldo leva o resíduo exato e zera a origem.
Saldo insuficiente não utiliza estoque global legado nem estoque de outra
organização para completar a quantidade.

Na mesma moeda-base, o destino recebe **exatamente o valor removido da origem**,
sem quantização adicional, mesmo se as precisões das políticas forem distintas.
Isso conserva valor e quantidade; não se divide valor por quantidade para
reconstruir custo unitário, evitando nova perda decimal. A política do destino
fica registrada e rege saídas futuras. Não informe taxa nesse caso.

Em moedas diferentes, a saída mantém seu valor na moeda da origem e a entrada
recebe o valor convertido/arredondado pelo contrato público do Financeiro e
política do destino. A entrada congela taxa, data, política e valores original/
convertido. Não se somam valores de moedas distintas como um total comum.

Ambos os movimentos possuem a mesma `transfer_reference`, organizações origem/
destino, papel (`out`/`in`), autor, data operacional e observações. A entrada
também referencia o ID da saída. O histórico da tela indica **Transferência
origem → destino** e a referência de correlação. Os registros são imutáveis.

## Contrato de serviço/JSON

API pública: `estoque_service.transferir_entre_organizacoes(data, actor=...)`.
POST JSON em `/estoque/saldos/transferir` recebe todos estes campos:

```json
{
  "source_organization": "ORIGEM_REAL",
  "destination_organization": "DESTINO_REAL",
  "material_id": 123,
  "quantity": "1.5",
  "operation_date": "2026-10-09",
  "source_policy_version_id": null,
  "destination_policy_version_id": null,
  "rate_id": null,
  "idempotency_key": "TRANSFERENCIA-0001",
  "notes": null
}
```

IDs inteiros positivos; `quantity` como texto decimal/Decimal, nunca float/bool.
Versão null escolhe a política inicial, preservando o contrato anterior;
não promove para a última versão automaticamente. Referência de até 80 caracteres,
observações até 1000, data ISO. Aplicam-se os limites Decimal existentes.

Retorno `{success:true,data:{transfer_reference,saida,entrada,replayed}}`;
cada lado inclui `movimentacao` e `saldo` após aquela operação. Primeira gravação
retorna 201, repetição equivalente retorna 200 com os saldos históricos originais,
mesmo depois de outros movimentos. Reusar referência da mesma origem com dados
diferentes é recusado. Origem + referência são convertidas em chave interna
determinística; referência igual usada por outra origem é uma operação distinta.
Dados inválidos/conflito retornam 422, sem confirmação parcial.

GET/POST exigem `movimentacaos.create` e `saldos.list`, além de autenticação.
Erros HTML preservam campos digitados. A função interna também desfaz alterações
se falhar; a regra central impede invocar uma perna isolada ou usar chaves
reservadas `transfer:` como movimento manual. Uma referência com histórico
incompleto é recusada e não é reparada automaticamente.

## Limites mantidos

Não transfere o saldo global legado; não altera lotes/validade, reservas de
produção, pedidos, títulos financeiros ou obrigações fiscais. A quantidade
transferida é na unidade-base compartilhada. Não faz rateio de frete ou
comparação cambial de fornecedores. Consultas históricas e documentos já
congelados mantêm seus contratos anteriores.

## Evidências

313 casos distintos passaram: 9 da área organizacional da cotação, 25 de
transferência e 279 de contexto/estoque/cadastro monetário/compras existentes
e do teste JavaScript UTF-8 de versões. Verificações incluem valor/quantidade
conservados, políticas de precisões diferentes, taxa com par/organização/data
corretos, idempotência, falha de entrada/commit, permissões, transferências
concorrentes iguais e inversas, e o JavaScript real de seleção/convite.
