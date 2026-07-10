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

Layouts visuais com widgets — monte um painel próprio arrastando
elementos que mostram leituras/controles em tempo real dos seus
dispositivos vinculados.
