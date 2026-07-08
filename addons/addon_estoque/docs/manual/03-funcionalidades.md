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

## Fabricantes, Origens, Tipos de Produto, Categorias

Telas de apoio — cadastros simples (só um nome) usados para
classificar os materiais. Vale cadastrar os valores que sua operação
usa antes de cadastrar o primeiro material.
