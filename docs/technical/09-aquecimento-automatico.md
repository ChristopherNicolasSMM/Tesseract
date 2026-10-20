# Fonte automática protegida — implementação e validação

## Responsabilidades

BrewStation configura fontes no JSON existente do tanque e autoriza somente após
uma ação explícita com permissão `brew_sessions.update`. Device Manager publica
comandos estruturados sem modificar o cache observado. Bridge é dono único do GPIO
protegido e avalia temperatura/demanda local. O corte externo de chama e o rearme
após essa falha pertencem ao circuito independente, sem retorno ao software.

[Contrato Bridge v1](https://github.com/ChristopherNicolasSMM/Tesseract-Device-Bridge/blob/main/docs/technical/09-fonte-automatica.md).
[Manual operacional](../manual/09-aquecimento-automatico.md).

## Autorização e ciclo de vida

- Configuração continua com controle otimista de versão e bloqueio durante sessão
  ativa/pausada. Modo automático exige função de atuador mapeada ao tanque.
- Uma única sessão ativa; processo exige etapa ativa do tanque. HLT/sparge usa seu
  alvo planejado. Troca de sessão, etapa, alvo, versão de configuração ou boot cancela.
- Sensor/função e temperatura da fonte precisam coincidir com os do tanque.
  Auxiliar também exige controlador PID local selecionado, mesmo alvo, sem override.
- Recepção tipada rejeita versão inválida, identidade divergente, atraso >5 s,
  futuro >2 s, mensagem retida, repetição e ordem inválida. Comandos usam boot/token
  atuais e sequência crescente; renovação não é habilitação.
- Autorizações residem em memória de `app.extensions`. O receptor MQTT renova
  somente a partir de estado válido da fonte; ler dashboard não renova nem aciona.
  Reinício não restaura autorização. HTTP/MQTT exigem mesmo processo nesta versão.
- OFF usa envelope genérico compatível também com dispositivos/Bridges legados;
  interrompe a renovação mesmo quando não há conexão. Não confirma desligamento:
  expirado o prazo, Bridge executa OFF no próximo ciclo, enquanto continua vivo.
- Habilitar com MQTT indisponível falha sem registrar autorização. Divergência ou
  erro de renovação remove autorização e tenta OFF; não rearma automaticamente.
- As respostas HTTP são confirmações de envio, nunca confirmação de chama/válvula.
  Tentativas de habilitar/parar identificam operador e fonte no log do servidor.

## Ensaios automatizados

`tests/test_automatic_heating.py` cobre validação do contrato, expiração/frescor,
repetição, retenção, escopo/login, habilitar/renovar/parar, pausa, mudança de alvo,
boot, sensor/controlador divergentes, falha de rede e saída OFF compatível sem
alterar observações. Fixture comum é processada pelo adaptador MQTT real do Core.
Os testes JS verificam permissões, comandos explícitos e ausência de renovação
por renderização, além da telemetria lógica e dos modos manuais existentes.

A integração adicional gerou autorização com `_send` do Core, entregou ao runtime
real do Bridge com GPIO simulado e verificou ON após condições sustentadas, seguido
de OFF térmico. Não utilizou broker de rede nem acionou equipamento físico.

## Resultado da validação

- Bridge: suíte completa, **511 testes Python aprovados**.
- Core: regressão ampliada, **288 testes aprovados**; suíte final de automação,
  **25 testes aprovados**, com sobreposição de 23 testes entre esses grupos.
- JavaScript: **19 testes aprovados**.
- Configuração final/aquecimento: **43 testes aprovados** em verificação focada,
  também sobrepostos aos grupos acima.
- Três avisos preexistentes `LegacyAPIWarning` de `Query.get()` nos testes antigos
  de importação de Bridge; nenhum teste falhou.
- Fixture comum e integração por mensagens nos dois sentidos verificadas sem rede.

Não foi executada a suíte inteira de todos os addons do Core, nem ensaio com broker,
hardware GLP, Windows ou Raspberry Pi. Sem nova migração ou dependência de produção.
