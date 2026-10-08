# Evolução da IDE — execução em grupos de três etapas

O usuário validou a entrega HTML no Windows: relatório exibido e execução
possível. Isso não confirma todas as opções do diálogo de impressão nem o
runtime nativo opcional. A geração de patch passa a ocorrer a cada três etapas.

| Grupo | Etapas | Situação |
| --- | --- | --- |
| 1 | Propriedades visuais; formatos e parâmetros; organização da IDE | Etapas 1–3 concluídas; patch consolidado do grupo 1 |
| 2 | Colunas de composição; imagens; paginação | Etapas 4–6 concluídas; patch consolidado do grupo 2 |
| 3 | Blocos reutilizáveis; condições e totais; produtividade | Planejado |
| 4 | Consolidação; avaliação do PDF automático opcional | Planejado |

## Etapa 1: propriedades visuais

Templates v1 mantêm os campos anteriores; `props.style` é opcional. Fonte
8–48 pt, margens superior/inferior 0–48 pt, espaço interno 0–24 pt,
alinhamento left/center/right/justify e negrito booleano. Valores inteiros;
CSS livre, URLs e propriedades desconhecidas são rejeitados antes da composição.
Ausência de propriedade mantém o padrão; zero é valor válido. Restaurar aparência
remove somente style, preservando conteúdo e vínculos. Trocar texto literal/campo
preserva style. Revisão publicada mantém controles desabilitados.

Tabelas aceitam cell_padding 0–24 pt. Colunas possuem width opcional 1–100 (%)
e align opcional. Soma das larguras explícitas não pode ultrapassar 100.
Colunas não configuradas usam o cálculo automático do navegador; as larguras
são orientações de composição, não promessa de medida física exata.

Canvas mostra propriedades visuais; prévia HTML usa dados resolvidos. Tema
escuro continua com papel #273549 e impressão branca. Não há cores/fontes
customizadas nesta etapa. Nenhuma migration ou dependência adicional.

As etapas 2 e 3 abaixo acrescentam formatos, parâmetros e edição de seções.

Etapa 1: 64 testes e 10 subtestes passaram em 13,64 s. Um teste de PDF
real WeasyPrint permaneceu opt-in, desabilitado. Suíte inclui contratos
malformados, larguras, estilos, compatibilidade, persistência/publicação/clone.
CSS de impressão preserva papel branco; não exige nova dependência.

Navegador aprovado: propriedade de fonte/alinhamento persiste após recarregar;
tabela aplica alinhamento e espaço de células na prévia. Entrada inválida é
bloqueada antes de salvar/publicar/visualizar, preservando o campo para correção.
Percurso anterior (temas, impressão, versões, conflito e consumidores) passou
com Playwright 1.51.1 / Chromium 134. Capturas claras e prévia escura inspecionadas.
Nenhum patch nesta etapa; entrega consolidada ao concluir 1–3.

## Etapa 2: formatos e formulário de parâmetros

`props.format` nos textos e `columns[].format` nas tabelas são opcionais.
`kind`: raw, number, currency, percent, date ou datetime. Numéricos aceitam
`decimals` inteiro 0–6 (padrão 2). Currency aceita BRL/USD/EUR (padrão BRL),
sem conversão. Decimal e ROUND_HALF_UP produzem apresentação pt-BR; percent
multiplica a fração por 100. Valores numéricos incompatíveis, booleanos, NaN,
infinito e magnitude fora do limite são rejeitados. Strings numéricas usam
ponto decimal; não reinterpretar separador brasileiro nos dados de entrada.

`null_text` até 120 caracteres substitui somente null, sem confundir zero,
falso e texto vazio. Campo ausente continua falha de vínculo. Tudo é escapado.
Datas exigem YYYY-MM-DD; datetime exige data/hora ISO com T. Offset informado
é mostrado, sem conversão de fuso nem uso do timezone do servidor.

Formulário compartilhado entre IDE e consumidores: strings, datas quando
schema.format=date, números, inteiros, booleanos e enums. Marcar Informar valor
inclui a chave; desmarcar omite e permite o default do servidor. Parâmetro
obrigatório sem default não pode ser desmarcado. JSON avançado permanece para
objetos, arrays e schemas complexos, também para null explícito fora de enum.
Defaults não são gravados automaticamente nos valores fornecidos. A API recebe
os mesmos JSONs anteriores; backend revalida tudo por JSON Schema.

Catálogo dos consumidores acrescenta parameters somente de revisões ativas
publicadas e compatíveis, sem exigir permissão de edição/detail. Consulta dos
parâmetros ocorre na mesma sessão de leitura e em lote; não expõe layout,
sample_data ou rascunho. Nenhuma migration/dependência adicional.

Etapa 2 validada: 91 testes e 10 subtestes passaram em 74,55 s; 1 teste PDF
WeasyPrint opt-in desabilitado. Formatos persistem e são preservados na cópia
de revisão. Backend distingue defaults por omissão, null, zero e falso.
Playwright 1.51.1 / Chromium 134 aprovado: propriedades visuais e monetárias,
formulário IDE/consumidores, valores zero/falso, null explícito no JSON avançado,
temas, impressão, versões e conflito. Sem pageerror. Captura do formulário
inspecionada. JSON de definição permanece avançado nesta etapa.

