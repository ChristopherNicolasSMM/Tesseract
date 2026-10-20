# Mash Control — contrato de aquecimento (entrega 1)

Plano e etapas: [expansão](../patches/mash-control-aquecimento-expansao.md).
Operação: [manual](../manual/08-aquecimento-hlt-sparge.md).

## Persistência e limites

`BrewPlantVessel.heating_config_json` armazena o perfil por tanque; `heating_version`
é incrementada por comparação e troca. Campos são somente leitura no CRUD genérico,
para que a escrita passe por `heating_configuration_service` e suas validações.
Não há segundo cadastro de dispositivos nem novas tabelas de atuadores.

Perfil: `usage` (`process|hlt|sparge`), `primary_sensor_mapping_id`, `target_temp`
(0–110 °C, opcional), `planned_volume_liters` (0–100000 L, opcional) e `sources`.
Fonte: UUID local, nome até 100 caracteres, `type` (`electric|gas|other`),
`role` (`primary|auxiliary`), `mode` (`manual|advisory`), `enabled`, potência nominal
opcional 0–10000 kW e `device_function_name` opcional. `advisory` é reservado;
nesta versão não dispara solicitações. Máximo de vinte fontes e uma principal.
Limites numéricos são validações de armazenamento, não especificações de equipamento.

O sensor precisa ser mapeamento de temperatura numérico válido do mesmo tanque.
A função da fonte precisa ser atuador/híbrido já mapeado no tanque e não pode ser
repetida entre suas fontes. Referências a Device Manager usam o serviço público
`device_function_lookup` e o nome da função; não há FK/objeto ORM entre addons.
Valores não finitos e seleções inválidas são rejeitados.

A escrita serializa pela planta, rejeita sessões ativas/pausadas e exige a versão
lida pela tela. Conflitos retornam 409 com rollback. Alterações de configuração
são feitas fora da sessão; não foi introduzido snapshot de configuração da sessão.

## Rotas e widget

`POST /brewstation/plant-workspace/<plant>/vessels/<vessel>/heating/<action>`:
`profile`, `source`, `remove-source`. Login e `brew_plant_vessels.update` obrigatórios;
planta/tanque são verificados no servidor. JSON usa `expected_version`; edição e
remoção de fonte usam `source_id`. Erros de validação retornam 400, ausência 404,
conflito 409. Exceções inesperadas desfazem a transação e registram o erro.

O widget `heating` reutiliza criação/edição/snapshot do dashboard, ligado por
`vessel_id` e limitado à planta do layout. O endpoint de acionamento rejeita esse
tipo mesmo se uma função for injetada no registro. Configurar e consultar não chama
`device_service.set_value`. As permissões existentes de dashboard continuam válidas.

Snapshot publica temperatura e origem do alvo; potência/demanda automática `null`,
`can_actuate=false` e proteções sem confirmação. O valor do sensor é o último cache
numérico finito, sem garantia de idade. Não se usa cache de comando para afirmar
funcionamento de fonte. No tipo `process`, uma etapa ativa da sessão da mesma planta
pode substituir o alvo planejado. HLT/sparge preservam o alvo do perfil.
O widget Tanque também passa a usar a seleção principal explícita/canônica/única.

Templates escapam entradas e o renderer usa `textContent`. Combos seguem o componente
de referência existente e são restritos ao tanque. Configuração fica na aba Planta,
sem novos menus de CRUD. `heating_workspace.py` usa descoberta padrão de blueprints.

## Migração e validação

Revisão aditiva `b04e7c98d216`, anterior `a93dbe671ca5`, acrescenta JSON anulável e
versão inteira não anulável com default 0. Verifica colunas já criadas compatíveis.
Downgrade é bloqueado se houver configuração/versão utilizada, evitando perda
silenciosa. Caminhos de código não dependem de separadores do SO; os testes de
migração usam `pathlib`. Validação local usa SQLite/Linux; Windows e Raspberry Pi
precisam da validação do operador nos respectivos ambientes.

```sh
python -m pytest tests/test_heating_configuration.py tests/test_dashboard_runtime.py tests/test_plant_workspace.py -q
node --test tests/js/*.cjs
```

Testes cobrem ausência de comandos, sensor principal, limites numéricos, fontes,
isolamento de plantas, RBAC, concorrência por versão, sessões ativas, CRUD genérico,
rotas, renderização HTML, renderer JS e preservação/bloqueio de perda na migração.
