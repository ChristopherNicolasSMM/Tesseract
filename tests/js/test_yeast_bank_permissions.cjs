const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function panel(file, visible, counts, create = false) {
  const calls = [], handlers = {}, panes = {};
  function element() {
    return {innerHTML: '', children: [], style: {}, dataset: {}, classList: {add(){}, remove(){}},
      appendChild(child) {this.children.push(child);},
      addEventListener(name, callback) {this[name] = callback;},
      querySelector(selector) {return selector === 'form' ? (this.innerHTML.includes('<form') ? form : null) : null;}};
  }
  const button = {disabled: false};
  const form = {addEventListener(name, callback){this[name] = callback;}, querySelector(){return button;}};
  const tab = file === 'painel-cepas' ? 'cepas' : 'eventos';
  const tbody = element(), items = element();
  const document = {
    getElementById(id) {
      if (id === 'painel-tabela-' + tab) return visible ? element() : null;
      return panes[id] ||= element();
    },
    querySelector(selector) {return selector.includes('tabela-itens') ? items : tbody;},
    querySelectorAll(){return [];}, createElement: element,
    addEventListener(name, callback){handlers[name] = callback;},
  };
  const cfg = {endpoints:{strains:'strains', bank_items:'items', bank_events:'events', cell_counts:'counts'}, links:{new_event:'/new'},
    permissions:{counts, new_count:create, item_detail:false}};
  const sandbox = {document, window:{addEventListener(){}}, console, Promise,
    TesseractData:{config(){return cfg;}, esc(v){return v ?? '';}, aviso(error){throw new Error(error);},
      rest:{async listar(endpoint){calls.push(endpoint); return {items:endpoint === 'strains' ? [{id:1,name:'US-05'}] : endpoint === 'items' ? [{id:2,strain_id:1,status:'active',estimated_viability_pct:90}] : []};}}}};
  vm.runInNewContext(fs.readFileSync('static/js/yeast_bank_painel/' + file + '.js', 'utf8'), sandbox);
  if (handlers.DOMContentLoaded) await handlers.DOMContentLoaded();
  if (visible && tab === 'cepas') {
    tbody.children[0].click();
    assert(!items.children[0].innerHTML.includes('href='), 'detail link must respect permission');
    items.children[0].click();
    assert.equal(panes['painel-item-detalhe'].innerHTML.includes('<form'), create);
    if (create) {
      let prevented = 0;
      form.submit({preventDefault(){prevented++;}});
      form.submit({preventDefault(){prevented++;}});
      assert.equal(prevented, 1);
      assert.equal(button.disabled, true);
    }
  }
  return calls;
}
(async () => {
  for (const file of ['painel-cepas', 'painel-eventos']) {
    assert.deepEqual(await panel(file, false, true), []);
    const denied = await panel(file, true, false);
    assert(!denied.includes('counts'), 'unauthorized endpoint must not be called');
    assert((await panel(file, true, true)).includes('counts'));
  }
  await panel('painel-cepas', true, false, true);
  console.log('YeastBank JS: permissions, hidden actions and duplicate submission passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
