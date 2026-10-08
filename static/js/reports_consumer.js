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
  const frame = document.getElementById('reports-consumer-preview');
  const printButton = document.getElementById('reports-consumer-print');
  const panel = document.getElementById('reports-consumer-preview-panel');
  printButton.onclick = () => window.TesseractReportsPreview.print(frame);
  const invalidate = () => { panel.hidden = true; window.TesseractReportsPreview.clear(frame, printButton); };
  function parameterForm(){const item=catalogItems.find(item=>item.key===select.value);window.TesseractReportsParameters.mount(document.getElementById('reports-consumer-parameter-fields'),item?.parameters||[],parameters,tr,invalidate);}
  select.onchange=()=>{parameters.value='{}';parameterForm();invalidate();};
  modal.addEventListener('hidden.bs.modal', () => { panel.hidden = true; window.TesseractReportsPreview.clear(frame, printButton); });
  let context, token, catalogItems=[], busy = false;
  const say = (key, error=false) => { status.textContent = tr[key] || key; status.className = error ? 'mt-3 text-danger' : 'mt-3'; };
  const fail = error => { say(error.message || tr.error, true); window.__tesseractToast?.show(error.message || tr.error, 'error'); };
  async function api(path, data) {
    const response = await fetch('/api/reports' + path, data === undefined ? {} : {
      method:'POST', headers:{'Content-Type':'application/json', 'X-Reports-CSRF':token}, body:JSON.stringify(data)
    });
    if (response.ok && response.headers.get('Content-Type')?.includes('text/html')) return response.text();
    const value = await response.json();
    if (!response.ok) throw Error(value.error?.message || tr.error);
    return value;
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-report-consumer]');
    if (!button) return;
    event.preventDefault(); if (busy) return;
    busy = true; select.replaceChildren(); parameters.value = '{}'; submit.disabled = true; say('loading');
    panel.hidden = true; window.TesseractReportsPreview.clear(frame, printButton);
    context = {consumer:button.dataset.reportConsumer};
    if (context.consumer === 'stock') context.material_id = Number(button.dataset.materialId);
    else { context.session_id = Number(button.dataset.sessionId); context.plant_id = Number(button.dataset.plantId); }
    bootstrap.Modal.getOrCreateInstance(modal).show();
    try {
      // A sessão emite cookie/token; concluir antes de consultar o catálogo.
      const session = await api('/session');
      token = session.csrf_token;
      const catalog = await api(`/consumers/${context.consumer}/templates`);
      catalogItems=catalog.items;
      for (const item of catalog.items) {
        const option = document.createElement('option'); option.value = item.key;
        option.dataset.version = item.version; option.textContent = `${item.name} · ${item.version}`; select.append(option);
      }
      parameterForm();
      submit.disabled = catalog.items.length === 0; say(catalog.items.length ? 'ready' : 'empty');
    } catch (error) { fail(error); }
    finally { busy = false; }
  });
  document.getElementById('reports-consumer-form').addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !select.value) return;
    if(!document.getElementById('reports-consumer-form').reportValidity())return;
    let values;
    try { values = JSON.parse(parameters.value); } catch (_) { fail(Error(tr.error)); return; }
    panel.hidden = true; window.TesseractReportsPreview.clear(frame, printButton);
    document.getElementById('reports-consumer-parameter-fields').disabled=true;
    busy = true; submit.disabled = true; select.disabled = true; parameters.disabled = true; say('generating');
    try {
      const {consumer, ...data} = context;
      const html = await api(`/consumers/${consumer}/render`, {...data, template:select.value,
        version:Number(select.selectedOptions[0].dataset.version), parameters:values, format:'html'});
      panel.hidden = false;
      await window.TesseractReportsPreview.show(frame, html, printButton); say('done');
    } catch (error) { fail(error); }
    finally { document.getElementById('reports-consumer-parameter-fields').disabled=false;busy = false; submit.disabled = false; select.disabled = false; parameters.disabled = false; }
  });
})();
