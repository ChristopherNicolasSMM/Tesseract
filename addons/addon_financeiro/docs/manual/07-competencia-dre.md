# Competência e DRE gerencial — segunda entrega da consolidação

Acesse Financeiro > Workspace financeiro > **DRE e resultados**. A área tem
Demonstrativo, Revisão assistida, Classificações e Apropriações e ajustes.
Exige a permissão `financial_results.list`; escritas exigem administrador.
As permissões anteriores não são ampliadas automaticamente para usuários.

## Competência não é pagamento

O principal de um título é reconhecido uma única vez, com o valor base congelado
na emissão. Parcelas, pagamentos parciais e recebimentos não repetem esse valor.
Por exemplo, um aluguel de 1.200 apropriado em outubro e novembro, 600 por mês,
produz despesa de 600 em cada competência, independentemente da data do pagamento.
O reconhecimento de competência não modifica caixa, títulos, compras ou estoque.

Nenhum título existente recebe competência presumida. A revisão assistida mostra
as origens ainda sem reconhecimento, inclusive componentes financeiros das
baixas. A revisão é do cadastro atual da organização, não limitada pelo período
do cabeçalho. Reconhecimentos e classificações também possuem histórico próprio.

## 1. Classificar as categorias

Em Classificações, escolha a categoria e registre grupo, mês inicial da vigência,
motivo e chave de idempotência. A versão esperada aparece no formulário; conflito
exige atualizar e revisar, sem sobrescrever outra classificação.

Grupos disponíveis: receita bruta, deduções da receita, custos reconhecidos,
despesas operacionais, receitas financeiras, despesas financeiras, tributos
sobre o lucro e **Não afeta o resultado**. Categorias de receber admitem receita,
receita financeira e exclusão; categorias de pagar admitem os demais grupos.
Cadastre categorias financeiras separadas em Configurações quando necessário.

Cada alteração cria uma versão. O reconhecimento exige escolher uma versão
explicitamente e uma competência igual ou posterior ao seu mês inicial. Versões
anteriores permanecem selecionáveis para revisão histórica explícita. Alterar a
classificação atual não recalcula os reconhecimentos antigos.

## 2. Revisar e apropriar uma origem

Na Revisão assistida, classifique as categorias pendentes e use Preparar
apropriação. Também é possível partir do detalhe do título pelo botão
Apropriar competência / DRE. Confira origem, total base e moeda; escolha a
classificação, motivo e chave de idempotência.

Adicione linhas com competência, valor base e centro de custo. As linhas devem
somar **exatamente** o total base da origem. Até 120 linhas; não há distribuição
ou arredondamento automático. Resíduos devem ser informados explicitamente na
última linha. O mesmo mês pode ter vários centros; não repita mês/centro na lista.

Use Conferir apropriações antes de Confirmar reconhecimento. A prévia não grava.
Erros preservam os valores e rateios digitados. Cada origem só pode ter um
reconhecimento ativo; repetir a mesma chave/conteúdo retorna o evento original.

### Compras e exclusões patrimoniais

Títulos originados de compras de estoque só podem ser reconhecidos em **Não afeta
o resultado** nesta entrega. Isso regulariza a revisão sem transformar o pagamento
da compra em despesa. O custo reconhecido dos produtos terá integração própria
na próxima entrega. Produção, compras, pagamentos e custo não devem ser somados
como despesas duplicadas. Exclusões aparecem com efeito zero no demonstrativo.

### Componentes das baixas

Juros, multa, desconto, diferença cambial e resíduo de arredondamento são origens
separadas, somente quando seu valor base for diferente de zero. Valores e moeda
vêm da baixa congelada, sem recotação. O grupo financeiro exigido é informado
na revisão. Desconto em pagamento representa receita financeira; em recebimento,
despesa financeira. Diferenças cambiais e resíduos têm direção conforme o efeito
registrado. O principal continua pertencendo ao reconhecimento do título.

### Ajustes manuais

Use Ajuste manual documentado para apropriações explícitas, como depreciações,
tributos ou correções sem pagamento imediato. Informe referência exclusiva,
moeda base, total, política monetária (vazio = configuração inicial/v1), linhas
mensais e evidência no motivo. Ajustes podem reconhecer ou reduzir valores.
A política escolhida precisa ser válida na primeira competência apropriada.

Não use ajuste para repetir principal ou componente já registrado. O sistema
impede repetição da mesma referência ativa, mas referências diferentes exigem
conferência do administrador quanto à mesma evidência econômica.

## 3. Conferir demonstrativo e composição

O período seleciona competências mensais **integrais**, do primeiro dia do mês
inicial ao último dia do mês final. Selecionar 01/10–19/10 representa outubro
inteiro para esta DRE; não faz um corte diário das apropriações mensais.

A tabela apresenta receita líquida, resultado bruto, operacional, financeiro,
antes dos tributos e resultado líquido gerencial parcial, com colunas mensais
e acumulado. Centro de custo filtra os valores. Clique em uma linha de grupo
para filtrar a composição; os subtotais continuam mostrando o demonstrativo.
Cada reconhecimento possui origem, competência, classificação/versionamento,
centro registrado, autor e motivo; o link abre o evento mesmo fora da primeira
página do histórico. Moedas originais não são somadas; o resultado usa a moeda base.

A DRE permanece marcada **parcial**, mesmo com zero pendências cadastradas:
integração automática de custos, conferência de cobertura e fechamento ainda
não estão disponíveis. Ausência de registros não comprova resultado zero.

## 4. Corrigir com histórico

Estorne integralmente o reconhecimento com motivo e nova chave e, se necessário,
reapresente a mesma origem com novas competências ou classificação. O estorno
retira o evento ativo e reapresenta suas competências originais; não lança uma
nova despesa/receita no mês atual, não movimenta caixa e não apaga registros.
A consulta representa o estado atual por competência, não uma posição histórica
"como era conhecido naquele dia". Fechamento e bloqueio de competência são da
próxima etapa.

Para cancelar um título reconhecido, estorne antes o reconhecimento do principal.
Para estornar uma baixa com componentes reconhecidos, estorne antes esses
reconhecimentos. O principal pode permanecer reconhecido quando apenas um
pagamento é estornado: pagamento e competência são eventos independentes.

## Relatórios

O botão Relatório da organização / período abre o Reports. Crie/publice um modelo
pelo exemplo **DRE gerencial por competência**, selecione organização e datas,
gere HTML e imprima/salve PDF pelo navegador. O relatório preserva valores exatos
e informa o caráter parcial. Centro/grupo não são propagados por esse botão;
fontes JSON podem informar esses filtros explicitamente. Sem Reports ativo,
a DRE e as operações do workspace permanecem disponíveis.
