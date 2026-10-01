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
 * Markup esperado (gerado por detail.html.j2/manage.html.j2):
 *   <div class="weakref-combo" data-weakref-source="materials"
 *        data-weakref-value-field="name">
 *     <input type="hidden" class="weakref-combo-value" name="material_id" value="3">
 *     <input type="text" class="weakref-combo-search" value="Malte Pilsen">
 *     <ul class="weakref-combo-results"></ul>
 *   </div>
 * `data-weakref-value-field` é opcional — extensão skill 11 §6 (achado
 * real, Dashboard de Brassagem): por padrão o combo guarda o `id` do
 * registro escolhido; quando presente, o backend devolve outra coluna
 * do alvo como "id" (ex.: "name", pra referência fraca guardada por
 * nome — device_function_name, skill 02).
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
        container._weakrefRequestId = (container._weakrefRequestId || 0) + 1;
        hidden.value = item.id;
        search.value = item.text;
        list.classList.remove("show");
        search.setCustomValidity("");
        search.blur();
        hidden.dispatchEvent(new Event("change", { bubbles: true }));
      });
      list.appendChild(li);
    });
    list.classList.add("show");
  }

  function search(container) {
    const source = container.dataset.weakrefSource;
    const valueField = container.dataset.weakrefValueField;
    const input = container.querySelector(".weakref-combo-search");
    const term = (input.value || "").trim();

    let url = "/api/options/" + encodeURIComponent(source) + "?search=" + encodeURIComponent(term);
    if (valueField) {
      url += "&value_field=" + encodeURIComponent(valueField);
    }

    if (container.dataset.weakrefIds !== undefined) {
      url += "&ids=" + encodeURIComponent(container.dataset.weakrefIds);
    }
    const requestId = container._weakrefRequestId = (container._weakrefRequestId || 0) + 1;
    fetch(url)
      .then(function (resp) {
        return resp.ok ? resp.json() : { results: [] };
      })
      .then(function (data) {
        if (requestId === container._weakrefRequestId && container.isConnected) {
          renderResults(container, data.results || []);
        }
      })
      .catch(function () {
        if (requestId === container._weakrefRequestId) renderResults(container, []);
      });
  }

  function initCombo(container) {
    if (container.dataset.weakrefInitialized) return;
    container.dataset.weakrefInitialized = '1';
    const debouncedSearch = debounce(function () { search(container); }, 250);
    const input = container.querySelector(".weakref-combo-search");
    const hidden = container.querySelector(".weakref-combo-value");

    container.querySelector(".weakref-combo-results").classList.add("list-group");
    input.addEventListener("input", function () {
      const hadValue = hidden.value !== "";
      hidden.value = "";
      container._weakrefRequestId = (container._weakrefRequestId || 0) + 1;
      container.querySelector(".weakref-combo-results").classList.remove("show");
      input.setCustomValidity(input.value ? "Selecione uma opção da lista." : "");
      if (hadValue) hidden.dispatchEvent(new Event("change", { bubbles: true }));
      debouncedSearch();
    });
    input.addEventListener("focus", debouncedSearch);

  }

  document.addEventListener('click', function (evt) {
    document.querySelectorAll('.weakref-combo').forEach(function (container) {
      if (!container.contains(evt.target)) {
        container.querySelector('.weakref-combo-results').classList.remove('show');
      }
    });
  });

  window.TesseractWeakRef = { init: function (root) {
    (root || document).querySelectorAll('.weakref-combo').forEach(initCombo);
  }};
  document.addEventListener("DOMContentLoaded", function () {
    window.TesseractWeakRef.init(document);
  });
})();
