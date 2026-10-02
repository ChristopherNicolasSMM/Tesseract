# 03 — Funcionalidades (Controle de Mostura)

## Receitas

Cadastro de receitas de brassagem — etapas de mostura, perfil de
água, etapas de fermentação e os ingredientes usados (ligados a um
Material do Estoque). A ressincronização da receita do Brewfather cria
uma versão nova; os snapshots existentes ficam disponíveis no histórico.
A edição manual pelo formulário atual ainda altera a versão existente.

### Conferir uma receita antes de gerar a sessão

No **Workspace de Planta**, abra a aba **Receita Mash** e escolha a
receita importada ou cadastrada. A ficha mostra origem e versão,
ingredientes com o estado do vínculo ao estoque, prévia de custo,
perfis de água, fermentação e a timeline. A planta escolhida já vem
selecionada ao gerar a sessão. A consulta não baixa materiais do
estoque: a confirmação do consumo acontece na tela do lote.
Ao gerar a sessão dentro do workspace, o lote aparece selecionado na
aba **Sessões**. O botão **Nova** nessa aba volta à escolha de receita
sem abrir outra janela. Um rascunho pode ser criado com ingredientes
pendentes, mas a confirmação do consumo depende da revisão desses itens.

Quando o volume planejado não foi registrado, a ficha mostra **não
informado**. Se faltar vínculo, quantidade, unidade compatível ou custo
médio, os avisos indicam o que revisar; valores parciais não são
apresentados como custo completo. Links para editar cada item continuam
disponíveis enquanto o cadastro não estiver incorporado ao workspace.

## Plantas e Tanques

Sua estrutura física — panela de mostura, caldeira, fermentador — e o
mapeamento de qual sensor/atuador (Função de Dispositivo) cada
tanque usa para cada papel (leitura de temperatura, controle de
aquecimento, etc.).

O **Workspace de Planta** aparece no menu de Controle de Mostura e na
lista de espaços de trabalho. Na aba **Planta** é possível cadastrar
tanques e vincular uma função de dispositivo a um papel por tanque.
O formulário aceita sensores para leitura de temperatura e atuadores
para aquecimento ou fluxo; uma função híbrida serve para ambos. Cada
tanque admite um vínculo ativo por papel. Os links de edição ainda
abrem o cadastro completo.

Os atalhos **Importar Receita para Brassar**, **Dashboard** avulso e
**Widgets de Dashboard** foram ocultados do menu: suas operações
estão nas abas Receita Mash e Dashboard. Suas rotas continuam ativas.
Os cadastros e históricos com consulta própria continuam disponíveis
para edição e consulta completa. Ao atualizar uma instalação, execute
`flask db upgrade` para aplicar a visibilidade no menu existente.

### Navegação de configuração e sessões

No menu **Controle de Mostura**, o grupo **Plantas e configuração**
oferece **Abrir planta**, Tanques, Mapeamentos de Planta e Layouts de
Dashboard. O grupo **Sessões de brassagem** oferece **Abrir fluxo de
sessões** e o acesso aos cadastros completos de sessões, passos, logs
e alarmes. Ao escolher uma planta nesses fluxos, a aba correspondente
já abre selecionada. O cadastro avulso de plantas não aparece mais no
menu; o cadastro e a edição continuam acessíveis no workspace.

Ingredientes, etapas de brassagem e etapas de fermentação são
consultados na aba **Receita Mash**. Suas páginas de edição continuam
disponíveis pelos links de cada item, mas suas listas gerais deixam
de ocupar o menu lateral. O perfil de água é exibido por contexto:
origem, alvo, mostura, lavagem e total. Até cinco linhas por receita
são esperadas quando todos os contextos vieram do Brewfather.

### Consulta agrupada da água

**Perfis de Água** abre agora uma lista de cards de receitas, com
busca pelo nome e indicação da versão. **Consultar perfis** abre uma
tela própria com um card por contexto e todos os íons em ppm, além
do pH. Valores ausentes aparecem como não informados. Os contextos
não são somados. A aba Receita Mash também possui um link para essa
consulta. A lista de registros individuais continua disponível em
**Manutenção dos registros de água**, para edição e exportação.

Se as entradas antigas de ingredientes, etapas, fermentação ou plantas
ainda estiverem no menu, execute `flask db upgrade`, reinicie o sistema
e atualize a página. Para reaplicar a configuração de visibilidade,
use `flask hide-legacy-mash-control-menu` (ou acrescente `--dry-run`
para conferir antes). Esse comando não remove páginas nem dados.

