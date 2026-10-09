# Fase 3 — cadastro monetário exato de cotações e pedidos

Continuação do patch organizacional `8cad061`, validado pelo usuário.
Arquivo: `tesseract-fase3-compras-moeda-decimal.patch`.
Migration: `b48d5e09a673`, após `a37c4d98f562`.

## Aplicação

Na raiz do Tesseract, com os patches anteriores aplicados e o diretório de
trabalho limpo:

```powershell
git am --keep-cr .\tesseract-fase3-compras-moeda-decimal.patch
python run.py db upgrade
python -m pytest tests/test_purchase_pricing.py tests/test_organization_stock.py tests/test_purchase_integrity.py tests/test_purchase_organization_context.py tests/test_addon_estoque.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py tests/test_financeiro_policy_versions.py::test_real_template_js_preserves_conflict_expectation -q
```

Reinicie a aplicação após o upgrade. O teste JavaScript utiliza Node já
disponível no ambiente de testes. Sua captura mantém `encoding='utf-8'`,
incluindo a correção anteriormente entregue para Windows.

Se `git am` apontar conflito, preserve o erro e verifique a base antes de
prosseguir; `git am --abort` cancela a tentativa. Não use `stamp` para pular
a migration. O upgrade aceita schema compatível criado por `create_all()`;
schema incompatível falha antes de alteração. O downgrade com histórico
monetário existente é bloqueado.

## O que mudou

`PurchasePricing` registra uma moeda explícita e os números originais como
strings decimais em um snapshot imutável, associado a uma cotação OU pedido.
Quantidade, preço unitário, subtotal, fator/quantidade-base e frete do pedido
são calculados com `Decimal` e preservados em SQLite sem conversão para REAL.
O snapshot registra organização, fornecedor, autor/data e origem dos itens
herdados de uma cotação.

A tela antiga continua como cadastro estrutural de cabeçalho/material/unidade
e itens. O novo cadastro monetário é uma confirmação separada, antes de escolher
vencedores/enviar o pedido. Ele recebe números como texto, permite conferir e
redigitar os valores originais, e os congela. Colunas Float antigas recebem
apenas cópias para compatibilidade; geração, avaliação e recebimento do
documento congelado usam os valores exatos. Isso não torna retroativamente
exatos os números digitados nas telas antigas.

O cadastro fica imutável também em rascunho: moeda, fornecedor, frete, itens,
quantidades, preços e fatores protegidos não podem mudar depois. Para corrigir,
preserve o documento e crie outro rascunho. A guarda cobre ORM/serviços e APIs
antigas; não depende de esconder botões. Observações/status do pedido continuam
seguindo as regras já existentes de compras.

## Fluxo do pedido avulso

1. Crie o pedido em rascunho, vincule sua organização explicitamente e cadastre
   os itens/material/unidade pelos controles existentes.
2. Abra **Cadastro monetário em rascunho** na página do contexto organizacional:
   `/estoque/pedido-compras/<id>/cadastro-monetario`.
3. Selecione a moeda original, confira/redigite quantidade e preço de todos os
   itens, declare o frete e confirme o congelamento.
4. Confirme o pedido. Na avaliação monetária, a moeda original precisa coincidir
   com a moeda congelada. Se for estrangeira, escolha taxa explícita da mesma
   organização/par/data e a versão de política desejada.
5. Congele a avaliação e registre a entrada. O saldo da organização recebe
   quantidade-base e valor convertido a partir dos números exatos. O frete
   continua fora do valor de estoque.

## Fluxo da cotação

1. Vincule a organização ao processo antes de convidar fornecedores.
2. Cadastre os itens solicitados e as respostas dos fornecedores. A cotação deve
   estar em `rascunho` ou `respondida`, com processo `aberto`/`comparado`.
3. Volte ao contexto organizacional do processo: a lista traz o link de cadastro
   monetário de cada fornecedor. Rota:
   `/estoque/processo-cotacaos/<process_id>/cotacoes/<quotation_id>/cadastro-monetario`.
4. Declare moeda, quantidade efetiva ofertada e preço exato de todos os itens
   ativos daquela resposta; frete da cotação é zero nesta etapa. Congele antes
   de selecionar qualquer vencedor ou gerar pedido.
5. A aba Comparação exibe os números exatos e a moeda, na ordem calculada com
   Decimal no servidor. Seleção/geração exigem cadastro monetário de todas as
   respostas com itens quando qualquer uma adotou o novo fluxo.
