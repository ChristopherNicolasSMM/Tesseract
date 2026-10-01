// Run with: node --test tests/js/test_weak_ref_combo.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(dataset = {}) {
  class Element extends EventTarget {
    constructor() { super(); this.value = ''; this.dataset = {}; this.children = []; this.isConnected = true;
      this.style = {}; this.classes = new Set(); this.classList = {
        add: value => this.classes.add(value), remove: value => this.classes.delete(value),
      }; }
    setCustomValidity(message) { this.validationMessage = message; }
    blur() {}
    appendChild(child) { this.children.push(child); }
    set innerHTML(value) { this.children = []; }
  }
  const hidden = new Element(), input = new Element(), list = new Element(), combo = new Element();
  combo.dataset = { weakrefSource: 'device_functions', weakrefValueField: 'name', ...dataset };
  combo.querySelector = selector => ({ '.weakref-combo-value': hidden, '.weakref-combo-search': input, '.weakref-combo-results': list })[selector];
  const document = new Element();
  document.querySelectorAll = () => [combo];
  document.createElement = () => new Element();
  let timer;
  const requests = [];
  const context = { document, window: {}, Event, encodeURIComponent,
    clearTimeout: () => { timer = null; }, setTimeout: fn => { timer = fn; return 1; },
    fetch: url => new Promise(resolve => requests.push({ url, resolve })),
  };
  vm.runInNewContext(fs.readFileSync('static/js/weak_ref_combo.js', 'utf8'), context);
  context.window.TesseractWeakRef.init(document);
  return { ...context, hidden, input, list, combo, requests, flush: () => { const fn = timer; timer = null; if (fn) fn(); } };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('scoped API lookup persists the business key and emits change once after repeated init', async () => {
  const ui = setup({ weakrefIds: '3,7' });
  ui.window.TesseractWeakRef.init(ui.document);
  let changes = 0;
  ui.hidden.addEventListener('change', () => changes++);
  ui.input.value = 'Temperatura';
  ui.input.dispatchEvent(new Event('input'));
  ui.flush();
  assert.equal(ui.requests.length, 1);
  const url = new URL(ui.requests[0].url, 'https://example.test');
  assert.equal(url.searchParams.get('ids'), '3,7');
  assert.equal(url.searchParams.get('value_field'), 'name');
  ui.requests[0].resolve({ ok: true, json: async () => ({ results: [{ id: 'mash_temp', text: 'Temperatura' }] }) });
  await settle();
  ui.list.children[0].dispatchEvent(new Event('click'));
  assert.equal(ui.hidden.value, 'mash_temp');
  assert.equal(ui.input.validationMessage, '');
  assert.equal(changes, 1);
  ui.input.value = '';
  ui.input.dispatchEvent(new Event('input'));
  assert.equal(ui.hidden.value, '');
  assert.equal(changes, 2);
});

test('empty scope stays explicit and an old response cannot replace current results', async () => {
  const ui = setup({ weakrefIds: '' });
  ui.input.value = 'antigo'; ui.input.dispatchEvent(new Event('input')); ui.flush();
  ui.input.value = 'novo'; ui.input.dispatchEvent(new Event('input')); ui.flush();
  assert.match(ui.requests[0].url, /&ids=$/);
  ui.requests[1].resolve({ ok: true, json: async () => ({ results: [{ id: 'new', text: 'Novo' }] }) });
  await settle();
  ui.requests[0].resolve({ ok: true, json: async () => ({ results: [{ id: 'old', text: 'Antigo' }] }) });
  await settle();
  assert.equal(ui.list.children.length, 1);
  assert.equal(ui.list.children[0].textContent, 'Novo');
});

test('a removed AJAX fragment ignores the response', async () => {
  const ui = setup();
  ui.input.dispatchEvent(new Event('focus')); ui.flush();
  ui.combo.isConnected = false;
  ui.requests[0].resolve({ ok: true, json: async () => ({ results: [{ id: 'gone', text: 'Removido' }] }) });
  await settle();
  assert.equal(ui.list.children.length, 0);
});
