const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('addons/addon_brewstation/features/feature_mash_control/templates/dashboards/_scripts.html', 'utf8');
function setup(canRespondHeating = true) {
  const body = {children: [], replaceChildren() {this.children = [];}, appendChild(node) {this.children.push(node);}};
  const link = {};
  const el = {querySelector: selector => selector === '.db-heating-body' ? body : link};
  const calls = [];
  const context = {document: {createElement: () => ({listeners: {}, addEventListener(type, fn) {this.listeners[type] = fn;}})}, plantId: 42, canRespondHeating, fmtValue: value => String(value),
    fetch: (url, options) => {calls.push({url, options}); return Promise.resolve({json: () => Promise.resolve({ok: true, message: 'Registrado'})});},
    window: {__tesseractToast: {show() {}}}};
  vm.runInNewContext(script.slice(script.indexOf('  function renderHeating('), script.indexOf('  function renderWidget(')), context);
  return {body, link, calls, render: data => context.renderHeating(el, data)};
}
test('renders HLT/sparge plans and unconfirmed source states as text, no HTML commands', () => {
  const ui = setup();
  ui.render({vessel_id: 7, vessel_name: '<img src=x onerror=attack()>', usage_label: 'Sparge', temperature: null,
    sensor_label: null, sensor_status: 'sem leitura', target_temp: 76, target_origin: 'planejado', planned_volume_liters: 25,
    sources: [{name: '<script>attack()</script>', type_label: 'Gás', role_label: 'Auxiliar', mode_label: 'Manual', enabled: true,
      state: 'sem confirmação de funcionamento', nominal_power_kw: 8}], power_status: 'indisponível', rule_status: 'futuro'});
  const text = ui.body.children.map(node => node.textContent).join('\n');
  assert.match(text, /Temperatura: —/);
  assert.match(text, /25 L \(não medido\)/);
  assert.match(text, /sem confirmação de funcionamento/);
  assert.match(text, /<script>attack/);
  assert.ok(ui.body.children.every(node => !Object.hasOwn(node, 'innerHTML')));
  assert.match(ui.link.href, /42\?tab=plant#heating-7$/);
  ui.render({error: 'Tanque inválido'});
  assert.equal(ui.body.children.length, 1);
  assert.equal(ui.body.children[0].textContent, 'Tanque inválido');
});

test('operator responses are explicit, permission gated and contain no actuator value', async () => {
  const data = {vessel_id: 7, vessel_name: 'HLT', usage_label: 'Sparge', temperature: 60,
    target_temp: 65, planned_volume_liters: null, sources: [], power_status: 'observado', rule_status: 'Condição atendida',
    automatic_demand_percent: 95,
    request_rule: {requests: [{source_name: 'GLP manual', status: 'requested', status_label: 'Pendente',
      created_at: '2026-10-20', currently_valid: true, can_respond: true, can_complete: false, response_url: '/operator-response'}]}};
  const ui = setup(); ui.render(data);
  assert.equal(ui.calls.length, 0);
  const buttons = ui.body.children.filter(node => node.type === 'button');
  assert.equal(buttons.length, 2);
  buttons[0].listeners.click(); buttons[0].listeners.click();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/operator-response');
  assert.deepEqual(JSON.parse(ui.calls[0].options.body), {action: 'acknowledge'});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(buttons[0].disabled, false);
  const reader = setup(false); reader.render(data);
  assert.equal(reader.body.children.filter(node => node.type === 'button').length, 0);
  data.request_rule.requests[0].can_respond = false;
  data.request_rule.requests[0].currently_valid = false;
  ui.render(data);
  assert.equal(ui.body.children.filter(node => node.type === 'button').length, 0);
  assert.ok(ui.body.children.some(node => /Revise manualmente/.test(node.textContent)));
});

test('Bridge metrics keep demand, selected duty and current window distinct and hide stale percentages', () => {
  const ui = setup();
  const data = {vessel_id:7,vessel_name:'HLT',usage_label:'Sparge',temperature:60,target_temp:65,
    planned_volume_liters:null,sources:[],rule_status:'Sem condição',power_status:'indisponível',
    controller:{available:true,fresh:true,status:'Telemetria recebida',owner_label:'Receita local',backend:'simulated',
      observed_at:'2026-10-20',demand_percent:95,power_limit_percent:60,automatic_percent:60,selected_percent:60,
      applied_window_percent:100,output_on:true,external_policy:'local_only',fault:null}};
  ui.render(data);
  let text=ui.body.children.map(node=>node.textContent).join('\n');
  assert.match(text,/Demanda calculada: 95% · teto: 60%/);
  assert.match(text,/selecionado: 60%/);
  assert.match(text,/Janela aplicada: 100% · saída lógica GPIO: ON/);
  assert.match(text,/Origem: simulated/);
  assert.match(text,/não mede potência elétrica nem confirma chama/);
  data.controller.fresh=false;data.controller.status='Telemetria antiga';ui.render(data);
  text=ui.body.children.map(node=>node.textContent).join('\n');
  assert.match(text,/Telemetria antiga/);
  assert.doesNotMatch(text,/Janela aplicada: 100%/);
  assert.equal(ui.calls.length,0);
});
