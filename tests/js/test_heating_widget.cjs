const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('addons/addon_brewstation/features/feature_mash_control/templates/dashboards/_scripts.html', 'utf8');
function setup() {
  const body = {children: [], replaceChildren() {this.children = [];}, appendChild(node) {this.children.push(node);}};
  const link = {};
  const el = {querySelector: selector => selector === '.db-heating-body' ? body : link};
  const context = {document: {createElement: () => ({})}, plantId: 42, fmtValue: value => String(value)};
  vm.runInNewContext(script.slice(script.indexOf('  function renderHeating('), script.indexOf('  function renderWidget(')), context);
  return {body, link, render: data => context.renderHeating(el, data)};
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
