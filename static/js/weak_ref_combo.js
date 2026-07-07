/**
 * static/js/weak_ref_combo.js
 *
 * Combo de busca assíncrona pra campo de referência fraca (skill 11 —
 * docs/skills/11-referencia-fraca-e-display-field.md), gerado pelo
 * CrudGen sempre que um model declara @weak_ref(..., options=...).
 *
 * Decisão de implementação (skill 11, seção 6, pendência em aberto
 * resolvida nesta rodada): vanilla JS, sem Select2/jQuery — o projeto
 * não tem nenhum dos dois nos assets estáticos hoje (herdados do Nice
 * Admin), e vendorizar uma lib nova só pra isto não se justificava.
 * Se o projeto adotar Select2 por outro motivo no futuro, este arquivo
 * pode ser aposentado em favor dele — o endpoint /api/options já
 * devolve o formato de resposta nativo do Select2, de propósito.
 *
 * Markup esperado (gerado por detail.html.j2):
 *   <div class="weakref-combo" data-weakref-source="materials">
 *     <input type="hidden" class="weakref-combo-value" name="material_id" value="3">
 *     <input type="text" class="weakref-combo-search" value="Malte Pilsen">
 *     <ul class="weakref-combo-results"></ul>
 *   </div>
 */
(function () {
  "use strict";

  function debounce(fn, delayMs) {
    let timer = null;
    return function debounced(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delayMs);
    };
  }

  function renderResults(container, items) {
    const list = container.querySelector(".weakref-combo-results");
    const hidden = container.querySelector(".weakref-combo-value");
    const search = container.querySelector(".weakref-combo-search");

    list.innerHTML = "";
    if (!items.length) {
      list.classList.remove("show");
      return;
    }

    items.forEach(function (item) {
      const li = document.createElement("li");
      li.className = "list-group-item list-group-item-action";
      li.style.cursor = "pointer";
      li.textContent = item.text;
      li.addEventListener("click", function () {
        hidden.value = item.id;
        search.value = item.text;
        list.classList.remove("show");
      });
      list.appendChild(li);
    });
    list.classList.add("show");
  }

  function search(container) {
    const source = container.dataset.weakrefSource;
    const input = container.querySelector(".weakref-combo-search");
    const term = (input.value || "").trim();

    fetch("/api/options/" + encodeURIComponent(source) + "?search=" + encodeURIComponent(term))
      .then(function (resp) {
        return resp.ok ? resp.json() : { results: [] };
      })
      .then(function (data) {
        renderResults(container, data.results || []);
      })
      .catch(function () {
        renderResults(container, []);
      });
  }

  function initCombo(container) {
    const debouncedSearch = debounce(function () { search(container); }, 250);
    const input = container.querySelector(".weakref-combo-search");

    input.addEventListener("input", debouncedSearch);
    input.addEventListener("focus", debouncedSearch);

    document.addEventListener("click", function (evt) {
      if (!container.contains(evt.target)) {
        container.querySelector(".weakref-combo-results").classList.remove("show");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".weakref-combo").forEach(initCombo);
  });
})();