O workspace integra cadastro inicial e consulta. A edição completa dos
cadastros, os registros detalhados de sessão e a consulta de históricos
ainda usam páginas próprias. Ocultar uma entrada do menu não incorpora
automaticamente todas as suas operações ao fluxo.

### Editar planta, tanques e vínculos no workspace

Na aba **Planta**, **Editar Planta** abre o formulário local de nome,
descrição, capacidade e ativação. O lápis de cada tanque abre sua
identificação, tipo, ordem e descrição. O lápis do mapeamento abre
tanque, papel, função, identificação do vínculo e obrigatoriedade.
Ao salvar, a aba é atualizada; editar o nome também atualiza o título
do workspace. A função de dispositivo usa o combo de busca padrão.

Cada operação exige a permissão de atualização da entidade. O servidor
confere os vínculos com a planta aberta e não permite transferir um
tanque para outra planta por esse formulário. O mapeamento pode mudar
de tanque dentro da própria planta, mas não duplicar um papel existente.
Papéis personalizados existentes são preservados quando mantidos na
edição. Capacidades devem ser positivas ou ficar sem preenchimento.

Os cadastros completos continuam disponíveis para configuração
avançada, exclusão e restauração. A edição dos layouts e os registros
detalhados das sessões ainda serão incorporados em etapas posteriores.
Este patch não acrescenta alterações de esquema no banco.

## Sessões de Brassagem

Acompanhamento de uma brassagem em andamento: etapas, logs (incluindo
os gerados automaticamente pela automação), e alarmes (que podem ser
confirmados/reconhecidos por um usuário).

Na tela de cada sessão, o botão **Confirmar Ingredientes** dá baixa no
estoque dos insumos da receita (malte, lúpulo, levedura) e trava o
custo total gasto — só tem efeito uma vez por lote. Não é obrigatório
clicar antes de envasar: se você for direto pro Envase sem confirmar,
o sistema confirma sozinho nesse momento (ver manual de Envase).

## Regras de Automação

Cadastro de regras (sensor → condição → ator) que **já disparam de
verdade** — assim que uma leitura chega de um sensor vinculado, o
sistema avalia a condição da regra e, se verdadeira, aciona o ator
correspondente sozinho, sem precisar de ninguém clicando em nada. Cada
disparo fica registrado no histórico da regra (valor que disparou,
ação tomada, se deu certo).

## Dashboards

A tela principal pra acompanhar uma brassagem em andamento. Cada
Dashboard é um painel visual que você monta — não vem pronto, você
arrasta os elementos que quiser acompanhar.

### Montando um painel (modo edição)

Clique em "Modo Edição" no topo da tela. Isso abre uma **paleta** do
lado esquerdo com os elementos disponíveis:

| Ícone | O que mostra |
|---|---|
| Temperatura | Valor atual de um sensor, em número |
| Gauge | Valor atual de um sensor, em mostrador circular |
| Gráfico | Histórico de um sensor ao longo do tempo |
| Botão | Liga/desliga de um atuador |
| Tanque | Desenho de tanque (panela, fermentador) com nível de líquido |
| Etapa | Card com a etapa atual da brassagem — ver seção própria abaixo |
| Alarme | Lista de alertas já disparados e agendados |
| Texto | Texto livre — título, aviso, instrução |
| Imagem | Imagem sua (logo, foto do equipamento, diagrama) |

Arraste o ícone da paleta pra qualquer lugar do painel. O elemento
aparece **sem estar ligado a nada ainda** — um selo cinza "Não
configurado" avisa disso. Clique nele (sem arrastar) pra abrir o
**painel de configuração** do lado direito: escolha ali o
sensor/atuador/tanque que ele deve mostrar, ajuste legenda, cor,
faixa de valores, etc. O selo some assim que salvar. O mesmo painel
também tem o botão "Remover", pra tirar o elemento do painel.

Pra mover um elemento já colocado, arraste-o pelo meio. Pra
redimensionar, arraste o cantinho inferior direito. Saia do Modo
Edição quando terminar — a tela volta a só mostrar os valores, sem as
alças de edição.

### Tubulação entre tanques

Com Planta vinculada ao Dashboard, o botão "Tubulação" abre um editor
onde você liga um tanque a outro (ex.: panela de mostura → caldeira
de fervura), escolhendo a bomba/válvula que controla esse fluxo — a
linha acende quando o atuador está ligado.