6. Se as moedas diferirem, a comparação/seleção/geração é bloqueada. Também se
   bloqueiam fatores congelados distintos para o mesmo item solicitado. Não
   há paridade cambial, comparação em moeda-base ou conversão de unidade
   automática nesta entrega. Processos inteiramente legados mantêm seu fluxo.
7. Gere os pedidos dos vencedores. Moeda, números exatos, fator original e
   proveniência são transportados. A geração tem um commit único: falha em
   qualquer pedido/cadastro monetário desfaz todos os novos pedidos e vínculos.
   Depois, confirme/avalie/receba cada pedido como acima.

## Contrato web/JSON

GET nas telas acima retorna HTML; com `Content-Type: application/json`, retorna
`{success, data}`, com o cadastro congelado ou `null`. POST JSON usa o mesmo
contrato das telas, exige todos os itens ativos sem duplicatas e recebe:

```json
{
  "currency_code": "USD",
  "freight": "0",
  "items": [
    {"id": 123, "quantity": "2", "unit_price": "0.123456789012"}
  ]
}
```

`id` é inteiro positivo; números monetários/quantidades são textos decimais
ou Decimal no serviço Python, nunca float/bool no novo contrato. Quantidade
positiva, preço/frete não negativos, sem vírgula, expoente, NaN ou Infinity.
Limites do contrato financeiro permanecem: magnitude menor que `1e18` e até
12 casas decimais para os valores e resultados originais/subtotais/base. Um
produto que exceda esses limites é recusado antes de confirmar; não há corte
ou arredondamento silencioso para encaixá-lo.

Respostas: 201 no primeiro congelamento, 200 na repetição equivalente, 409 na
repetição com valores diferentes, 422 nos dados/estados inválidos. Erros no
formulário preservam os valores digitados. Documento/cotação de outro processo
retorna 404; autenticação e permissões existentes continuam obrigatórias.

Comparação: GET `/estoque/processo-cotacaos/<id>/comparacao-monetaria` retorna
JSON `{success, exact, currency_code, items}` no fluxo exato, ou `exact:false`
para processo sem cadastros monetários. Cada item possui quantidade/preço/
subtotal como strings, fornecedor/material, seleção/geração. Dados incompatíveis
retornam 422, sem recorrer à comparação Float. Não cria avaliação cambial,
movimento de estoque, título ou pagamento.

| Operação | Permissões exigidas |
| --- | --- |
| Cadastro do pedido (GET/POST) | pedido_compras.update + item_pedido_compras.update |
| Cadastro da cotação (GET/POST) | processo_cotacaos.update + cotacaos.update + item_cotacaos.update |
| Consulta de comparação | processo_cotacaos.detail + item_cotacaos.list |
| Selecionar vencedor/gerar pedido | Permissões das ações existentes; mesmas validações do serviço |

Não há menu novo nem consulta direta a modelos financeiros pelo Estoque.
Moedas/opções vêm do contrato público do Financeiro. Organização continua
vindo do vínculo Core explícito, sem inferência por usuário.

## Histórico e limites

Pedidos sem cadastro monetário continuam usando o adaptador Float já existente
na avaliação. Nenhuma linha antiga recebe moeda/organização automaticamente.
Avaliações já congeladas permanecem iguais e não podem receber um novo cadastro
monetário. Alterar o fator atual da unidade não recalcula a resposta congelada
nem o pedido gerado; o snapshot original é transportado.

Ainda pendentes: comparação cambial entre fornecedores em moedas diferentes,
entrada estrutural inteira em Decimal pelos formulários antigos, cadastro
exato do fator de conversão de unidade, recebimento parcial/estorno, rateio de
frete, seleção organizacional do BrewStation, conciliação de estoque legado e
obrigações/parcelas/liquidações financeiras. Esta entrega não cria contas a
pagar nem regras fiscais/PDV.

Executados 289 casos distintos: 32 do novo cadastro monetário, 38 de estoque
organizacional, 218 de compras/estoque legado e migrações, e o teste JavaScript
UTF-8 de versões. Os testes incluem concorrência de congelamento/transferência,
rollback da geração, preservação de histórico e comparação exata.

Validação usa Python/Flask/SQLAlchemy/SQLite, Node com DOM mínimo e migrações
reais. Não constitui certificação visual em navegador, Windows nativo ou
PostgreSQL. O patch é conferido por `git am --keep-cr` em uma cópia da base,
com árvore final idêntica.
