# 03 — Funcionalidades (Yeast Bank)

## Painel

Tela de entrada (menu "Banco de Levedura" → "Painel") — reúne Cepas e
Eventos numa tela só, com atalhos pras demais telas.

- **Aba Cepas**: clique numa cepa da lista pra ver, do lado, todos os
  itens do banco dela — em qual Container/Dispositivo está, posição,
  tipo de armazenamento, viabilidade estimada e status. Linhas com
  aviso de validade/viabilidade baixa aparecem destacadas.
  - Logo abaixo, um **resumo da cepa**: total de itens, quantos
    ativos, quantos descartados, quantos contaminados (separados),
    quantos em alerta, e a viabilidade média entre eles.
  - Clicando num item específico da lista, aparece um **detalhe do
    item**: última contagem registrada, a contagem anterior a ela
    (pra comparar a tendência), a viabilidade estimada atual, e uma
    estimativa de quando vale a pena fazer o próximo starter (com
    base na configuração de alerta do tipo de armazenamento). Um
    botão "Nova Contagem pra este Item" já cria o registro vinculado
    e te leva direto pra edição — sem precisar trocar de aba.
- **Aba Eventos do Banco**: clique num evento pra ver a cepa, status
  atual em cards, e as contagens de célula daquele item. O botão
  "Novo Evento do Banco" leva pra tela de Eventos do Banco (onde a
  criação de verdade acontece — Painel é só navegação e consulta).
  Quando o evento selecionado é do tipo Starter, os campos dele
  (data de início, volume alvo, objetivo, status, viabilidade
  resultante, estimativa de células) aparecem direto no card — não
  tem tela separada pra abrir, é tudo no próprio evento.
- **Atalhos** (botões no topo): Dispositivos de Armazenamento e
  Configuração do Banco — abrem as telas próprias delas.

## Cepas

Cadastro/edição: nome, família, fornecedor, notas, e parâmetros de
viabilidade (avançado — pode deixar no padrão, ou usar a Configuração
do Banco por tipo de armazenamento, ver abaixo). Lista mostra só as
ativas (lixeira separada).

## Dispositivos de Armazenamento

O freezer, geladeira ou câmara fria físico. Guarda a última
temperatura registrada (atualizada manualmente por enquanto, sem
sensor integrado ainda).

## Containers

A organização dentro de um Dispositivo — uma caixa, estante ou
prateleira. Todo Container pertence a exatamente um Dispositivo (não
existe Container "solto", fora de um freezer/geladeira). É aqui que
você agrupa as amostras pra saber onde procurar fisicamente sem abrir
o freezer inteiro.

## Configuração do Banco

Botão de atalho (não é uma lista que você navega dentro dela) — define,
por tipo de armazenamento (Agar Inclinado, Seca, etc.), três coisas
que alimentam o cálculo automático:

- **Prazo de validade** — quantos dias depois de preparado o item
  vence. Preenche a data de validade sozinho quando você cadastra um
  Item do Banco daquele tipo (só se você não tiver digitado uma data
  manualmente).
- **Decaimento diário** — se cadastrado, passa a valer no lugar do
  decaimento da cepa pra todo item daquele tipo de armazenamento.
- **Alertas** — dias antes de vencer e/ou viabilidade mínima que
  merecem atenção. Quando um item cruza qualquer um dos dois limites,
  a tela dele mostra um aviso — sem e-mail, sem notificação, é só um
  sinal visual.

Só existe uma configuração ativa por tipo de armazenamento.

## Itens do Banco

O que você guardou fisicamente de uma cepa — data de congelamento,
em qual Container está guardado, status (Ativo/Descartado/
Contaminado). O dispositivo onde o item está é sempre o dispositivo do
Container escolhido — você não escolhe o dispositivo direto no item.
Um item descartado ou contaminado é ignorado no cálculo de
viabilidade.

Quando um item se aproxima do vencimento ou da viabilidade mínima
cadastrada na Configuração do Banco, a tela mostra um aviso — não
manda notificação nenhuma, é só um sinal visual pra você perceber ao
olhar a lista.

## Eventos do Banco

Ponto de entrada pra registrar o que acontece com um item — todo
evento novo nasce aqui. Ao criar um evento, você escolhe o tipo:

- **Starter** — os campos da propagação (data de início, volume alvo,
  objetivo, status, viabilidade resultante, estimativa de células)
  ficam direto no próprio evento — não existe mais uma tela separada
  de "Starter", é tudo aqui.
- **Contagem de Células** — cria automaticamente um registro de
  Contagem vinculado e já te leva direto pra tela dele, pra você
  preencher a contagem (veja "Contagens de Célula" abaixo).
- **Descarte** — muda o status do Item de verdade (pra Descartado ou
  Contaminado, você escolhe qual). O status anterior é registrado
  sozinho no evento, como histórico.
- **Outro** — fica só no próprio evento, com observações, sem mudar
  nada no item.

Contagens de Célula **não têm mais botão de criação direto na própria
tela** — nascem sempre a partir de um Evento do Banco tipo "Contagem
de Células". Você ainda pode editar/consultar uma contagem já
existente normalmente, só a criação passa por aqui.

## Contagens de Célula

Registro de uma contagem real — nasce a partir de um Evento do Banco
tipo "Contagem de Células". É a fonte mais confiável pro cálculo de
viabilidade, quando disponível.

Se você usa câmara de Neubauer, dá pra digitar direto o que contou
(células vivas, células mortas, quantos quadrados usou, fator de
diluição) e o sistema calcula sozinho células/mL e % de viabilidade —
sem precisar fazer a conta na mão. Se preferir, ainda dá pra digitar
o resultado final direto, sem passar pelos campos brutos.

Registro de uma contagem real (ao microscópio, por exemplo) — nasce a
partir de um Evento do Banco tipo "Contagem de Células". É a fonte
mais confiável pro cálculo de viabilidade, quando disponível.

## Recalcular Viabilidade

Botão que recalcula a viabilidade estimada de **todos** os itens de
uma vez. Pra cada item, o sistema usa a melhor referência disponível,
nesta ordem de prioridade: contagem real → viabilidade estimada
anterior → starter → valor inicial cadastrado da cepa. O decaimento
usado é o da Configuração do Banco (se existir uma pro tipo de
armazenamento do item) ou o da cepa, como padrão. Itens
descartados/contaminados são pulados.

## Lixeira

Registros movidos para lixeira somem da lista principal, mas
continuam recuperáveis até serem excluídos de vez.
