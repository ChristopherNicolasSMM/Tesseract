/* Consulta assistida, inclusive em formulários CrudGen inseridos por AJAX. */
(function () {
  'use strict';
  const states = new WeakMap();
  function scopeOf(input) { return input.closest('[data-address-scope]') || input.closest('form'); }
  function field(scope, name, names = {}) { return scope.querySelector('[name="' + (names[name] || name) + '"]'); }
  function attach(input) {
    if (states.has(input) || input.disabled || input.readOnly) return;
    const names = input.name === 'endereco_cep' ? {logradouro: 'endereco_rua', bairro: 'endereco_bairro', cidade: 'endereco_cidade', estado: 'endereco_uf'} : {};
    const scope = scopeOf(input);
    if (!scope || !field(scope, 'cidade', names) || !field(scope, 'estado', names)) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'btn btn-outline-secondary btn-sm mt-1';
    button.textContent = 'Consultar CEP';
    const status = document.createElement('small');
    status.className = 'd-block text-body-secondary'; status.setAttribute('role', 'status');
    input.insertAdjacentElement('afterend', button); button.insertAdjacentElement('afterend', status);
    const state = {sequence: 0, controller: null}; states.set(input, state);
    async function lookup() {
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
      state.controller = new AbortController();
      const timer = setTimeout(() => state.controller.abort(), 10000);
      status.textContent = 'Consultando CEP…';
      try {
        const response = await fetch('/api/plugins/getcep/' + cep, {signal: state.controller.signal, credentials: 'same-origin'});
        const result = await response.json();
        if (sequence !== state.sequence || input.value !== original || !input.isConnected || (country && country.value !== countryValue)) return;
        if (!response.ok || !result.success) throw new Error(result.error || 'Consulta indisponível.');
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
          status.textContent = 'Consulta indisponível ou CEP não encontrado. Confira o CEP; o preenchimento manual continua disponível.';
        }
      } finally { clearTimeout(timer); }
    }
    button.addEventListener('click', lookup);
    input.addEventListener('blur', () => { if (input.value.trim()) lookup(); });
    input.addEventListener('input', () => { ++state.sequence; if (state.controller) state.controller.abort(); status.textContent = ''; });
  }
  function scan() { document.querySelectorAll('input[name="cep"], input[name="endereco_cep"]').forEach(attach); }
  scan();
  new MutationObserver(scan).observe(document.body, {childList: true, subtree: true});
})();
