/**
 * static/js/core_toast.js
 *
 * Skill 15 — substitui os <div class="alert"> duplicados por
 * template por um container único (#core-toast-container, em
 * templates/core/base.html), com dois caminhos de disparo:
 *
 * 1. Flash tradicional (POST -> redirect -> GET): base.html injeta
 *    window.__tesseractFlashMessages uma única vez; este arquivo lê no
 *    DOMContentLoaded e mostra como toast.
 * 2. Resposta AJAX (fragmento que não recarrega a página): quem já faz
 *    o fetch() chama window.__tesseractToast.show(message, category)
 *    diretamente.
 */
(function () {
  'use strict';

  var ICON_BY_CATEGORY = {
    success: 'bi-check-circle-fill',
    error: 'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill',
  };

  var AUTO_DISMISS_MS = 6000;

  function ensureContainer() {
    var el = document.getElementById('core-toast-container');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'core-toast-container';
    document.body.appendChild(el);
    return el;
  }

  function show(message, category) {
    if (!message) return;
    var resolvedCategory = ICON_BY_CATEGORY[category] ? category : 'info';
    var container = ensureContainer();

    var toast = document.createElement('div');
    toast.className = 'core-toast core-toast-' + resolvedCategory;
    toast.setAttribute('role', 'alert');
    toast.innerHTML =
      '<i class="bi ' + ICON_BY_CATEGORY[resolvedCategory] + '"></i>' +
      '<span class="core-toast-message"></span>' +
      '<button type="button" class="core-toast-close" aria-label="Fechar">\u00d7</button>';
    toast.querySelector('.core-toast-message').textContent = message;
    container.appendChild(toast);

    var timer = null;

    function remove() {
      if (timer) clearTimeout(timer);
      toast.classList.remove('core-toast-show');
      toast.addEventListener('transitionend', function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, { once: true });
    }

    toast.querySelector('.core-toast-close').addEventListener('click', remove);
    toast.addEventListener('mouseenter', function () {
      if (timer) clearTimeout(timer);
    });
    toast.addEventListener('mouseleave', function () {
      timer = setTimeout(remove, AUTO_DISMISS_MS);
    });

    // Duas fases (classe adicionada depois do append) para a transição
    // CSS de entrada funcionar de verdade.
    requestAnimationFrame(function () {
      toast.classList.add('core-toast-show');
    });

    timer = setTimeout(remove, AUTO_DISMISS_MS);
  }

  window.__tesseractToast = { show: show };

  document.addEventListener('DOMContentLoaded', function () {
    var flashed = window.__tesseractFlashMessages || [];
    flashed.forEach(function (item) {
      show(item.message, item.category);
    });
  });
})();
