/* Emissão contextual, com delegação para fragmentos AJAX do Workspace. */
(() => {
  'use strict';
  const modal = document.getElementById('reports-consumer-modal');
  if (!modal || modal.dataset.initialized) return;
  modal.dataset.initialized = 'true';
  const tr = JSON.parse(document.getElementById('reports-consumer-translations').textContent);
  const select = document.getElementById('reports-consumer-template');
  const parameters = document.getElementById('reports-consumer-parameters');
  const status = document.getElementById('reports-consumer-status');
  const submit = document.getElementById('reports-consumer-submit');
  let context, token, busy = false;
  const say = (key, error=false) => { status.textContent = tr[key] || key; status.className = error ? 'mt-3 text-danger' : 'mt-3'; };
  const fail = error => { say(error.message || tr.error, true); window.__tesseractToast?.show(error.message || tr.error, 'error'); };
  async function api(path, data) {
    const response = await fetch('/api/reports' + path, data === undefined ? {} : {
      method:'POST', headers:{'Content-Type':'application/json', 'X-Reports-CSRF':token}, body:JSON.stringify(data)
    });
    if (response.ok && response.headers.get('Content-Type')?.includes('application/pdf')) return response.blob();
    const value = await response.json();
    if (!response.ok) throw Error(value.error?.message || tr.error);
    return value;
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-report-consumer]');
    if (!button) return;
    event.preventDefault(); if (busy) return;
    busy = true; select.replaceChildren(); parameters.value = '{}'; submit.disabled = true; say('loading');
    context = {consumer:button.dataset.reportConsumer};
    if (context.consumer === 'stock') context.material_id = Number(button.dataset.materialId);
    else { context.session_id = Number(button.dataset.sessionId); context.plant_id = Number(button.dataset.plantId); }
    bootstrap.Modal.getOrCreateInstance(modal).show();
    try {
      // A sessão emite cookie/token; concluir antes de consultar o catálogo.
      const session = await api('/session');
      token = session.csrf_token;
      const catalog = await api(`/consumers/${context.consumer}/templates`);
      for (const item of catalog.items) {
        const option = document.createElement('option'); option.value = item.key;
        option.dataset.version = item.version; option.textContent = `${item.name} · ${item.version}`; select.append(option);
      }
      submit.disabled = catalog.items.length === 0; say(catalog.items.length ? 'ready' : 'empty');
    } catch (error) { fail(error); }
    finally { busy = false; }
  });
  document.getElementById('reports-consumer-form').addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !select.value) return;
    let values;
    try { values = JSON.parse(parameters.value); } catch (_) { fail(Error(tr.error)); return; }
    busy = true; submit.disabled = true; select.disabled = true; parameters.disabled = true; say('generating');
    try {
      const {consumer, ...data} = context;
      const blob = await api(`/consumers/${consumer}/render`, {...data, template:select.value,
        version:Number(select.selectedOptions[0].dataset.version), parameters:values});
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url; link.download = 'report.pdf'; document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000); say('done');
    } catch (error) { fail(error); }
    finally { busy = false; submit.disabled = false; select.disabled = false; parameters.disabled = false; }
  });
})();
