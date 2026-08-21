# 03 — Funcionalidades (Yeast Bank)

## Cepas

Cadastro/edição: nome, família, fornecedor, notas, e parâmetros de
viabilidade (avançado — pode deixar no padrão). Lista mostra só as
ativas (lixeira separada).

## Dispositivos de Armazenamento

O freezer, geladeira ou câmara fria físico. Se tiver sensor, as
leituras de temperatura aparecem automaticamente no histórico —
senão, dá pra lançar manualmente.

## Containers

A organização dentro de um Dispositivo — uma caixa, estante ou
prateleira. Todo Container pertence a exatamente um Dispositivo (não
existe Container "solto", fora de um freezer/geladeira). É aqui que
você agrupa as amostras pra saber onde procurar fisicamente sem abrir
o freezer inteiro.

## Itens do Banco

O que você guardou fisicamente de uma cepa — data de congelamento,
em qual Container está guardado, status (ativo/descartado/
contaminado). O dispositivo onde o item está é sempre o dispositivo do
Container escolhido — você não escolhe o dispositivo direto no item.
Um item descartado ou contaminado é ignorado no cálculo de
viabilidade.

## Leituras de Armazenamento

Histórico de temperatura do Dispositivo — vem automaticamente se ele
tiver sensor vinculado, ou pode ser lançada manualmente.

## Starters

Registro de cada starter (propagação) feito com uma cepa — serve tanto
de histórico quanto de referência pro cálculo de viabilidade quando
não há uma contagem de célula real disponível.

## Contagens de Célula

Registro manual de uma contagem real (ao microscópio, por exemplo) —
é a fonte mais confiável pro cálculo de viabilidade, quando disponível.

## Recalcular Viabilidade

Botão que recalcula a viabilidade estimada de **todas** as suas cepas
de uma vez. Pra cada item, o sistema usa a melhor referência
disponível, nesta ordem de prioridade: contagem real → viabilidade
estimada anterior → starter → valor inicial cadastrado da cepa. Itens
descartados/contaminados são pulados.

## Lixeira

Registros movidos para lixeira somem da lista principal, mas
continuam recuperáveis até serem excluídos de vez.