A linha nasce reta, mas você pode dar forma a ela: com a tubulação
selecionada (clique nela em Modo Edição), arraste o meio de qualquer
trecho pra criar uma curva, arraste os pontos verdes nas pontas pra
mudar onde ela sai/entra do tanque, e selecione um ponto de curva +
tecla Delete pra removê-lo. Isso é útil principalmente pra
**recirculação** (um tanque ligado a ele mesmo) — nesse caso a
tubulação já nasce com uma alcinha pronta pro lado de fora, em vez de
ficar escondida atrás do próprio desenho.

### Card de Etapa

Mostra a etapa atual da brassagem (mostura ou fervura) sem precisar
sair do Dashboard pra outra tela:

- **Nome e temperatura alvo** da etapa em andamento.
- **Contagem regressiva** (minutos:segundos) até a etapa terminar.
- **Duas barras de progresso**: uma de **rampa** (tempo até chegar na
  temperatura alvo) que some assim que a rampa termina, e uma de
  **patamar/hold** (o tempo que a etapa fica naquela temperatura) que
  assume a partir daí.
- **Próxima etapa**, como prévia.
- Botão **"Concluir e Avançar"** — sempre disponível, mesmo antes do
  tempo acabar (a contagem regressiva é só uma sugestão, quem decide é
  você). Ganha destaque quando o tempo já passou.
- Botão **"Voltar"** — se você avançou por engano ou quer refazer a
  etapa anterior, ele reativa a etapa de trás e reinicia o timer dela.

O ícone de lista no canto do card abre **"Gerenciar Etapas"**: uma
tela pra adicionar, editar ou remover etapas da receita sem sair do
Dashboard. Como isso edita a **receita** (não só esta sessão), tem um
botão **"Ressincronizar com a sessão"** — use-o depois de mudar algo
ali pra essas mudanças aparecerem na brassagem que já está em
andamento (etapa já concluída ou em andamento nunca é alterada por
esse botão, só as que ainda não começaram).

## Conferência de ingredientes do lote

Na tela da sessão, a tabela **Insumos da Receita** mostra cada linha como Pronto, Pendente ou Não consumir. O atalho Receita abre o planejamento no workspace. Se já houver sessão vinculada, prepare uma revisão para os próximos lotes antes de editar ingredientes. Para água ou outros itens deliberadamente fora do estoque, selecione o status **Não consumir do estoque** no ingrediente; essa decisão fica registrada na receita e a linha não gera baixa. Quantidades inválidas, material ausente ou unidade sem conversão deixam a confirmação bloqueada e mostram a causa. O mesmo bloqueio vale se o envase tentar confirmar ingredientes automaticamente. Para receitas sem ingredientes cadastrados, o comportamento anterior de confirmação sem baixas é preservado.
## Sanear ingredientes na receita

Na aba Receita da planta, selecione uma receita sem sessões vinculadas e
abra **Sanear ingrediente** na linha desejada. Busque o Material de Estoque
e clique em **Salvar decisão**. A tabela de conferência e a estimativa são
atualizadas mantendo a receita selecionada. Vincular não cria material nem
retira nada do estoque; quantidade e unidade permanecem iguais.

Para itens deliberadamente fora do estoque, escolha **Não consumir do estoque**
e confirme no diálogo. Cancelar mantém a decisão anterior. É possível voltar
a vincular um material em receita ainda editável. Confira os avisos: vínculo
não resolve automaticamente unidade incompatível ou quantidade incompleta.

Receitas já vinculadas a qualquer sessão, inclusive na lixeira, exibem bloqueio
da edição local para preservar os lotes. Use **Criar revisão desta receita**
para preparar uma versão separada.
O formulário só aparece para usuários com permissão de editar ingredientes.
O cadastro completo continua acessível com seu funcionamento anterior.

### Criar revisão e ajustar dados planejados

1. Na aba Receita, abra **Criar revisão desta receita**, informe uma observação
   opcional e clique em **Criar revisão**. Confirme no modal do Core.
2. A nova versão abre na mesma planta. Copia volume planejado, ingredientes
   ativos com vínculos/decisões, timeline e alertas, fermentação e todos os
   contextos de água ativos. Os IDs internos dos alertas apontam para a cópia.
   Registros na lixeira não são copiados. O número será maior que todas as
   versões do mesmo nome, mesmo quando a origem for uma versão antiga.
