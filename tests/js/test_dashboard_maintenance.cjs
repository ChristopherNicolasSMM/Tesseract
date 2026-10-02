// Run with: node --test tests/js/test_dashboard_maintenance.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const html = fs.readFileSync('addons/addon_brewstation/features/feature_mash_control/templates/plant_workspace/_dashboard_maintenance.html', 'utf8');
  const formTag = html.match(/<form\b[^>]*>/s)[0];
  const attrs = Object.fromEntries([...formTag.matchAll(/([\w-]+)="([^"]*)"/g)].map(match => [match[1], match[2]]));
  const dataset = Object.fromEntries(Object.entries(attrs).filter(([key]) => key.startsWith('data-')).map(([key, value]) =>
    [key.slice(5).replace(/-([a-z])/g, (_, char) => char.toUpperCase()), value]));
  dataset.layoutName = 'Painel de teste';
  const rootListeners = {}, documentListeners = {};
  const button = { disabled: false };
  let nativePosts = 0, ajaxPosts = 0, confirmations = 0, errors = 0, resolveConfirmation, lastConfirmation;
  const form = {
    dataset, isConnected: true,
    querySelector: () => button,
    submit: () => nativePosts++,
    closest: selector => selector === 'form[data-confirm-key]' && attrs['data-confirm-key'] ? form : null,
  };
  const target = { closest: selector => selector === '.pw-layout-maintenance-form' && attrs.class.includes('pw-layout-maintenance-form') ? form : form.closest(selector) };
  const root = { addEventListener: (type, handler) => { rootListeners[type] = handler; } };
  const document = {
    getElementById: id => id === 'pwDashboardMaintenance' ? root : null,
    addEventListener: (type, handler) => { documentListeners[type] = handler; },
  };
  const window = { __workspaceSubmitForm: async () => { ajaxPosts++; }, __tesseractToast: { show: () => errors++ } };
  const context = { window, document };
  // Inclui a delegação REAL do Core para detectar confirmação/post em duplicidade.
  vm.runInNewContext(fs.readFileSync('static/js/core_confirm_dialog.js', 'utf8'), context);
  window.__tesseractConfirm = options => {
    confirmations++;
    lastConfirmation = options;
    return new Promise(resolve => { resolveConfirmation = resolve; });
  };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  return {
    form, button, confirmation: () => lastConfirmation,
    submit() {
      const event = { target, preventDefault() {} };
      documentListeners.submit(event);
      return rootListeners.submit(event);
    },
    confirm: value => resolveConfirmation(value),
    stats: () => ({ nativePosts, ajaxPosts, confirmations, errors }),
  };
}

test('confirma uma vez e envia somente AJAX, mesmo com delegação global do Core', async () => {
  const ui = setup();
  const pending = ui.submit();
  await ui.submit(); // clique repetido durante a confirmação
  assert.equal(ui.stats().confirmations, 1);
  assert.equal(ui.confirmation().key, "brewstation_mashctrl.workspace.confirm_trash_layout");
  assert.equal(ui.confirmation().params.name, "Painel de teste");
  assert.equal(ui.button.disabled, true);
  ui.confirm(true);
  await pending;
  assert.deepEqual(ui.stats(), { nativePosts: 0, ajaxPosts: 1, confirmations: 1, errors: 0 });
  assert.equal(ui.button.disabled, false);
});

for (const cancel of [true, false]) {
  test(cancel ? 'cancelar não envia manutenção' : 'trocar aba durante modal não envia formulário removido', async () => {
    const ui = setup();
    const pending = ui.submit();
    if (!cancel) ui.form.isConnected = false;
    ui.confirm(!cancel);
    await pending;
    assert.deepEqual(ui.stats(), { nativePosts: 0, ajaxPosts: 0, confirmations: 1, errors: 0 });
    assert.equal(ui.button.disabled, false);
  });
}
