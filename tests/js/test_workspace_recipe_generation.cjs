const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('addons/addon_brewstation/features/feature_mash_control/templates/plant_workspace/_tab_recipe_detail.html', 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).find(s => s.includes('workspaceGenerateSessionForm'));
function fixture() {
  let submit, resolve, requests = 0;
  const opened = [], messages = [], button = {disabled: false};
  const form = {dataset: {}, isConnected: true, action: '/generate-session', querySelector: () => button, addEventListener: (_, handler) => submit = handler};
  const context = {document: {getElementById: () => form, querySelectorAll: () => []}, FormData: function () {}, encodeURIComponent,
    fetch: () => {requests++; return new Promise(r => resolve = r);},
    window: {__workspaceOpenTab: (...args) => opened.push(args), __tesseractToast: {show: (...args) => messages.push(args)}}};
  vm.runInNewContext(script, context);
  return {form, button, opened, messages, submit: () => submit({preventDefault() {}}), count: () => requests,
    respond: (ok = true) => resolve({ok, headers: {get: () => 'application/json'}, json: async () => ({ok, name: 'Sessão', session_id: 42, error: 'Falha de geração'})})};
}
(async () => {
  const f = fixture(), pending = f.submit();
  assert(f.button.disabled);
  await f.submit(); assert.equal(f.count(), 1);
  f.respond(); await pending;
  assert.equal(f.opened[0][0], 'sessions'); assert.equal(f.opened[0][1], '?session_id=42');
  assert(!f.button.disabled);
  const detached = fixture(), waiting = detached.submit();
  detached.form.isConnected = false; detached.respond(); await waiting;
  assert.equal(detached.opened.length, 0); assert.equal(detached.messages.length, 0);
  const failed = fixture(), attempt = failed.submit(); failed.respond(false); await attempt;
  assert.equal(failed.opened.length, 0); assert.equal(failed.messages[0][0], 'Falha de geração'); assert(!failed.button.disabled);
  const retry = failed.submit(); assert.equal(failed.count(), 2); failed.respond(); await retry;
  console.log('Geração AJAX: envio único, retorno contextual, erro e fragmento removido verificados.');
})().catch(error => {console.error(error); process.exitCode = 1;});
