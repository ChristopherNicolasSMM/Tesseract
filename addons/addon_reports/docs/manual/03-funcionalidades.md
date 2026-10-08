# Funcionalidades

## Layout

Insira texto, tabela ou divisor. Selecione o elemento pela folha ou pela lista Estrutura. Mova acima/abaixo ou remova usando os botões de propriedades. Texto pode ser fixo ou associado a um campo. Tabela permite escolher coleção, nome de coluna, campo e adicionar/remover colunas. Campos ausentes no contrato são sinalizados.

## Dados e parâmetros

Informe o contrato dos dados e um exemplo para testar. Parâmetros possuem definição e valores padrão; valores de teste não substituem os padrões do modelo. O formulário ainda usa JSON para configurações técnicas.

## Salvar e pré-visualizar

Salve manualmente. A tela avisa quando existem alterações não salvas e impede trocar de modelo/revisão antes de salvar. Erros são mostrados pelos avisos padrão do sistema. Prévia HTML usa os dados de exemplo e configurações atuais; alterações posteriores tornam a prévia antiga indisponível/desatualizada.

## Publicação e versões

Publicar exige a permissão correspondente e valida estrutura, dados, parâmetros e composição HTML; não exige WeasyPrint. Uma revisão publicada não pode ser editada. Nova revisão cria uma cópia; a versão anterior continua disponível. Não há comparação visual entre versões neste primeiro corte.

## Aparência

A IDE segue o tema do Tesseract. No tema escuro, a folha em edição é cinza azulada. PDF e impressão permanecem em papel branco. Trocar tema não altera o modelo salvo.

## Emissão nos consumidores

O detalhe do saldo oferece relatório HTML apenas daquele material. A aba Sessões oferece
relatório HTML da sessão selecionada na planta. As ações aparecem para quem possui as
permissões de Reports e do domínio, quando Reports está ativo. O seletor mostra
somente modelos com revisão ativa publicada cujo contrato corresponde ao
consumidor. Uma revisão nova em rascunho não substitui a publicação anterior.

## Impressão e quebra de página

A prévia HTML usa os dados efetivos, em documento contínuo. No tema escuro,
a folha da prévia também é cinza azulada. O botão Imprimir / salvar PDF imprime
somente o relatório, sem os controles da IDE ou do consumidor. A mídia de
impressão aplica papel branco. Use o componente Quebra de página para iniciar
um novo trecho na impressão; na tela ele aparece como linha tracejada.

Selecione A4, escala adequada e confira margens/cabeçalhos do navegador.
Quebras automáticas, repetição de cabeçalhos e linhas muito altas dependem do
navegador. Não há promessa de paginação idêntica à prévia contínua ou a outro
motor. O servidor retorna HTML por padrão e não recebe o PDF salvo pelo usuário.

## Aparência dos componentes

Selecione um texto para ajustar alinhamento, negrito, tamanho de fonte e
espaçamentos no painel Aparência. As medidas são em pontos (pt). Campo vazio
mantém o padrão do componente; zero remove o espaçamento correspondente.
Restaurar aparência padrão preserva o conteúdo e sua vinculação.

Em tabelas, ajuste fonte e espaço das células. Cada coluna permite alinhamento
e largura percentual. A soma das larguras definidas deve ser até 100%; deixe
vazio para cálculo automático. Salve e confira a prévia com os dados reais.
Essas propriedades também são usadas na impressão. Modelos publicados precisam
de Nova revisão antes de editar. A configuração do papel será ampliada depois.

## Formatos e valores dos parâmetros

Em textos e colunas, selecione Formato para apresentar número, moeda,
percentual, data ou data/hora. Moeda muda a apresentação, sem converter valores.
Percentual usa uma fração: 0.25 aparece como 25,00 %. Informe números nos dados
com ponto decimal e datas como 2026-10-08. Data/hora aceita ISO com T e mantém
o offset informado. O texto Valor nulo aparece somente quando o dado é null.