3. Abra **Sanear ingrediente** e, no formulário **Dados planejados do ingrediente**,
   ajuste quantidade, unidade pesquisável, tipo, etapa de uso, uso detalhado,
   tempo de adição e especificações. Clique em **Salvar dados planejados**.
   O vínculo/decisão de estoque é salvo pelo formulário separado acima.
4. Confira pendências, custo estimado e timeline. Para lúpulo de fervura, o
   tempo representa minutos restantes até o término. Os alertas automáticos
   são atualizados junto com os dados; alertas manuais são preservados.
5. Gere a próxima sessão com a nova versão quando o planejamento estiver pronto.
   O lote antigo continua com receita, etapas, confirmação e custo registrado
   anteriores. Criar revisão ou editar dados não movimenta estoque.

A unidade **PCT** não significa 1 kg: o conteúdo/conversão deve estar cadastrado
no material. Selecionar uma unidade não converte a quantidade automaticamente.
Campo vazio continua pendente quando necessário; quantidade zero também não
libera consumo. Valores legados podem ser mantidos até seu saneamento, mas
novas unidades precisam existir no catálogo.

Criar revisão exige permissão de criar receitas e consultar etapas; editar
os dados exige permissão de editar ingredientes. Toda gravação dos dados
alterados registra um snapshot com o operador autenticado. Falha na cópia
ou no registro desfaz a tentativa. Referências inválidas a etapas/ingredientes
apagados ou de outra receita precisam ser corrigidas antes de revisar.
As ações avançadas de cadastro, de-para, importação e runtime mantêm seus
fluxos existentes; o bloqueio aqui se refere à edição local de ingredientes.

## Preparar embalagens para o lote

Na aba **Sessões**, card **Envase e precificação**, abra **Preparar envase
deste lote**, busque o produto e informe os litros. **Consultar prévia de
embalagens** mostra unidades, composição, necessidade, saldo e estimativa.
Custos ausentes deixam a estimativa parcial; o custo registrado de insumos
é separado e preservado. Confira o aviso de consumo automático de ingredientes
ainda não confirmados no registro existente. A prévia não grava envase,
não reserva/baixa estoque nem confirma ingredientes. Registro e estorno
continuam nas telas existentes. [Manual de envase](../../../feature_envase/docs/manual/03-funcionalidades.md).

## Seletores e aproveitamento da tela de mostura

Na aba Sessões, a lista e o resumo ficam na primeira linha. Os demais cards
ocupam a largura abaixo, incluindo ingredientes e preparação de envase.
Em uma janela estreita, os cards são empilhados.

Para escolher planta, tanque, painel, sessão, material ou função de dispositivo,
digite parte do nome e clique no resultado. Somente digitar não confirma a
escolha. Para remover uma referência opcional, apague o texto. No Dashboard,
o botão **Detecção automática** volta à sessão escolhida automaticamente.
Os seletores de tanques respeitam a planta e a tubulação oferece funções de
atuadores. Status, tipos e demais opções fixas continuam nas caixas de seleção.
As opções pesquisadas devem ser legíveis nos temas claro e escuro.

### Encontrar um painel recém-criado

Depois de criar um painel no workspace, use a busca de dashboards para
encontrá-lo pelo nome e clique no resultado. As opções são carregadas durante
a busca. No workspace, são painéis da planta; na tela completa de Dashboard,
também é possível escolher painéis de outras plantas.

## Registrar envase na sessão da planta

Abra o lote na aba Sessões, inclusive se ele for antigo. Em Preparar envase,
selecione o produto, informe os litros e, se desejar, data e tipo do envase.
Consulte a prévia e confira componentes, unidades, custos e avisos.

Clique em **Registrar envase deste lote**. O modal informa se também serão
consumidos ingredientes ainda não confirmados. Cancelar o modal não grava
nada. Confirmar registra o envase e as baixas de estoque na mesma operação,
retornando à sessão escolhida. Ingredientes já confirmados e seu custo
registrado são preservados. Pendências precisam ser resolvidas primeiro.

Se a resposta se perder, tente novamente com a mesma confirmação exibida.
Essa repetição recupera o mesmo envase, sem outra baixa. Consultar uma nova
prévia inicia outro registro e permite um envase adicional. A prévia não
reserva estoque: composição e custos são conferidos no registro.

Para estornar, use o detalhe de envase existente. A integração do estorno
dentro da sessão e a consolidação da precificação são próximas etapas.


