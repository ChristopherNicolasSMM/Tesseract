# 03 — Funcionalidades (Controle de Mostura)

## Receitas

Cadastro de receitas de brassagem — etapas de mostura, perfil de
água, etapas de fermentação e os ingredientes usados (ligados a um
Material do Estoque). Cada alteração salva gera uma nova versão; o
histórico de versões fica disponível para consulta/comparação.

## Plantas e Vasilhames

Sua estrutura física — panela de mostura, caldeira, fermentador — e o
mapeamento de qual sensor/atuador (Função de Dispositivo) cada
vasilhame usa para cada papel (leitura de temperatura, controle de
aquecimento, etc.).

## Sessões de Brassagem

Acompanhamento de uma brassagem em andamento: etapas, logs (incluindo
os gerados automaticamente pela automação), e alarmes (que podem ser
confirmados/reconhecidos por um usuário).

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
| Tanque | Desenho de vasilhame (panela, fermentador) com nível de líquido |
| Etapa | Card com a etapa atual da brassagem — ver seção própria abaixo |
| Alarme | Lista de alertas já disparados e agendados |
| Texto | Texto livre — título, aviso, instrução |
| Imagem | Imagem sua (logo, foto do equipamento, diagrama) |

Arraste o ícone da paleta pra qualquer lugar do painel. O elemento
aparece **sem estar ligado a nada ainda** — um selo cinza "Não
configurado" avisa disso. Clique nele (sem arrastar) pra abrir o
**painel de configuração** do lado direito: escolha ali o
sensor/atuador/vasilhame que ele deve mostrar, ajuste legenda, cor,
faixa de valores, etc. O selo some assim que salvar. O mesmo painel
também tem o botão "Remover", pra tirar o elemento do painel.

Pra mover um elemento já colocado, arraste-o pelo meio. Pra
redimensionar, arraste o cantinho inferior direito. Saia do Modo
Edição quando terminar — a tela volta a só mostrar os valores, sem as
alças de edição.

### Tubulação entre vasilhames

Com Planta vinculada ao Dashboard, o botão "Tubulação" abre um editor
onde você liga um vasilhame a outro (ex.: panela de mostura → caldeira
de fervura), escolhendo a bomba/válvula que controla esse fluxo — a
linha acende quando o atuador está ligado.

A linha nasce reta, mas você pode dar forma a ela: com a tubulação
selecionada (clique nela em Modo Edição), arraste o meio de qualquer
trecho pra criar uma curva, arraste os pontos verdes nas pontas pra
mudar onde ela sai/entra do vasilhame, e selecione um ponto de curva +
tecla Delete pra removê-lo. Isso é útil principalmente pra
**recirculação** (um vasilhame ligado a ele mesmo) — nesse caso a
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
