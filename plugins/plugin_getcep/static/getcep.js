/* Consulta assistida, inclusive em formulários CrudGen inseridos por AJAX. */
(function () {
  'use strict';
  const states = new WeakMap();
  const lookupURL = document.currentScript?.dataset.getcepUrl || '/api/plugins/getcep/__CEP__';
  function scopeOf(input) { return input.closest('[data-address-scope]') || input.closest('form'); }
  function field(scope, name, names = {}) { return scope.querySelector('[name="' + (names[name] || name) + '"]'); }
  function attach(input) {
    if (states.has(input) || input.disabled || input.readOnly) return;
    const names = input.name === 'endereco_cep' ? {logradouro: 'endereco_rua', bairro: 'endereco_bairro', cidade: 'endereco_cidade', estado: 'endereco_uf'} : {};
    const scope = scopeOf(input);
    if (!scope || !field(scope, 'cidade', names) || !field(scope, 'estado', names)) return;
    const container = input.parentElement;
    const button = container?.querySelector('[data-getcep-button]') || document.createElement('button');
    button.type = 'button'; button.className = 'btn btn-outline-secondary btn-sm mt-1';
    button.textContent = 'Consultar CEP'; button.disabled = false;
    const status = container?.querySelector('[data-getcep-status]') || document.createElement('small');
    status.className = 'd-block text-muted'; status.setAttribute('role', 'status');
    if (!button.parentElement) input.insertAdjacentElement('afterend', button);
    if (!status.parentElement) button.insertAdjacentElement('afterend', status);
    status.textContent = 'Informe o CEP para consultar ou preencha manualmente.';
    const state = {sequence: 0, controller: null, timer: null}; states.set(input, state);
    async function lookup() {
      clearTimeout(state.timer);
      const sequence = ++state.sequence;
      if (state.controller) state.controller.abort();
      const original = input.value;
      const cep = original.trim().replace('-', '');
      if (!/^[0-9]{8}$/.test(cep)) { status.textContent = 'Informe um CEP de oito dígitos.'; return; }
      const country = field(scope, 'pais');
      if (country && country.value.trim() && !/^(brasil|br|brazil)$/i.test(country.value.trim())) {
        status.textContent = 'Consulta disponível para endereços no Brasil.'; return;
      }
      const countryValue = country ? country.value : null;
      const targets = ['logradouro', 'bairro', 'cidade', 'estado'].map(name => [name, field(scope, name, names)]);
      const before = targets.map(([name, element]) => [name, element, element ? element.value : null]);
      const controller = new AbortController();
      state.controller = controller;
      const timer = setTimeout(() => controller.abort(), 10000);
      status.textContent = 'Consultando CEP…';
      try {
        const response = await fetch(lookupURL.replace('__CEP__', encodeURIComponent(cep)), {signal: controller.signal, credentials: 'same-origin'});
        if (response.status === 401 || response.status === 403) throw new Error('Sessão encerrada ou acesso não autorizado. Entre novamente.');
        let result;
        try { result = await response.json(); }
        catch { throw new Error('Resposta indisponível. Confira o carregamento do GetCEP.'); }
        if (sequence !== state.sequence || input.value !== original || !input.isConnected || (country && country.value !== countryValue)) return;
        if (!response.ok || !result.success) throw new Error(result.error || 'Consulta CEP indisponível.');
        let preserved = false;
        before.forEach(([name, element, previous]) => {
          if (!element || element.disabled || element.readOnly) return;
          if (previous.trim() || element.value !== previous) { preserved = true; return; }
          element.value = result.address[name] || '';
          element.dispatchEvent(new Event('input', {bubbles: true}));
          element.dispatchEvent(new Event('change', {bubbles: true}));
        });
        status.textContent = 'ViaCEP: ' + result.address.logradouro + ', ' + result.address.bairro + ', ' + result.address.cidade + '/' + result.address.estado + '. Confira número e complemento.' + (preserved ? ' Campos já preenchidos foram preservados.' : '');
      } catch (error) {
        if (sequence === state.sequence && input.value === original && input.isConnected) {
          status.textContent = (error.name === 'AbortError' ? 'Tempo limite da consulta CEP excedido.' : error.message || 'Consulta CEP indisponível.') + ' O preenchimento manual continua disponível.';
        }
      } finally { clearTimeout(timer); }
    }
    button.addEventListener('click', lookup);
    input.addEventListener('blur', () => { if (input.value.trim()) lookup(); });
    input.addEventListener('input', () => {
      ++state.sequence; clearTimeout(state.timer);
      if (state.controller) state.controller.abort();
      status.textContent = 'Informe o CEP para consultar ou preencha manualmente.';
      if (/^[0-9]{5}-?[0-9]{3}$/.test(input.value.trim())) state.timer = setTimeout(lookup, 450);
    });
  }
  function scan() { document.querySelectorAll('input[name="cep"], input[name="endereco_cep"]').forEach(attach); }
  function initialize() {
    scan();
    new MutationObserver(scan).observe(document.body, {childList: true, subtree: true});
    document.addEventListener?.('focusin', event => {
      if (event.target.matches?.('input[name="cep"], input[name="endereco_cep"]')) attach(event.target);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
