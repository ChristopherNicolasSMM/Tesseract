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


## Blocos reutilizáveis

Selecione um componente ou uma seção na árvore. Em Blocos reutilizáveis,
informe uma chave única (letras minúsculas, números, ponto, hífen ou sublinhado,
começando por letra) e um nome. Salvar seleção como bloco grava primeiro as
alterações pendentes do template e salva uma cópia fixa da seleção.

Escolha o bloco no catálogo e use Inserir cópia em um rascunho. Com uma seção
selecionada, a cópia entra nela; com outro componente selecionado, entra no
mesmo grupo. A cópia tem IDs próprios e pode ser editada independentemente.
Os vínculos são preservados: confira dados e parâmetros do destino na prévia.
As definições de parâmetros, a página e os dados de exemplo não são importados.

Arquivar bloco pede confirmação e retira a opção do catálogo, preservando
cópias já inseridas e relatórios publicados. Sua chave não fica disponível
para reutilização. Para outra variante, salve uma nova seleção com outra chave.
O catálogo depende das permissões de modelos de relatório do seu usuário.


## Exibição condicional

Selecione um componente e abra Exibição condicional nas propriedades.
Escolha Comparar campo, selecione o campo dos dados ou parâmetros, e escolha
Igual a ou Diferente de. Informe o tipo e o valor esperado. Texto "1" é
diferente do número 1; falso é diferente de zero; nulo é um valor próprio.
Uma seção oculta também oculta seus filhos. Sempre exibir remove a regra.

O canvas mantém todos os componentes visíveis para edição. Use Prévia HTML
para conferir o resultado com os dados e parâmetros atuais. Campo ausente
gera erro, mesmo se você estiver comparando com nulo. Uma condição não é uma
regra de permissão de acesso ao relatório.

## Totais nas tabelas

Em cada coluna, escolha Total da coluna: soma, média, mínimo, máximo ou
contagem de linhas. Sem total deixa a célula do rodapé vazia. O rodapé aparece
uma vez, depois das linhas, e acompanha a impressão. Soma/média/mínimo/máximo
usam valores numéricos e ignoram nulos; contagem inclui todas as linhas.

Em tabela vazia, soma e contagem mostram zero; outras operações mostram o
texto configurado para nulo. Configure Número ou Moeda na coluna para formatar
o total; contagem sempre mostra inteiro. Os cálculos usam valores originais,
antes do arredondamento de apresentação. Dados em moedas ou unidades diferentes
precisam ser normalizados antes de gerar o relatório.

O total pode ir para a folha seguinte se não houver espaço no fim da tabela.
Confira o resultado no diálogo de impressão antes de salvar o PDF.


## Desfazer, refazer e atalhos

Use Desfazer e Refazer na barra de ações para recuperar alterações locais do
rascunho: componentes, propriedades, página, contrato, dados de exemplo e
definições de parâmetros. Os botões ficam desabilitados quando não há histórico.
Editar depois de desfazer elimina o caminho anterior de refazer.

O histórico pertence à revisão aberta, fica apenas na memória e é apagado ao
salvar, recarregar ou trocar de revisão/modelo. Ele não recupera edições de
sessões anteriores. Desfazer não desfaz publicação, criação ou arquivamento
de blocos; alterações restauradas precisam ser salvas novamente.

Ctrl+S (Cmd+S no macOS) salva o rascunho. Fora de campos de texto, Ctrl+Z
desfaz e Ctrl+Shift+Z ou Ctrl+Y refaz. Dentro dos campos, o navegador mantém
seu próprio desfazer de digitação; use os botões para restaurar o documento.
Atalhos não atuam com um modal aberto nem em revisão publicada. Os valores
informados para testar parâmetros não fazem parte do histórico do template.


## Biblioteca de modelos operacionais

Em Relatórios → Modelo de relatório, selecione um modelo pronto e clique em criar.
A ação cria e salva um rascunho com estrutura e contrato; não publica nem inventa
dados. Se a chave já existir, abra o modelo existente ou clone sua versão.

No editor, escolha a fonte correspondente, busque e selecione uma receita ou
sessão quando solicitado e clique em carregar dados reais. Para validade,
informe a janela de dias e opcionalmente a data de referência (padrão: dia UTC).
Confira a prévia, salve e imprima pelo navegador. A folha acompanha o tema
escuro na edição (cinza azulado #273549) e fica branca na impressão.

| Modelo | Conteúdo existente utilizado |
| --- | --- |
| Receita completa | Cadastro atual, ingredientes, mostura, fermentação e água |
| Sessão detalhada | Sessão, etapas registradas, logs, alarmes, observações e valores armazenados |
| Estoque atual | Saldos legados do exportador de estoque, identificados no título |
| Banco de leveduras | Itens, cepas, localização, datas e viabilidade já registrada |
| Dashboard geral | Contagens de registros, sessões, leveduras e starters existentes |
| Disponibilidade e validade | Itens ativos do banco de leveduras: disponíveis, a vencer, vencidos e sem validade |
| Planejamento de starters | Eventos Starter já cadastrados como planned ou active |
| Checklist de receita | Dados atuais da receita e campos em branco para conferência manual |

Carregar dados exige as permissões de leitura das fontes. Os dados são uma
cópia do momento da consulta: salvar ou abrir a prévia persiste essa cópia nos
dados de exemplo do relatório. Quem puder ler o relatório poderá acessar essa
cópia; verifique o público do modelo antes de salvar informações sensíveis.
Atualize a cópia explicitamente para obter registros mais recentes.

Não há baixa de estoque, recalculo de viabilidade, criação de starter ou alteração
da receita/sessão. A disponibilidade não certifica uso biológico; usa status e
datas cadastrados. O estoque não representa o novo saldo por organização.
O checklist não marca regras como cumpridas automaticamente. Receita atual
não equivale a uma fotografia histórica da receita usada em uma sessão.
