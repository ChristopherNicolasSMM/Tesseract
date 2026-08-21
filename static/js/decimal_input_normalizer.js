/*
 * static/js/decimal_input_normalizer.js
 *
 * Skill 20 (docs/skills/20-proposta-crudgen-tipo-sqlalchemy-html.md):
 * campos <input type="number"> só aceitam ponto como separador
 * decimal — teclado numérico PT-BR (inclusive em mobile) sugere
 * vírgula, e o navegador rejeita o valor digitado sem avisar direito.
 * Este script normaliza vírgula -> ponto em qualquer campo marcado
 * com a classe "crudgen-decimal-input" (só campos number derivados de
 * Float/Numeric — Integer usa step="1", não passa por aqui na
 * prática, mas o seletor não distingue por decisão de simplicidade).
 *
 * Escopo travado (skill 20, seção N): só troca vírgula por ponto no
 * blur/submit, sem biblioteca externa, sem máscara de input completa.
 */
(function () {
  function normalize(input) {
    if (typeof input.value === "string" && input.value.includes(",")) {
      input.value = input.value.replace(",", ".");
    }
  }

  document.addEventListener("blur", function (event) {
    if (event.target && event.target.classList && event.target.classList.contains("crudgen-decimal-input")) {
      normalize(event.target);
    }
  }, true);

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.querySelectorAll) return;
    var fields = form.querySelectorAll(".crudgen-decimal-input");
    for (var i = 0; i < fields.length; i++) {
      normalize(fields[i]);
    }
  }, true);
})();
