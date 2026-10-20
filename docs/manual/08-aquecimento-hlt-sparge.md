# Aquecimento, HLT e água de lavagem — entregas 1 e 2

## Atualização

Após atualizar o repositório, com o ambiente virtual ativado, execute na raiz:

```sh
python run.py db upgrade
```

A revisão `b04e7c98d216` acrescenta configuração e versão ao tanque, preservando
os registros existentes. O comando é o mesmo no Windows e no Linux/Raspberry Pi.
A entrega 2 acrescenta a revisão `c18f7d23a904`, com estado do avaliador e histórico
de solicitações. Nenhuma das duas exige atualização do Tesseract Device Bridge.

## Configurar os equipamentos

1. Abra o workspace da planta, aba **Planta**. Cadastre ou selecione o tanque.
   Para água quente, use o tipo já existente **hlt**.
2. Cadastre os mapeamentos dos sensores e atuadores do tanque como habitualmente.
3. Abra **Aquecimento e água de lavagem**, no tanque desejado. Selecione o uso:
   processo/etapa, água quente (HLT), ou água para lavagem (sparge).
4. Escolha o sensor principal de temperatura entre os mapeamentos deste tanque.
   Sem seleção explícita, será usado o sensor canônico `sensor_temp` ou o único
   sensor de temperatura válido. Se houver vários sem canônico, selecione um.
5. Informe opcionalmente alvo de temperatura e volume planejado. O volume é
   planejamento; não indica nível medido, vazão ou água efetivamente transferida.
6. Cadastre as fontes principais/auxiliares. Informe nome, tipo (elétrico/gás/outro),
   participação, modo manual ou solicitação ao operador, disponibilidade e potência nominal
   opcional em kW. No máximo uma fonte principal e vinte fontes por tanque.
   A associação opcional de função aceita somente atuadores já mapeados neste tanque.

Alterações exigem a permissão `brew_plant_vessels.update`. Encerre sessões ativas
ou pausadas antes de alterar as configurações. Se outra pessoa salvar primeiro,
recarregue e confira os dados antes de tentar novamente.

## Novo widget no dashboard

No editor do dashboard, arraste **Aquecimento** e selecione o tanque da mesma
planta no painel lateral. Redimensione se desejar. Podem existir vários widgets,
por exemplo um para mostura e outro para HLT/sparge.

O widget mostra o último valor numérico registrado do sensor selecionado, alvo,
volume planejado e fontes cadastradas. No uso processo, uma etapa ativa da sessão
selecionada pode fornecer o alvo. Em HLT/sparge, o alvo vem da preparação do tanque.
O link **Configurar fontes e sensores na Planta** abre a configuração correspondente.

A leitura não comprova atualidade do sensor. A potência nominal em kW não é demanda
PID nem potência aplicada. O painel só mostra demanda quando a regra usa um sensor
percentual com observação recebida válida. Funcionamento das fontes continua sem
confirmação física.

## Configurar a regra de solicitação

Antes de iniciar a sessão, na aba **Planta**, abra o tanque e cadastre uma fonte
com modo **Solicitação ao operador** e disponibilidade marcada. Em **Regra de
solicitação ao operador**, selecione essa fonte, ajuste os limites e habilite a regra.
A fonte pode ser principal ou auxiliar. Cada tanque possui uma regra nesta entrega.

| Parâmetro | Padrão de fábrica |
|---|---:|
| Regra habilitada | Não |
| Exigir demanda percentual | Sim |
| Demanda acima de | 80% |
| Histerese de demanda | 10 pontos percentuais |
| Distância mínima abaixo do alvo | 2 °C |
| Histerese de temperatura | 0,5 °C |
| Tempo mínimo da condição | 10 s |
| Intervalo mínimo entre pedidos | 60 s |
| Prazo para responder | 120 s |
| Idade máxima da leitura | 15 s |

Exemplo com alvo 65 °C: temperatura de até 63 °C e demanda maior que 80%,
sustentadas pelo tempo mínimo, geram um pedido. Uma vez emitido, a saída ocorre
quando a temperatura chega a 63,5 °C ou a demanda cai a 70% ou menos. Isso encerra
a condição do pedido; o operador deve conferir a fonte manualmente. Não é corte de gás.

O sensor de demanda precisa ser uma função **sensor**, numérica, com unidade `%`
ou `percent`, mapeada no próprio tanque e que represente demanda do controlador.
Um atuador, potência nominal em kW ou comando de potência não substitui essa leitura.
Sem sensor ou observação recente, o widget informa o bloqueio. Para trabalhar apenas
pela distância do alvo, desmarque **Exigir também demanda acima do limite**.

A avaliação acontece no servidor quando chegam observações; não depende do navegador.
Novas leituras comprovam continuidade. Se houver intervalo maior que a idade máxima,
o tempo mínimo recomeça. Exige uma única sessão ativa e não pausada na planta.
No uso processo, precisa existir uma etapa ativa do tanque com alvo válido; em
HLT/sparge, utiliza o alvo planejado do próprio tanque, mesmo durante a mostura.

## Responder no widget

Com permissão `brew_sessions.update`, o widget permite:

- **Registrar ação manual:** declarar que o operador atendeu o pedido; não envia
  comando, não comprova ignição nem funcionamento.
- **Recusar:** registrar que o pedido não será atendido.
- **Concluir atendimento:** encerrar a declaração anteriormente registrada.

Usuário e horário ficam no histórico. O widget mostra os cinco pedidos mais recentes;
a auditoria completa permanece no banco. Depois de recusar, concluir ou expirar,
a condição precisa sair da faixa e voltar para emitir outro pedido. Também é
respeitado o intervalo mínimo entre pedidos. Respostas duplicadas/conflitantes são
rejeitadas. Cada resposta verifica novamente sessão, alvo, fonte e idade das leituras.

Pausa, encerramento, troca de etapa/alvo, dados inválidos ou reinício invalidam
pedidos anteriores. Mensagens de cancelamento exigem revisar manualmente a fonte;
o software não presume que uma fonte manual foi desligada. No painel de uma sessão
histórica, não há ações para responder pedidos da sessão atual.

## Manutenção sem novas leituras

O recebimento de leituras e as ações de sessão fazem a avaliação normal. Sem novos
eventos, o painel e a resposta verificam validade, mas a reconciliação persistida
aguarda um evento ou a tarefa de manutenção. Para reconciliação periódica, habilite
o agendador já existente com `TASK_SCHEDULER_ENABLED=true`, reinicie a aplicação e
cadastre no monitor de tarefas uma chamada Python:

- Target: `brewstation.evaluate_heating_requests`
- Agenda cron: `* * * * *` (uma vez por minuto)

Não é necessário cadastrar essa tarefa para pedidos por observações. Ela não envia
comandos, não substitui dispositivos de proteção e pode cancelar pedidos antigos.
O prazo exato sempre é conferido ao responder, mesmo entre execuções da tarefa.

## Limites e próximas etapas

O widget não envia comandos, não abre a solenoide, não acende o fogareiro e não
executa transferência de água. O fogareiro GLP existente com chama piloto sem
supervisão permanece sob operação manual do responsável.

Sensores de gás, chama, nível, fluxo e sobretemperatura independente estão previstos;
não são considerados presentes ou confirmados por este cadastro. A entrega 3 trata
telemetria específica e arbitragem com o controlador local antes de qualquer nova
atuação física. O HLT desta etapa é recipiente aberto de água quente; não envolve
vapor ou pressurização.

Os widgets e acionamentos legados continuam disponíveis. Cadastrar uma fonte ou
regra de solicitação não altera regras/acionamentos legados automaticamente.
