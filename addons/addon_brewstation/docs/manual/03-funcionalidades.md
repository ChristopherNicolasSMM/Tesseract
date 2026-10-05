# 03 — Funcionalidades (BrewStation)

Ver o manual de cada área:
- **Banco de Levedura** — `features/feature_yeast_bank/docs/manual/03-funcionalidades.md`
- **Controle de Mostura (Receitas, Sessões, Automação)** — `features/feature_mash_control/docs/manual/03-funcionalidades.md`
- **Ingredientes** — `features/feature_ingredientes/docs/manual/03-funcionalidades.md`
- **Envase** — `features/feature_envase/docs/manual/03-funcionalidades.md`
- **Integração BrewFather** — `features/feature_brew_father/docs/manual/03-funcionalidades.md`

Dispositivos IoT (sensores/atuadores) e Estoque de materiais vivem em
áreas próprias do sistema — não são parte do BrewStation, mas são
usados por ele.

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


### Continuidade de envase no lote

Na aba Sessões do workspace, o registro de envase (2A.2) agora é acompanhado
por detalhes e estorno (2B). A abertura dos detalhes é somente leitura e usa
custos/saídas registrados. O estorno exige motivo e confirmação, devolve
embalagens pelo estoque central e preserva ingredientes/custo do lote.
A precificação continua em sua tela própria e seu alinhamento aos snapshots
permanece uma etapa posterior.


### Custos na precificação (2C.1)

O total confirmado de ingredientes e o snapshot de embalagem são usados na
precificação. Estimativas anteriores à confirmação/legadas ficam identificadas.
O detalhe de envase do workspace abre a precificação com lote/envase e
retorno contextual. O rateio por envase/unidade permanece pendente; esta
entrega não registra envase nem movimenta estoque ao simular/salvar cálculo.

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

## Lixeira e restauração de painéis (3B)

Na aba **Dashboard**, abra **Configurar layouts**. **Enviar painel à lixeira**
pede confirmação e retira somente o painel selecionado da lista disponível.
Widgets e configurações permanecem guardados; sessões e controles da planta
continuam funcionando. O workspace abre o padrão restante ou o primeiro
painel disponível. Se era o último, aparece a tela de criação e a lixeira.

Em **Lixeira de painéis**, use **Restaurar painel** e confirme. A lixeira
mostra apenas painéis da planta atual, em páginas de 20 itens. A restauração
abre o painel recuperado. Se ele era padrão, mas já existe outro padrão
ativo na planta, volta sem substituir a escolha atual; use **Salvar fundo
e padrão** para escolher explicitamente depois. Sem outro padrão, conserva
a marcação original. Nome, dimensões, fundo, widgets e tubulação permanecem
como estavam. Widgets previamente removidos individualmente mantêm esse
estado; restaurar o painel não restaura automaticamente cada widget.

Enviar à lixeira e restaurar exigem permissões próprias. Usuário que pode
consultar layouts vê a lista; sem permissão de restauração, não recebe o
botão. Exclusão permanente continua no cadastro completo e não está neste
fluxo. Uma URL que aponta explicitamente para painel apagado/externo retorna
erro; as ações locais é que encaminham para a seleção disponível.


### Automação no workspace — filtros e histórico (4B.1)

Em `/brewstation/plant-workspace/<ID_PLANTA>`, abra Automação. Busque por
nome ou pelo combo de regra; filtre status e vínculo global/sessão.
Os mesmos filtros limitam os disparos; Resultado filtra somente o histórico.
Regras e disparos têm páginas independentes de 20 itens. Filtrar/limpar
reinicia as páginas; Anterior/Próxima conserva os filtros e a outra página.
Limpe o combo para consultar todas as regras permitidas da planta e globais.

Histórico exige `automation_rule_logs.list`; criar e consultar detalhes
exigem as permissões respectivas. Cadastro avançado continua acessível.
Regras vinculadas só disparam quando a sessão está ativa, não apagada e
com planta disponível. Pausar bloqueia novos disparos, sem desligar atuadores. Regras globais/histórico são compartilhados
entre plantas; logs não identificam a planta do disparo. Consultar ou
filtrar não aciona dispositivos nem altera sessões/estoque.

Etapas anteriores de custos/rateio e manutenção de painéis foram validadas
pelo usuário em 05/10/2026. Standby continua pendente.


### Automação vinculada à sessão — guarda de execução (4B.2a)

Regras globais continuam avaliadas por sensor/condição/cooldown. Regras com
sessão vinculada exigem status interno `active`, sessão não apagada e planta
existente/não apagada. Rascunho, pausa, conclusão e aborto impedem novos
acionamentos. Vínculos incompletos/órfãos também são bloqueados.

