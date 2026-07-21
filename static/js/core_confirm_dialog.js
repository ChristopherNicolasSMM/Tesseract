/**
 * static/js/core_confirm_dialog.js
 *
 * Skill 15 — substitui window.confirm() nativo por um modal Bootstrap
 * estilizado, resolvido via i18n (window.__tesseractTranslations,
 * injetado por templates/core/base.html a partir do i18n_service).
 *
 * Regra de ouro da skill (motivo real: Plant Workspace/Dashboard
 * carregam tela via fragmento AJAX, e <script> injetado via innerHTML
 * não auto-executa): o listener é registrado UMA VEZ aqui, por
 * delegação no document — nunca por querySelectorAll + addEventListener
 * em elementos específicos, que ficaria surdo a qualquer form injetado
 * depois do load inicial.
 *
 * Uso declarativo (forms):
 *   <form data-confirm-key="core.confirm.trash_generic">
 *   <form data-confirm-key="..." data-confirm-param-label="Bomba 1">
 *
 * Uso programático (fluxo que não é um submit de form simples, ex.:
 * dashboards/_scripts.html):
 *   window.__tesseractConfirm({ key: '...', params: { label: '...' } })
 *     .then(function (ok) { if (ok) { ... } });
 */
(function () {
  'use strict';

  function t(key, params) {
    var dict = window.__tesseractTranslations || {};
    var s = Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
    if (!params) return s;
    return s.replace(/\{(\w+)\}/g, function (_, name) {
      return Object.prototype.hasOwnProperty.call(params, name) ? params[name] : '{' + name + '}';
    });
  }

  // Lê data-confirm-param-[nome] de um elemento -> { nome: valor }
  function paramsFromDataset(el) {
    var params = {};
    var prefix = 'confirmParam';
    for (var key in el.dataset) {
      if (key.indexOf(prefix) === 0 && key !== prefix) {
        var name = key.slice(prefix.length);
        name = name.charAt(0).toLowerCase() + name.slice(1);
        params[name] = el.dataset[key];
      }
    }
    return params;
  }

  function ensureModal() {
    var existing = document.getElementById('core-confirm-modal');
    if (existing) return existing;

    var wrapper = document.createElement('div');
    wrapper.innerHTML =
      '<div class="modal fade core-popup-modal" id="core-confirm-modal" tabindex="-1" aria-hidden="true">' +
        '<div class="modal-dialog modal-dialog-centered">' +
          '<div class="modal-content">' +
            '<div class="modal-body" id="core-confirm-modal-body"></div>' +
            '<div class="modal-footer">' +
              '<button type="button" class="btn btn-outline-secondary" id="core-confirm-modal-cancel">Cancelar</button>' +
              '<button type="button" class="btn btn-danger" id="core-confirm-modal-ok">Confirmar</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(wrapper.firstElementChild);
    return document.getElementById('core-confirm-modal');
  }

  /**
   * @param {{key?: string, text?: string, params?: object}} opts
   * @returns {Promise<boolean>}
   */
  window.__tesseractConfirm = function (opts) {
    opts = opts || {};
    var text = opts.text != null ? opts.text : t(opts.key, opts.params);

    var modalEl = ensureModal();
    var bodyEl = document.getElementById('core-confirm-modal-body');
    var okBtn = document.getElementById('core-confirm-modal-ok');
    var cancelBtn = document.getElementById('core-confirm-modal-cancel');
    bodyEl.textContent = text;

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    return new Promise(function (resolve) {
      var confirmed = false;

      function onOk() {
        confirmed = true;
        modal.hide();
      }
      function onCancel() {
        modal.hide();
      }
      function onHidden() {
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        modalEl.removeEventListener('hidden.bs.modal', onHidden);
        resolve(confirmed);
      }

      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      modalEl.addEventListener('hidden.bs.modal', onHidden);
      modal.show();
    });
  };

  // Delegação de submit, fase de captura — cobre qualquer form com
  // data-confirm-key, incluindo os injetados depois do load inicial
  // por fragmento AJAX (skill 15, seção 1.3).
  document.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-confirm-key]');
    if (!form || form.dataset.confirmBypass === '1') return;

    event.preventDefault();
    window.__tesseractConfirm({
      key: form.dataset.confirmKey,
      params: paramsFromDataset(form),
    }).then(function (ok) {
      if (!ok) return;
      form.dataset.confirmBypass = '1';
      // HTMLFormElement.submit() não dispara o evento 'submit' de novo
      // (diferente de clicar no botão) — evita loop de interceptação.
      form.submit();
      delete form.dataset.confirmBypass;
    });
  }, true);

  // Delegação de click para elementos com data-confirm-key fora de um
  // <form> (ex.: botão avulso que dispara ação própria via JS, sem ser
  // submit). Elementos dentro de um form[data-confirm-key] já são
  // cobertos pelo listener de submit acima — não duplica confirmação.
  document.addEventListener('click', function (event) {
    var el = event.target.closest('[data-confirm-key]');
    if (!el || el.tagName === 'FORM' || el.closest('form[data-confirm-key]')) return;
    if (el.dataset.confirmBypass === '1') return;

    event.preventDefault();
    event.stopImmediatePropagation();
    window.__tesseractConfirm({
      key: el.dataset.confirmKey,
      params: paramsFromDataset(el),
    }).then(function (ok) {
      if (!ok) return;
      el.dataset.confirmBypass = '1';
      el.click();
      delete el.dataset.confirmBypass;
    });
  }, true);
})();
