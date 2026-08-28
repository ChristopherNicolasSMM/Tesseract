# 03 — Funcionalidades (Estoque)

## Materiais

Cadastro de tudo que pode ser estocado — matéria-prima, embalagem, ou
um kit composto por outros materiais. Cada material tem: nome, SKU
(código único), fabricante (opcional), origem, tipo de produto,
categoria, e campos fiscais opcionais (NCM, CEST).

Materiais criados automaticamente pela importação do BrewFather (veja
o manual de Integração BrewFather) aparecem marcados como "pendente de
revisão" — não é um erro, é só um aviso de que os dados foram
preenchidos com valores padrão e podem ser completados quando você
tiver tempo. Isso não impede o material de ser usado normalmente em
movimentações.

## Movimentações

Todo registro de entrada, saída ou ajuste de quantidade de um
material. Uma vez lançada, uma movimentação não é editada — se um
lançamento estiver errado, a correção é um novo lançamento de ajuste,
nunca alterar o que já foi salvo.

## Saldo de Estoque

Mostra a quantidade atual de cada material, calculada automaticamente
a partir das Movimentações — você não edita o saldo diretamente aqui.

## Composições

Para materiais que são, na prática, outro material embalado de forma
diferente (ex.: um saco de 25kg de um insumo que também é vendido em
pacotes de 1kg) — a composição registra essa relação pai/componente,
usada como referência, sem mexer no estoque automaticamente.

## Unidades de Material (compra × consumo)

Um material pode ser comprado numa unidade e usado/movimentado em
outra — o exemplo mais comum é comprar um saco de 25kg de um insumo,
mas consumir esse insumo em frações de 1kg. Para isso, cada Material
pode ter mais de uma "Unidade" cadastrada (na tela de detalhe do
próprio Material, seção "Unidades").

**Como preencher o campo "Fator para Unidade-Base"** — ele responde
"quantas unidades da unidade-base equivalem a 1 desta unidade que
estou cadastrando?":

- Na unidade marcada como **"É a Unidade-Base?"**, o fator é sempre
  **1** — é a própria referência.
- Em qualquer outra unidade do mesmo Material, o fator é quantas
  unidades-base cabem dentro dela.

Exemplo — Material "Malte Pilsen" com unidade-base em **kg**:

| Unidade cadastrada | É Unidade-Base? | Fator para Unidade-Base |
|---|---|---|
| `kg` | Sim | `1` |
| `saco25kg` | Não | `25` (1 saco = 25 kg) |
| `g` | Não | `0.001` (1 grama = 0,001 kg) |

Só pode existir **uma** unidade marcada como base por Material — o
sistema recusa se você tentar marcar uma segunda. Se precisar trocar
qual é a base, desmarque a antiga primeiro.

O Saldo de Estoque é sempre calculado na unidade-base — comprar em
"sacos" e consumir em "kg" não gera inconsistência, a conversão
acontece automaticamente ao registrar a compra ou o consumo.

## Fabricantes, Origens, Tipos de Produto, Categorias

Telas de apoio — cadastros simples (só um nome) usados para
classificar os materiais. Vale cadastrar os valores que sua operação
usa antes de cadastrar o primeiro material.

## Fornecedores e Transportadoras

Cadastros de quem fornece os materiais e de quem faz o transporte.
Cada Fornecedor e cada Transportadora podem ter mais de um endereço
associado (cobrança, entrega, correspondência, faturamento, etc.) —
isso é feito direto na tela de detalhe de cada um, seção "Endereços",
sem precisar de uma tela separada.

## Pedidos de Compra

Um Pedido de Compra tem um Fornecedor (e opcionalmente uma
Transportadora), e uma lista de Itens — cada item é um Material, a
unidade de compra escolhida, a quantidade e o preço. O pedido nasce em
**rascunho** e passa por: enviado → confirmado → recebido.

Ao marcar como **recebido**, o sistema gera automaticamente uma
Movimentação de entrada de estoque pra cada item — você não precisa
lançar isso manualmente depois.

## Cotação de Fornecedores (RFQ)

Quando você quer comparar preço entre vários fornecedores antes de
fechar uma compra, use um **Processo de Cotação** em vez de um Pedido
de Compra direto:

1. Crie o Processo de Cotação e liste os **Itens Pedidos** (Material +
   quantidade desejada) — isso é feito **uma vez só**, mesmo que vários
   fornecedores sejam convidados depois.
2. Na aba "Cotações", convide um ou mais fornecedores.
3. Pra cada fornecedor, abra "Responder Preços" e digite o preço que
   ele cobrou por cada item — ao salvar, uma mensagem confirma que o
   preço foi gravado.
4. Na aba "Comparação", veja todos os preços lado a lado (agrupados
   por item, ordenados do mais barato pro mais caro) e clique em
   "Selecionar" no fornecedor vencedor de cada item — o botão vira
   verde e uma mensagem confirma a seleção. Clicar em "Selecionar" de
   outro fornecedor para o mesmo item troca o vencedor automaticamente
   (não precisa desmarcar antes).
5. Quando terminar de escolher os vencedores, clique em **"Gerar
   Pedido"** — o sistema cria um Pedido de Compra (em rascunho, pronto
   pra revisar) pra cada fornecedor vencedor, já com os itens certos.

**Sobre as mensagens que aparecem e somem sozinhas**: toda ação de
salvar/selecionar nessas telas mostra uma confirmação rápida no canto
da tela (alguns segundos) — é só uma indicação de que a ação
funcionou, não precisa fazer nada com ela.
