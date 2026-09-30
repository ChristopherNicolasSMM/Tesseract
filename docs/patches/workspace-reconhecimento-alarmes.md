# Reconhecimento de alarmes na aba Sessões

O histórico de alarmes ganha filtro Todos/Pendentes/Reconhecidos, seletor
`form-select` padrão, contador de pendências do lote e ação Reconhecer alarme.
O filtro preserva a sessão, a busca e a página de registros e reinicia apenas
a página de alarmes. A paginação dos alarmes mantém o filtro selecionado.

A ação exige `brew_session_alarms.update` e usa o modal padrão do Core.
A rota verifica que o alarme pertence à sessão e à planta informadas, e
que os três registros estão fora da lixeira. O usuário do reconhecimento
vem da sessão autenticada; valores enviados pelo formulário não podem
substituir usuário, data, severidade ou mensagem.

O serviço manual `session_alarm_actions.py` registra usuário/data e cria
um log da sessão na mesma transação. A atualização só ocorre se o alarme
ainda não estiver reconhecido; repetir a chamada preserva o primeiro
operador e horário e não cria outro log. Falha ao gravar desfaz tanto o
reconhecimento quanto seu log.

Reconhecer significa registrar que o operador viu o alarme. Não muda timers,
etapas, status da sessão, atuadores ou estoque. O runtime já exclui alarmes
reconhecidos da lista de alarmes disparados no snapshot; essa regra permanece.
O histórico da sessão continua permitindo consultar os reconhecidos.

Rota nova:
`POST /brewstation/plant-workspace/<ID_PLANTA>/sessions/<ID_SESSAO>/alarms/<ID_ALARME>/acknowledge`

O novo parâmetro de consulta é `alarm_state` (`pending`, `acknowledged` ou
vazio). Nenhuma migration ou alteração de menu é necessária. Não foram
editados controllers/services gerados pelo CrudGen. O cadastro avançado
mantém seu comportamento existente; a ação no workspace é o fluxo recomendado
para registrar reconhecimento com rastreabilidade.

## Verificação

Abrir `http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions`.
Selecionar uma sessão com alarmes. Filtrar pendentes, reconhecer um alarme
e conferir a redução do contador. Filtrar reconhecidos e abrir seus detalhes;
o histórico de registros deve conter o reconhecimento. Cancelar o modal
deve manter o estado. Conferir a paginação com mais de 20 alarmes.

```shell
pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_feature_envase.py
```

Os testes cobrem operador autenticado, idempotência, isolamento entre
plantas/sessões, lixeira, permissão, rollback e paginação filtrada. Sintaxe
Python/JavaScript e aplicação do patch foram verificadas neste ambiente;
pytest e revisão visual precisam rodar no ambiente do projeto.
