/* Prévia isolada: HTML gerado pelo compositor, sem execução de scripts. */
(() => {
  'use strict';
  function show(frame, html, button) {
    button.disabled = true;
    return new Promise(resolve => {
      frame.onload = () => {
        frame.contentDocument.documentElement.dataset.theme = document.documentElement.dataset.theme || 'light';
        button.disabled = false;
        resolve();
      };
      frame.srcdoc = html;
    });
  }
  function clear(frame, button) {
    frame.onload = null;
    frame.removeAttribute('srcdoc');
    button.disabled = true;
  }
  function print(frame) {
    if (!frame.hasAttribute('srcdoc')) return;
    frame.contentWindow.focus();
    frame.contentWindow.print();
  }
  window.TesseractReportsPreview = {show, clear, print};
})();
