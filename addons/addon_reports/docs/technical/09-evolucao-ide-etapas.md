# Evolução da IDE — execução em grupos de três etapas

O usuário validou a entrega HTML no Windows: relatório exibido e execução
possível. Isso não confirma todas as opções do diálogo de impressão nem o
runtime nativo opcional. A geração de patch passa a ocorrer a cada três etapas.

| Grupo | Etapas | Situação |
| --- | --- | --- |
| 1 | Propriedades visuais; formatos e parâmetros; organização da IDE | Etapas 1–3 concluídas; patch consolidado do grupo 1 |
| 2 | Colunas de composição; imagens; paginação | Planejado |
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
