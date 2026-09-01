# 04 — Perguntas Frequentes (Envase)

**P: Preciso digitar quais materiais de embalagem entraram no envase?**
R: Não mais. Cadastre isso uma vez só, na Composição do Material
resultante (Estoque) — todo Envase feito com esse mesmo Material
reaproveita a mesma lista automaticamente.

**P: O Material resultante não aparece pra escolher / dá erro ao
envasar.**
R: Confira se o Material resultante tem o campo **Volume Real**
preenchido — sem ele, o sistema não consegue calcular quantas unidades
o envase representa e recusa o registro.

**P: Por que o estoque de insumo de receita (malte, lúpulo) foi
descontado sozinho quando eu envasei, sem eu pedir?**
R: Se o lote ainda não tinha passado pelo botão "Confirmar
Ingredientes", o Envase faz essa confirmação automaticamente antes de
prosseguir — o sistema nunca deixa um Envase acontecer sem saber
quanto custaram os insumos daquele lote.

**P: Cliquei em "Confirmar Ingredientes" duas vezes por engano — vai
descontar o estoque duas vezes?**
R: Não. A confirmação só tem efeito na primeira vez; clicar de novo
só mostra o que já foi confirmado, sem descontar nada de novo.

**P: Ainda tenho Envases antigos com "Itens de Envase" cadastrados —
eles somem?**
R: Não, ficam intactos como estavam. Só os Envases novos passam a
funcionar pelo Material resultante + Composição.
