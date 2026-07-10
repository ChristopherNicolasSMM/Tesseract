# 03 — Funcionalidades (Yeast Bank)

## Cepas

Cadastro/edição: nome, família, fornecedor, notas, e parâmetros de
viabilidade (avançado — pode deixar no padrão). Lista mostra só as
ativas (lixeira separada).

## Itens do Banco

O que você guardou fisicamente de uma cepa — data de congelamento,
onde está guardado, status (ativo/descartado/contaminado). Um item
descartado ou contaminado é ignorado no cálculo de viabilidade.

## Leituras de Armazenamento

Histórico de temperatura do local onde o item está guardado — vem
automaticamente de um Dispositivo vinculado, se você tiver um, ou pode
ser lançada manualmente.

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
