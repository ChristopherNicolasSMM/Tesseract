# Aquecimento, HLT e água de lavagem — entrega 1

## Atualização

Após atualizar o repositório, com o ambiente virtual ativado, execute na raiz:

```sh
python run.py db upgrade
```

A revisão `b04e7c98d216` acrescenta configuração e versão ao tanque, preservando
os registros existentes. O comando é o mesmo no Windows e no Linux/Raspberry Pi.
Esta entrega não exige atualização do Tesseract Device Bridge.

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
   participação, modo manual ou solicitação futura, disponibilidade e potência nominal
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
PID nem potência aplicada. O painel informa demanda indisponível e funcionamento
sem confirmação enquanto não houver telemetria específica.

## Limites desta entrega e próximas etapas

O widget não envia comandos, não abre a solenoide, não acende o fogareiro e não
executa transferência de água. A opção de solicitação é reservada para etapa futura;
ainda não gera pedidos ao operador. O fogareiro GLP existente, com chama piloto
sem supervisão de chama, permanece representado como operação manual.

Sensores de gás, chama, nível, fluxo e sobretemperatura independente estão previstos;
não são considerados presentes nem confirmados por este cadastro. Regras como
“demanda acima de X%”, histerese e solicitações ao operador são a entrega 2.
Telemetria e arbitragem com o controlador local são a entrega 3. O HLT desta etapa
é recipiente aberto de água quente; não envolve vapor ou pressurização.

Os widgets e acionamentos legados continuam disponíveis. Cadastrar uma fonte aqui
não bloqueia nem altera automaticamente regras/acionamentos que já existiam.
