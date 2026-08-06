/**
 * static/js/freestyle/model_full-interacoes.js
 *
 * Modal, tooltip, confirmação e toast — os componentes do Bootstrap
 * que precisam de inicialização em JavaScript, mais os diálogos
 * padronizados do Tesseract (skill 15).
 */
(function () {
  'use strict';

  // ── Tooltips ────────────────────────────────────────────────────
  // Diferente do modal (que funciona só com data-bs-toggle), o tooltip
  // do Bootstrap 5 NÃO se inicializa sozinho: sem esta linha o
  // atributo `title` cai no balão nativo do navegador, fora do tema.
  if (window.bootstrap && window.bootstrap.Tooltip) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      window.bootstrap.Tooltip.getOrCreateInstance(el);
    });
  }

  // ── Confirmação ─────────────────────────────────────────────────
  // Use SEMPRE window.__tesseractConfirm em vez do confirm() nativo:
  // respeita o tema, resolve i18n e é consistente com o resto do
  // sistema (skill 15). Devolve Promise<boolean>.
  async function confirmarExclusao() {
    if (!window.__tesseractConfirm) return;

    const confirmado = await window.__tesseractConfirm({
      text: 'Excluir este registro? Esta ação não pode ser desfeita.',
    });
    if (!confirmado) return;

    // Aqui entraria a chamada real, ex.:
    //   await TesseractData.rest.lixeira(base, id);
    if (window.__tesseractToast) window.__tesseractToast.show('Registro excluído.', 'success');
  }

  // ── Toast ───────────────────────────────────────────────────────
  function mostrarToast() {
    if (!window.__tesseractToast) return;
    window.__tesseractToast.show('Mensagem de exemplo.', 'info');
  }

  // ── Progresso animado ───────────────────────────────────────────
  // Demonstra atualizar barra de progresso por código. Os aria-* têm
  // que acompanhar o width, senão leitor de tela anuncia o valor antigo.
  function animarProgresso() {
    const barra = document.querySelector('[data-progresso-animado]');
    if (!barra) return;

    let valor = 60;
    setInterval(function () {
      valor = valor >= 100 ? 20 : valor + 5;
      barra.style.width = valor + '%';
      barra.textContent = valor + '%';
      barra.setAttribute('aria-valuenow', valor);
    }, 2000);
  }

  // ── Eventos ─────────────────────────────────────────────────────
  // Delegação no document: funciona para elementos que ainda não
  // existem no momento em que este script roda.
  document.addEventListener('click', function (evento) {
    const acao = evento.target.closest('[data-acao]');
    if (!acao) return;

    switch (acao.getAttribute('data-acao')) {
      case 'confirmar-exclusao': confirmarExclusao(); break;
      case 'mostrar-toast': mostrarToast(); break;
    }
  });

  animarProgresso();
})();
