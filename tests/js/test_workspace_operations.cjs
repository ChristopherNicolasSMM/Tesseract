// Confirmação/envio dos novos controles, sem navegador ou banco.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const folder = path.join(__dirname, '../../addons/addon_brewstation/features/feature_mash_control/templates/plant_workspace');

async function verify(template, rootId, selector, dataset, busyKey) {
  const html = fs.readFileSync(path.join(folder, template), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const buttons = [{disabled: false}, {disabled: false}];
  const callbacks = {};
  const root = {
    dataset: {},
    addEventListener: (name, handler) => { callbacks[name] = handler; },
    querySelector: () => ({addEventListener() {}}),
    querySelectorAll: query => query.includes('button') ? buttons : [],
  };
  let resolveConfirmation;
  let submits = 0;
  const messages = [];
  const window = {
    __tesseractConfirm: options => {
      const translations = JSON.parse(fs.readFileSync(path.join(folder, '../../i18n/pt_BR.json'), 'utf8'));
      assert.ok(translations[options.key], 'Chave de confirmação existe no catálogo');
      assert.equal(options.text, undefined, 'Modal usa i18n, não texto direto');
      return new Promise(resolve => { resolveConfirmation = resolve; });
    },
    __workspaceSubmitForm: async () => { submits++; },
    __tesseractToast: {show: message => messages.push(message)},
  };
  vm.runInNewContext(script, {window, document: {getElementById: id => id === rootId ? root : null},
    URLSearchParams, FormData: class {}});
  const form = {dataset, isConnected: true, querySelector: () => buttons[0]};
  const event = {preventDefault() {}, target: {closest: query => query === selector ? form : null}};
  const first = callbacks.submit(event);
  assert.ok(buttons.every(button => button.disabled), 'Bloqueia todos os comandos durante o modal');
  await callbacks.submit(event);
  assert.equal(submits, 0, 'Reenvio durante confirmação não envia');
  resolveConfirmation(false);
  await first;
  assert.ok(buttons.every(button => !button.disabled));
  assert.equal(submits, 0, 'Cancelar não envia');
  assert.equal(root.dataset[busyKey], undefined);

  const confirmed = callbacks.submit(event);
  resolveConfirmation(true);
  await confirmed;
  assert.equal(submits, 1);
  assert.ok(buttons.every(button => !button.disabled));

  const detached = callbacks.submit(event);
  form.isConnected = false;
  resolveConfirmation(true);
  await detached;
  assert.equal(submits, 1, 'Fragmento removido durante modal não envia');
  form.isConnected = true;
  window.__tesseractConfirm = undefined;
  await callbacks.submit(event);
  assert.equal(submits, 1);
  assert.ok(messages.some(message => message.includes('Confirmação indisponível')));
  assert.ok(buttons.every(button => !button.disabled));
}
(async () => {
  await verify('_tab_automation.html', 'pwAutomation', '.pw-automation-mutation',
    {ruleConfirmKey: 'brewstation_mashctrl.workspace.rule_activate_global', ruleName: 'Regra'}, 'mutationBusy');
  await verify('_session_operations.html', 'pwSessionOperations', 'form[data-session-confirm]',
    {sessionConfirm: 'brewstation_mashctrl.workspace.session_toggle_pause'}, 'busy');
  console.log('OK: confirmação, cancelamento, reenvio, fragmento removido e recuperação dos controles');
})().catch(error => { console.error(error); process.exitCode = 1; });
