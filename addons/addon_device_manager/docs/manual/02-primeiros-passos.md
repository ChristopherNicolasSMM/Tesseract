# 02 — Primeiros Passos (Dispositivos)

1. Cadastre as Funções que seus dispositivos vão usar (ex.: "Sensor
   de Temperatura", "Atuador de Aquecimento") — defina uma faixa de
   valores aceitável, se fizer sentido pra essa função.
2. Cadastre o Dispositivo (ex.: "Freezer Principal") — se ainda não
   tem o equipamento físico, use "Dispositivo Emulado" no lugar (ver
   `03-funcionalidades.md`).
3. Cadastre um Ator: associe uma porta do dispositivo a uma Função,
   escolhendo se essa porta é um sensor (leitura) ou um atuador
   (comando).

## Ligando um dispositivo real por MQTT (opcional)

Sem isso, os cadastros funcionam normalmente, só não trocam mensagem
de verdade com hardware nenhum. Pra ligar de fato:

1. No `.env` do sistema, defina `MQTT_ENABLED=true` e preencha
   `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT` (endereço do seu broker
   MQTT). `MQTT_USERNAME`/`MQTT_PASSWORD` só se o broker exigir
   autenticação; `MQTT_CLIENT_ID`/`MQTT_TOPIC_PREFIX` têm valor
   padrão, só mude se precisar.
2. Reinicie o sistema — a conexão MQTT só é aberta na subida, com
   essa variável ligada.
3. Em cada Ator que vai se comunicar de verdade, preencha o campo
   "Config Json" com o tópico MQTT daquela porta (ver
   `03-funcionalidades.md`, seção Atores) — sem isso, o sistema usa um
   tópico padrão baseado no identificador interno do ator, o que
   funciona, mas fica menos legível.
