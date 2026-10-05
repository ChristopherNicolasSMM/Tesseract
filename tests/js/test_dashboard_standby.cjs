const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function fixture(enabled = true) {
  const listeners = new Map(), timers = new Map(), classes = new Set();
  let next = 0, suspended = false;
  const document = {
    addEventListener: (key, callback) => listeners.set(key, callback),
    removeEventListener: key => listeners.delete(key)
  };
  const context = {window: {}, document, setTimeout: callback => {timers.set(++next, callback); return next;}, clearTimeout: id => timers.delete(id)};
  vm.runInNewContext(fs.readFileSync('static/js/dashboard_standby.js', 'utf8'), context);
  const canvas = {isConnected: true, classList: {add: v => classes.add(v), remove: v => classes.delete(v)}};
  const cleanup = context.window.TesseractDashboardStandby.mount({canvas, enabled, seconds: 10, suspended: () => suspended});
  function expire() {const [id, callback] = [...timers][0]; timers.delete(id); callback();}
  return {listeners, timers, classes, cleanup, expire, canvas, suspend: value => suspended = value};
}
const disabled = fixture(false);
assert.equal(disabled.listeners.size, 0);
assert.equal(disabled.timers.size, 0);
const f = fixture();
f.expire(); assert(f.classes.has('db-visual-standby'));
for (const event of ['pointermove', 'pointerdown', 'keydown', 'focusin', 'wheel', 'visibilitychange']) {
  f.listeners.get(event)(); assert.equal(f.classes.size, 0); assert.equal(f.timers.size, 1);
  f.expire(); assert(f.classes.has('db-visual-standby'));
}
f.suspend(true); f.listeners.get('pointerdown')(); f.expire();
assert.equal(f.classes.size, 0); assert.equal(f.timers.size, 1);
f.suspend(false); f.expire(); assert(f.classes.has('db-visual-standby'));
f.cleanup(); f.cleanup(); assert.equal(f.timers.size, 0); assert.equal(f.listeners.size, 0); assert.equal(f.classes.size, 0);
const detached = fixture(); detached.canvas.isConnected = false; detached.expire(); assert.equal(detached.classes.size, 0); detached.cleanup();
console.log('Standby: inatividade, despertar, edição, desativação e limpeza verificados.');