### Envase: detalhes e estorno no lote (2B)

Na aba Sessões, clique no número de um envase para consultar seus dados,
embalagens e custos registrados na confirmação. Os detalhes permanecem no
workspace e mostram também envases cancelados. “Fechar detalhes” mantém o
mesmo lote selecionado, inclusive um lote antigo fora da página atual.

Com permissão de atualização de envase, informe o motivo (até 1000
caracteres) e escolha “Estornar envase”. Confirme no modal do Core. São
criadas entradas correspondentes às saídas de embalagem identificadas;
os ingredientes e seu custo registrado permanecem no lote. O histórico
mostra operador, horário, motivo e vínculos saída → entrada. Repetir o pedido
não devolve novamente. Envase antigo sem snapshot exige reconciliação manual.


### Precificação com o envase selecionado (2C.1)

Nos detalhes de um envase registrado, “Abrir precificação com este envase”
preenche lote/envase e preserva o retorno aos mesmos detalhes. A tela indica
custo registrado versus estimativa. Ingredientes confirmados mantêm o total
congelado e embalagens novas usam o snapshot, sem alterar saldo ou ledger.
O escopo permanece lote inteiro mais embalagens do envase, sem rateio por
volume/unidade nesta entrega. Envases cancelados não participam de novos
cálculos, mas seu histórico de precificação não é apagado.

## Precificação por envase e unidade (2C.2)

Abra a precificação pelo detalhe do envase na aba Sessões. Ingredientes
recebem a fração litros do envase / soma dos litros dos envases registrados
e não apagados do lote. Cancelados não participam. Embalagens são apenas
as do envase escolhido. A tela informa litros, percentual e custo total
do lote usado como base; quantidades de ingredientes continuam sendo da
receita completa e o custo aplicado é proporcional.

Custo por unidade = subtotal / unidades do envase. Preço por unidade =
total após lucro/impostos / unidades. Preço por litro = total / litros do
envase. As fórmulas de lucro e impostos existentes foram preservadas.
As unidades não são arredondadas para inteiro. Sem envase não se calcula
preço unitário. Volume ausente/inválido em qualquer envase participante
bloqueia o rateio, exigindo conferir o histórico.

Novos registros guardam volume por unidade e unidades geradas. Alterar
o cadastro do produto depois não altera essa base. Para envases antigos,
a tela identifica unidades estimadas pelo volume atual do produto ou
preço unitário indisponível. Não se deduz volume pelo nome do material,
pacote ou unidade PCT. Custos registrados e estimados mantêm indicação
separada; estimativas incompletas não se tornam custos confirmados.

Calcular e Salvar congela a base do rateio e valores unitários. Um novo
envase ou estorno altera novos cálculos, sem reescrever cálculos salvos.
Vincular posteriormente um cálculo do lote a um envase mantém sua base
original; faça novo cálculo com o envase selecionado para aplicar rateio.
Cálculos antigos sem snapshot permanecem históricos, sem reconstrução.
Simular e consultar não movimentam estoque.

## Fundo e painel padrão no workspace (3A.1)

Na aba **Dashboard**, escolha o painel e abra **Configurar layouts**.
O formulário **Salvar fundo e padrão** permite escolher cor hexadecimal
(#RGB, #RRGGBB ou #RRGGBBAA) e imagem de fundo por URL HTTP/HTTPS ou caminho
iniciado por /. Deixar a imagem vazia remove o fundo ilustrado. A cor fica
atrás da imagem; use fundo que mantenha as leituras visíveis. Imagens
externas dependem da disponibilidade do servidor de origem. Não há upload
ou biblioteca de imagens neste incremento.

Marque **Painel padrão desta planta** para abrir esse painel ao entrar na
aba sem seleção explícita. Os demais painéis não apagados desta planta
deixam de ser padrão; outras plantas ficam intactas. Se nenhum for padrão,
abre o primeiro cadastrado. O atalho global de dashboards continua seguindo
a seleção global existente. Ao salvar, o painel editado permanece aberto.

A imagem aparece no workspace e na visualização própria, atrás dos widgets
e da tubulação. Nome/dimensões continuam no formulário **Salvar painel**;
o Modo Edição continua cuidando dos elementos e conexões. Configurações
de fundo não alteram widgets, controles, sessão ou estoque. Alterações
exigem permissão de atualização de layouts. Standby e manutenção por
lixeira/restauração ainda não foram incorporados neste formulário.