Retomar permite avaliar as próximas leituras, respeitando o cooldown anterior;
não reproduz leituras recebidas durante a pausa. Bloqueio não registra disparo,
não aumenta contador e não muda último disparo, timers ou estoque. Pausar não
é um comando de desligamento; atuadores já ligados permanecem em seu estado.
Funções configuradas continuam resolvidas por nome; esta guarda não identifica
a planta física do sensor nem valida mapeamentos. Criação/edição básicas estão integradas; o cadastro avançado continua acessível.


### Automação — isolamento por configuração (4B.2b)

Regras vinculadas exigem que sensor e atuador estejam mapeados somente na
planta da sessão, por mapeamentos/tanques/plantas não apagados. Cada função
precisa resolver exatamente um ator não apagado, com função disponível.
Ausência, compartilhamento entre plantas ou múltiplos atores bloqueiam novos
disparos sem gravar contador/horário/log de disparo. Regras globais preservam
o comportamento anterior e continuam compartilhadas.

Antes de operar, confira os mapeamentos na aba Planta. Configurações antigas
sem mapeamentos exclusivos deixam de disparar regras vinculadas. Isso não
altera dados nem desliga atuadores. O isolamento é pela configuração: o evento
continua contendo nome/valor, sem identificar planta física ou autenticar origem.
Logs também não passam a armazenar origem. Não há migration.


### Automação e sessões — manutenção integrada (4B.3 / 4B.4 / 4C)

Em Automação, expanda Criar regra. As funções de sensor/atuador e a sessão são
combos pesquisáveis; sessão vazia cria regra global, disponível em todas as
plantas. Condição e ação usam opções fixas. Definir valor exige valor numérico;
intervalo mínimo entre disparos é dado em segundos. Métrica é informativa:
o motor recebe o valor publicado pela função. Criar não aciona equipamentos.

Selecione Editar na linha da regra. Desative antes de editar. Salvar preserva
contador, último disparo e histórico; a regra continua inativa. Ativar é ação
separada e não dispara imediatamente: permite avaliar próximas leituras.
Regras vinculadas precisam de mapeamentos exclusivos e ator único por função;
execução também depende da sessão ativa e planta disponível. Alterações de
regras globais afetam todas as plantas. Desativar/mover para lixeira não
desliga atuadores. Lixeira tem 20 itens por página; restaurar preserva histórico
e mantém inativa. Exclusão permanente continua no cadastro avançado.

Em Sessões, escolha inclusive um lote antigo. Operações disponíveis conforme
status/permissão: concluir e avançar etapa, voltar etapa, pausar/retomar,
concluir sessão e ressincronizar etapas da receita. Voltar reinicia a etapa
anterior; não recupera seu tempo original. Ressincronizar atualiza pendentes e
preserva completas, usando o serviço existente. Concluir marca completed pelo
runtime; não registra envase ou confirma ingredientes. Não é desligamento.

Nos detalhes de uma etapa pendente/ativa de sessão aberta, ajuste Nome,
Temperatura alvo ou Permanência (s). Temperatura vazia remove o alvo. O ajuste
registra operador/antes/depois no histórico do lote; não muda a receita,
rampa, status, confirmação de ingredientes ou custo congelado.

Ações usam confirmação do Core e mensagens do projeto. Se status/etapa mudou,
recarregue a aba antes de reenviar controles. Timers/listeners do Dashboard
continuam limpos pela navegação existente. Não há migration.


## Navegação consolidada e cadastros avançados

Use **Abrir planta**, **Abrir fluxo de sessões** ou **Abrir fluxo de automação**
para escolher a planta e trabalhar nas abas. O novo acesso de automação abre
regras, edição e manutenção no mesmo processo, conforme suas permissões.

**Regras de Automação**, **Layouts de Dashboard** e
**Histórico de Regras** continuam disponíveis para operações que
não cabem no contexto de uma planta. Tanques, mapeamentos, sessões, passos,
registros e alarmes também mantêm seus cadastros completos, incluindo a
manutenção ainda não incorporada às abas. Os cadastros de água e de-para
compartilhado continuam separados do saneamento local da receita.

Ocultar atalhos redundantes não apaga registros ou telas. A configuração do
menu pode ser revertida na administração. Standby dos painéis ainda depende
de implementação; a existência do campo no cadastro não garante seu funcionamento.

As descrições dos itens do menu aparecem como dicas ao passar o mouse.
Os nomes permanecem curtos; a dica informa o uso avançado ou global.
