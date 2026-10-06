const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('addons/addon_brewstation/features/feature_mash_control/templates/plant_workspace/_ingredient_conversion_scripts.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
function fixture() {
  let submit, input, confirms = 0, saves = 0, shown = 0, cleaned = 0, resolveConfirm;
  const factor = {value: '1', addEventListener: (_, cb) => input = cb};
  const output = {}, button = {disabled: false}, messages = [];
  const hidden = [];
  const modal = {classList: {contains: () => true}, addEventListener: (_, cb) => hidden.push(cb)};
  let instance;
  function getOrCreateInstance() {
    if (!instance) instance = {hide: () => { const callbacks = hidden.slice(); hidden.splice(1); callbacks.forEach(cb => cb()); },
      show: () => shown++, dispose: () => instance = null};
    return instance;
  }
  const form = {isConnected: true, dataset: {quantity: '2', base: 'UN', invalidFactor: 'Fator inválido', confirmMissing: 'Sem confirmação'},
    querySelector: s => s.includes('fator_para_base') ? factor : s.includes('preview') ? output : button,
    closest: () => modal, addEventListener: (_, cb) => submit = cb};
  const context = {document: {querySelectorAll: () => [form]}, bootstrap: {Modal: {getOrCreateInstance, getInstance: () => instance}},
    window: {__tabCleanup: () => cleaned++, __tesseractConfirm: () => {confirms++; return new Promise(r => resolveConfirm = r);},
      __workspaceSubmitForm: async () => {saves++; return {ok: true};}, __tesseractToast: {show: (...args) => messages.push(args)}}};
  vm.runInNewContext(script, context);
  return {form, factor, output, button, messages, context, input: () => input(), submit: () => submit({preventDefault() {}}),
    confirm: v => resolveConfirm(v), counts: () => ({confirms, saves, shown, cleaned})};
}
(async () => {
  const f = fixture();
  assert.equal(f.output.textContent, '2 UN');
  f.factor.value = '0,5'; f.input(); assert.equal(f.output.textContent, '1 UN');
  let pending = f.submit(); await Promise.resolve();
  await f.submit(); assert.equal(f.counts().confirms, 1); assert(f.button.disabled);
  f.confirm(true); await pending; assert.equal(f.counts().saves, 1); assert(!f.button.disabled);
  const cancel = fixture(); pending = cancel.submit(); await Promise.resolve(); cancel.confirm(false); await pending;
  assert.equal(cancel.counts().saves, 0); assert.equal(cancel.counts().shown, 1);
  cancel.context.window.__tabCleanup(); assert.equal(cancel.counts().cleaned, 1);
  const detached = fixture(); pending = detached.submit(); await Promise.resolve(); detached.form.isConnected = false; detached.confirm(true); await pending;
  assert.equal(detached.counts().saves, 0); assert.equal(detached.counts().shown, 0);
  const invalid = fixture(); invalid.factor.value = 'Infinity'; invalid.input(); assert.equal(invalid.output.textContent, '—');
  await invalid.submit(); assert.equal(invalid.counts().confirms, 0); assert.equal(invalid.messages[0][0], 'Fator inválido');
  const failure = fixture(); failure.context.window.__workspaceSubmitForm = async () => null;
  pending = failure.submit(); await Promise.resolve(); failure.confirm(true); await pending;
  assert.equal(failure.counts().shown, 1);
  console.log('Conversão: prévia, confirmação, cancelamento, erro, contexto e envio único aprovados.');
})().catch(error => {console.error(error); process.exitCode = 1;});