Na aba Parâmetros, o formulário de valores acompanha as definições em JSON.
O mesmo formulário aparece na emissão de Estoque/BrewStation. Marque Informar
valor para enviar uma chave; desmarque para usar o padrão, se existir. Zero e
Não são valores válidos. Use JSON avançado para objetos/arrays ou null explícito
que não pertença a um enum. Valores de teste não alteram as definições/defaults.
Ao trocar de modelo/revisão, os valores de teste são reiniciados.

## Organização dos componentes

Adicione uma seção para agrupar componentes. Com a seção selecionada, os novos
componentes são inseridos dentro dela. Selecione um componente na árvore ou
na folha para editar. Seção de destino permite movê-lo para outro grupo ou
para Documento. As setas mudam a ordem dentro do mesmo grupo.

Duplicar componente também duplica todos os filhos de uma seção. Remover uma
seção remove seus filhos. Salve para persistir; a prévia resolve os dados e
mostra o relatório final sem os contornos de edição. Revisões publicadas são
somente leitura; clone uma revisão para editar.

## Colunas de composição

Use Colunas de composição para criar um agrupamento com duas seções filhas.
Selecione uma seção filha e adicione textos, tabelas ou outros componentes.
Eles ficam juntos na mesma coluna. No agrupamento, configure 1–4 colunas de
largura igual e espaço de 0–24 pt entre elas. Mudar a quantidade reorganiza
o conteúdo sem removê-lo; filhos excedentes seguem para novas linhas.

Cada filho direto do agrupamento ocupa uma célula. Use Seção de destino para
transferir conteúdo para a coluna desejada. Duplicação e ordenação seguem
as mesmas regras das demais seções. Tabelas mantêm suas próprias colunas
de dados, que são uma configuração diferente das colunas de composição.

Em tela estreita, a composição aparece empilhada para leitura. A impressão
continua em colunas e com fundo branco. Verifique a prévia antes de imprimir.

## Imagens e logotipos

Clique Imagem / logotipo e selecione um PNG ou JPEG local. A imagem fica
incorporada à revisão; o relatório não precisa de um endereço externo para
carregá-la. Para trocar, selecione o componente e use Selecionar PNG ou JPEG.
Arquivo inválido não substitui o anterior.

Configure largura em mm e, opcionalmente, altura. Altura vazia mantém a
proporção natural. Com altura definida, a imagem cabe na caixa sem deformar
ou cortar. Escolha alinhamento e forneça descrição alternativa. Imagens
podem ficar em seções e colunas, ser duplicadas e acompanhar novas revisões.

Use arquivos de até 128 KiB, até 2048 pixels por lado e até 4 milhões de
pixels. O template aceita até 16 imagens e 512 KiB somadas, inclusive
duplicatas. SVG, GIF e animações não são aceitos. Prepare um arquivo menor
antes de selecionar quando necessário. O tema escuro muda a folha, mantendo
as cores e a transparência do logotipo; na impressão a folha é branca.

## Página e paginação

Na aba Layout, abra Página e impressão. Escolha A4, A5 ou Letter, retrato
ou paisagem, e margens de 0–40 mm. O padrão permanece A4 retrato com 15 mm.
Restaurar página A4 não altera o conteúdo. A configuração acompanha a revisão.

Numerar páginas acrescenta Página X de Y ao rodapé em navegadores compatíveis
(testado no Chromium 134). Essa opção precisa de margem inferior de ao menos
8 mm. No diálogo de impressão, confira papel/orientação e desative os
cabeçalhos/rodapés automáticos do navegador para não acrescentar informações.

No painel de um componente, abra Paginação para iniciar uma nova página antes
ou depois dele ou tentar mantê-lo inteiro. Um componente maior que a página
pode se dividir mesmo com essa preferência. O marcador Quebra de página
continua disponível fora dos grupos de colunas. Dentro de colunas, aplique
a quebra ao agrupamento inteiro, não a um de seus filhos. Para tabelas muito
longas, prefira o fluxo normal fora das colunas.

A prévia HTML é contínua e não mostra antecipadamente o total de páginas.
Confira a paginação no diálogo Imprimir / salvar PDF. A folha impressa
é branca em ambos os temas. As escolhas feitas no diálogo podem alterar
a saída em relação ao template.