## Etapa 3: estrutura e organização

Árvore e canvas mostram seções e componentes aninhados. Adicionar enquanto uma
seção está selecionada insere dentro dela; selecionar um componente insere
no mesmo grupo. O seletor Seção de destino move para outra seção ou Documento.
Destinos no próprio componente/subárvore são excluídos. Setas ordenam irmãos;
remover seção remove sua subárvore. Duplicar copia conteúdo, estilos, formatos
e vínculos, com novos IDs em todos os descendentes e sem referências mutáveis
compartilhadas. Não há arrastar/soltar, desfazer ou salvamento automático.

Operações respeitam 200 componentes e profundidade 8, com rollback quando
ultrapassam os limites. Servidor continua revalidando o JSON. Painel de árvore
possui rolagem; canvas delimita seções sem inserir seus rótulos no relatório.
Propriedades permanecem no padrão Bootstrap/NiceAdmin, com conteúdo e aparência.
Tema escuro mantém papel cinza azulado; impressão branca. Nenhuma migration,
dependência de produção ou biblioteca nativa nova.

Validação grupo 1: 92 testes Python e 10 subtestes passaram; 1 PDF WeasyPrint
opt-in desabilitado. Cinco testes Node cobrem cópia independente, ordenação,
remoção, prevenção de ciclos e rollback dos limites. Playwright/Chromium
aprovado com seções, duplicação, mudança de destino, salvar/reabrir,
temas, formatos, parâmetros, publicação, conflito e consumidores HTML.
Captura escura inspecionada. Impressão testada pelo helper e PDF do Chromium;
não substitui validação do diálogo de impressão no Windows.

## Etapa 4: colunas de composição

Seções v1 acrescentam props.columns inteiro 1–4 (padrão 1) e props.gap
inteiro 0–24 pt (padrão 8). Sem mudança de schema_version ou migration.
Seções anteriores permanecem verticais. Booleanos, strings, frações e valores
fora do intervalo são rejeitados. CSS Grid é gerado somente pelo compositor;
nenhum CSS livre ou recurso externo é aceito.

Cada filho direto ocupa uma célula, na ordem da árvore; células adicionais
formam novas linhas. Para manter vários componentes juntos numa coluna, use
uma seção filha como célula. Botão Colunas de composição cria duas seções
filhas em um agrupamento de duas colunas. Alterar quantidade reorganiza os
filhos existentes e não cria/apaga conteúdo. Destino, duplicação, ordenação,
estilos e vínculos usam as operações de seção já existentes.

Larguras iguais com minmax(0,1fr), gap configurável e quebra de textos longos.
Canvas empilha em largura de tela até 767 px; prévia empilha quando seu próprio
viewport tem até 600 px. As regras são restritas à mídia screen; impressão
mantém colunas e papel branco, inclusive sob tema escuro. A etapa 6 abaixo define o comportamento de conteúdo longo e de quebras nos grupos de colunas. Compatibilidade com
PDF automático WeasyPrint ainda depende de validação do runtime opcional;
nesta etapa o caminho principal continua HTML/impressão pelo navegador.

Sem patch antecipado: entrega consolidada será feita ao concluir etapas 4–6.

Validação etapa 4: 104 testes Python e 10 subtestes aprovados; 1 teste
WeasyPrint opt-in desabilitado. Cinco testes Node aprovados. Playwright
1.51.1/Chromium 134 aprovado: criação, propriedades e persistência da
composição, conteúdo em células lado a lado, empilhamento da prévia estreita,
três trilhas de grid na mídia print, temas, formatos, parâmetros, versões,
conflitos e consumidores. Teste de reabertura aguarda conclusão do carregamento
assíncrono para evitar contar uma árvore ainda não preenchida.

## Etapa 5: imagens e logotipos incorporados

Componente image em schema_version=1: props.source obrigatório como data URI
base64 de PNG ou JPEG; alt opcional até 240 caracteres; width inteiro 5–180 mm
(padrão 40); height opcional inteiro 5–250 mm. Sem height mantém proporção
natural; com height usa caixa com object-fit:contain sem deformação/corte.
max-width:100% mantém a imagem dentro da coluna. style tipado controla
alinhamento, margens e padding; sem filtros ou alterações das cores do arquivo.

Seleção local lê bytes no navegador e incorpora ao JSON da revisão; não cria
arquivos no servidor ou URLs públicas. Troca de arquivo inválido mantém imagem
anterior. Servidor revalida na gravação/publicação/renderização. Revisões
publicadas continuam imutáveis pelo serviço; duplicação/clone carregam os
mesmos bytes como valores independentes. Não há binding de imagem aos dados
nesta etapa, banco de assets compartilhados, recorte, SVG/GIF ou animação.

