# Perguntas frequentes

## Por que não posso salvar uma revisão publicada?
Use Nova revisão para criar uma cópia editável e preservar o documento anterior.

## O que significa conflito de edição?
Outra alteração foi salva na mesma revisão. Sua edição não será enviada por cima dela. Compare e recarregue antes de tentar novamente.

## O tema escuro aparece no PDF?
Não. A folha escura é usada durante a edição e a prévia HTML.

## A prévia usa dados reais do estoque?
A prévia da IDE utiliza os exemplos configurados. Os botões de emissão no
detalhe do saldo e na aba Sessões utilizam os dados reais registrados.

## O seletor de emissão está vazio?
Carregue um exemplo compatível na IDE, salve e publique. Apenas uma revisão
ativa publicada aparece nesse seletor; um modelo sem contrato correspondente
ou ainda em rascunho não aparece.

## O custo não mudou depois de alterar a receita?
O relatório da brassagem mostra o custo registrado na confirmação dos insumos.
Não recalcula a receita nem cria um histórico que a sessão não possui.

## Preciso instalar Pango/MSYS2 para usar Relatórios?

Não para editar, publicar, visualizar HTML ou imprimir pelo navegador existente.
WeasyPrint e suas bibliotecas nativas são opcionais, usados apenas na emissão
PDF explícita no servidor. Imprimir / salvar PDF abre o diálogo do navegador;
o usuário escolhe o destino e o local do arquivo. Não é download PDF automático.

## Preciso de instalador externo para os logotipos?

A validação usa Pillow, uma biblioteca Python incluída nos requisitos do
addon. Instale `python -m pip install -r addons/addon_reports/requirements.txt`
no ambiente do Tesseract. O fluxo HTML continua sem WeasyPrint/Pango.

## Posso vincular a imagem a uma URL ou aos dados enviados?

Nesta etapa, a imagem é um arquivo PNG/JPEG incorporado ao template. Não
aceita URL externa, caminho local do servidor ou binding aos dados.


### Por que um componente com condição ainda aparece na folha de edição?

O canvas mantém todos os componentes acessíveis para edição. A condição só
altera a prévia e a saída gerada. Confira os parâmetros e dados usados na prévia.

### Por que o total pode diferir da soma dos números arredondados da tela?

O cálculo usa os valores originais e arredonda somente o resultado. Soma,
média, mínimo e máximo ignoram nulos; contagem inclui todas as linhas.
