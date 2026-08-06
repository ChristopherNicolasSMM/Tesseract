/**
 * static/js/freestyle/model_full-formularios.js
 *
 * Comportamento de formulário: validação do Bootstrap, contador de
 * caracteres e exibição do valor da faixa.
 */
(function () {
  'use strict';

  // ── Validação ───────────────────────────────────────────────────
  // O <form> tem `novalidate` para desligar a validação nativa do
  // navegador (que ignora o tema e mostra balão do sistema). A classe
  // `was-validated` é o que faz o Bootstrap pintar os campos e mostrar
  // .invalid-feedback / .valid-feedback.
  document.querySelectorAll('[data-form-validado]').forEach(function (form) {
    form.addEventListener('submit', function (evento) {
      if (!form.checkValidity()) {
        evento.preventDefault();
        evento.stopPropagation();
      } else {
        evento.preventDefault(); // exemplo: não há endpoint de destino
        if (window.__tesseractToast) window.__tesseractToast.show('Formulário válido.', 'success');
      }
      form.classList.add('was-validated');
    });
  });

  // ── Contador de caracteres ──────────────────────────────────────
  document.querySelectorAll('[data-contador]').forEach(function (campo) {
    // O alvo é procurado dentro do mesmo bloco de campo, não no
    // documento inteiro — a tela pode ter vários contadores.
    const bloco = campo.closest('.row') || campo.parentElement;
    const alvo = bloco ? bloco.querySelector('[data-contador-alvo]') : null;
    if (!alvo) return;

    const atualizar = () => { alvo.textContent = campo.value.length; };
    campo.addEventListener('input', atualizar);
    atualizar(); // estado inicial, caso o campo já venha preenchido
  });

  // ── Editor de texto (Quill) ─────────────────────────────────────
  // A lib é carregada no extra_js da página; sem esta inicialização o
  // <div> fica só com o HTML inicial, sem barra de ferramentas.
  document.querySelectorAll('[data-editor-quill]').forEach(function (elemento) {
    if (!window.Quill) return;
    new window.Quill(elemento, {
      theme: 'snow',
      // Barra enxuta de propósito: a completa do Quill gera HTML que o
      // resto do sistema não estiliza.
      modules: {
        toolbar: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'clean'],
        ],
      },
    });
    // Ao salvar, envie `editor.root.innerHTML`. No servidor, trate como
    // conteúdo NÃO confiável — é digitado pelo usuário.
  });

  // ── Faixa (range) ───────────────────────────────────────────────
  // Um <input type="range"> sem indicação numérica é adivinhação: o
  // usuário arrasta sem saber onde parou.
  document.querySelectorAll('[data-faixa]').forEach(function (faixa) {
    const rotulo = document.createElement('div');
    rotulo.className = 'form-text';
    faixa.insertAdjacentElement('afterend', rotulo);

    const atualizar = () => { rotulo.textContent = 'Valor: ' + faixa.value; };
    faixa.addEventListener('input', atualizar);
    atualizar();
  });
})();