Pillow 12.3.0 é dependência Python do addon, instalada via pip com wheel
compatível; não exige MSI/Pango para fluxo HTML. Image.open restringe codecs
a PNG/JPEG, verify confere integridade e uma segunda abertura/load decodifica
os pixels para rejeitar truncamento. MIME declarado deve corresponder ao
formato real. Limites: 128 KiB por arquivo, 2048 px por lado, 4 milhões de
pixels, uma frame; 16 imagens e 512 KiB somadas por template, inclusive cópias.
Limites JSON 1 MiB e HTML 2 MiB permanecem. Imagens devem ser preparadas dentro
do limite antes da seleção; não há compressão ou redimensionamento automático.

CSP do documento e resposta HTML admite img-src data:, mantendo os demais
recursos restritos. Worker opcional aceita somente data URI PNG/JPEG validada
pelo mesmo serviço; continua rejeitando rede, file://, SVG e outros dados.
WeasyPrint não foi executado: este ajuste foi verificado no fetcher, sem
afirmar validação do PDF nativo. HTML/Chromium é o caminho exercitado.

Referência da biblioteca: https://pillow.readthedocs.io/en/stable/reference/Image.html
Patch continua reservado ao fechamento das etapas 4–6. Sem migration.

Validação etapa 5: 132 testes Python e 10 subtestes aprovados; 1 WeasyPrint
opt-in desabilitado. Cinco testes Node da árvore aprovados. Playwright
1.51.1/Chromium 134 aprovado para seleção PNG, substituição JPEG, substituição
inválida sem perda, medidas, descrição, duplicação, remover cópia, salvar/
reabrir, imagem em colunas, raster carregado na prévia, tema escuro e folha
branca em print. Percurso anterior da IDE/consumidores também passou.
Captura do componente/painel inspecionada. Serviço/fetcher verificados sem
acionar WeasyPrint, nenhuma instalação nativa adicional.

## Etapa 6: página, fragmentação e numeração

Layout v1 aceita page opcional. Campos: format A4/A5/Letter, orientation
portrait/landscape, margin_top/right/bottom/left inteiros 0–40 mm e
number_pages booleano. Ausência mantém A4 retrato, 15 mm e sem numeração.
number_pages exige margem inferior mínima de 8 mm; null, CSS livre, campos
desconhecidos e tipos incompatíveis são rejeitados. Restaurar página A4
remove somente page e preserva componentes, estilos, imagens e vínculos.

IDE possui Página e impressão recolhível, canvas proporcional à página e
margens escolhidas. Documento de edição e prévia continuam contínuos; não
calculam antecipadamente o número de folhas. Papel escuro #273549 na tela e
branco em print, incluindo números de página. Configuração fica no JSON
da revisão, preservada na publicação/clone. Sem migration adicional.

props.pagination opcional em componentes exceto page_break: break_before,
break_after e keep_together, todos booleanos. Geram somente CSS confiável
break-before:page / break-after:page / break-inside:avoid quando true.
Keep together é uma preferência: componentes maiores que a área imprimível
podem se dividir. Imagens recebem break-inside:avoid por padrão; tabelas
continuam com cabeçalho repetível e linhas com break-inside:avoid.

Quebras forçadas dentro de qualquer descendente de seção columns>1 são
rejeitadas, inclusive marcador page_break. Use a quebra antes/depois do
agrupamento inteiro, ou um marcador fora dele. UI desabilita essas opções;
operações de árvore validam destino e fazem rollback ao mover para posição
incompatível. Backend revalida inclusive clientes HTTP/Python. Keep together
dentro de colunas é permitido. Não há promessa de fragmentação de tabelas
muito longas lado a lado; prefira tabela longa fora das colunas.

Numeração usa @page / @bottom-right com counter(page)/counter(pages).
Validada no Chromium 134; outros motores podem ignorar caixas de margem.
Desative cabeçalhos/rodapés automáticos do navegador quando usar a numeração
do template, evitando conteúdo adicional. PreferCSSPageSize usado nos testes;
o diálogo local pode alterar papel, escala, margens e destino. Referência:
https://developer.chrome.com/blog/print-margins . Não há cabeçalho/rodapé
customizado, posição absoluta, total de páginas pré-calculado na IDE ou
PDF automático sem runtime opcional.

Validação local das etapas 4–6: 159 testes Python e 10 subtestes passaram;
1 teste WeasyPrint opt-in desabilitado. Seis testes Node aprovados.
Playwright/Chromium aprovado para página A5 paisagem, margens, restauração,
publicação somente leitura, colunas, imagens, temas, impressão, versões e
consumidores. PDF de tabela com 100 linhas gerou 9 páginas A5 paisagem e
5 páginas A4 retrato; todas as linhas foram preservadas, cabeçalhos repetidos,
imagem presente, números corretos em cada página e fechamento em página
separada. PDF anterior com quebra explícita manteve 2 páginas. PDFs renderizados
em PNG e inspecionados (primeira paisagem e terceira retrato), sem cortes.
WeasyPrint não foi executado; Windows depende da validação após aplicação.
