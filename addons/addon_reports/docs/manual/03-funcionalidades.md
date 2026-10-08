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
