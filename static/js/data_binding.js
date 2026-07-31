/**
 * static/js/data_binding.js
 *
 * Fase 10, Patch 4 — bind de dado real dos componentes do Tier 1
 * (select dinâmico, radio, form_container, datagrid). Sempre busca
 * dado via o endpoint server-side já existente
 * (POST /admin/designer/data-action/<id>/execute, core/actions_catalog.py
 * §call_data_action) — nunca fala direto com um provedor OData do
 * navegador, mesma regra de "toda Ação que toca dado roda no
 * servidor" já aplicada ao motor de Ações (Patch 3).
 *
 * form_container casa campo por NOME (atributo `name` do input,
 * vindo de field_name/comp.name — mesma convenção de textbox desde a
 * Fase 7c) com a chave do registro retornado, filtrando os
 * componentes da página que caem geometricamente dentro do
 * retângulo do container (x/y/width/height do canvas) — não é
 * aninhamento real de DOM, é aninhamento por posição, coerente com o
 * canvas livre (x/y) que o Designer já usa desde a Fase 7c.
 */
(function (window) {
  "use strict";

  function fetchDataAction(actionId, body) {
    return fetch("/admin/designer/data-action/" + actionId + "/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (r) { return r.json(); });
  }

  function initSelects() {
    document.querySelectorAll("[data-select-comp]").forEach(function (sel) {
      const source = sel.getAttribute("data-options-source");
      if (source === "data_action") {
        const actionId = sel.getAttribute("data-data-action-id");
        const valueField = sel.getAttribute("data-value-field") || "id";
        const labelField = sel.getAttribute("data-label-field") || "name";
        if (!actionId) return;
        fetchDataAction(actionId).then(function (res) {
          if (!res.success) return;
          (res.result.value || []).forEach(function (row) {
            const opt = document.createElement("option");
            opt.value = row[valueField];
            opt.textContent = row[labelField];
            sel.appendChild(opt);
          });
        });
      } else {
        const raw = sel.getAttribute("data-static-options") || "";
        raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean).forEach(function (v) {
          const opt = document.createElement("option");
          opt.value = v;
          opt.textContent = v;
          sel.appendChild(opt);
        });
      }
    });
  }

  function initRadioGroups() {
    document.querySelectorAll("[data-radio-group]").forEach(function (container) {
      const name = container.getAttribute("data-radio-name");
      const def = container.getAttribute("data-radio-default") || "";
      const raw = container.getAttribute("data-radio-options") || "";
      raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean).forEach(function (v, i) {
        const id = name + "_" + i;
        const wrap = document.createElement("div");
        wrap.className = "form-check";
        wrap.innerHTML =
          '<input class="form-check-input" type="radio" name="' + name + '" id="' + id + '" value="' + v + '"' +
          (v === def ? " checked" : "") + ">" +
          '<label class="form-check-label small" for="' + id + '">' + v + "</label>";
        container.appendChild(wrap);
      });
    });
  }

  function fieldsWithin(container) {
    const x = parseInt(container.getAttribute("data-x"), 10);
    const y = parseInt(container.getAttribute("data-y"), 10);
    const w = parseInt(container.getAttribute("data-width"), 10);
    const h = parseInt(container.getAttribute("data-height"), 10);
    const result = [];
    document.querySelectorAll("#runtimeCanvas .dsg-runtime-component").forEach(function (el) {
      if (el.querySelector("[data-form-container]")) return;
      const ex = parseInt(el.style.left, 10);
      const ey = parseInt(el.style.top, 10);
      if (ex >= x && ey >= y && ex <= x + w && ey <= y + h) {
        result.push(el);
      }
    });
    return result;
  }

  function applyRecordToFields(container, record) {
    fieldsWithin(container).forEach(function (el) {
      const input = el.querySelector("input[name], select[name], textarea[name]");
      if (input) {
        const field = input.name;
        if (!(field in record)) return;
        if (input.type === "checkbox") {
          input.checked = !!record[field];
        } else {
          input.value = record[field] == null ? "" : record[field];
        }
        return;
      }
      const radioGroup = el.querySelector("[data-radio-group]");
      if (radioGroup) {
        const field = radioGroup.getAttribute("data-radio-name");
        if (!(field in record)) return;
        el.querySelectorAll('input[type="radio"][name="' + field + '"]').forEach(function (r) {
          r.checked = String(r.value) === String(record[field]);
        });
      }
    });
  }

  function initFormContainers() {
    document.querySelectorAll("[data-form-container]").forEach(function (container) {
      const actionId = container.getAttribute("data-data-action-id");
      if (!actionId) return;
      const keyParam = container.getAttribute("data-key-param") || "id";
      const keyValue = new URLSearchParams(window.location.search).get(keyParam);
      if (!keyValue) return;
      fetchDataAction(actionId, { params: { "$filter": "id eq " + keyValue } }).then(function (res) {
        if (!res.success) return;
        const rows = res.result.value || [];
        if (rows.length) applyRecordToFields(container, rows[0]);
      });
    });
  }

  function initDatagrids() {
    document.querySelectorAll("[data-datagrid]").forEach(function (wrapper) {
      const actionId = wrapper.getAttribute("data-data-action-id");
      const table = wrapper.querySelector("[data-datagrid-table]");
      if (!actionId || !table) return;
      const columnsAttr = (wrapper.getAttribute("data-columns") || "")
        .split(",").map(function (s) { return s.trim(); }).filter(Boolean);

      fetchDataAction(actionId).then(function (res) {
        if (!res.success) return;
        const rows = res.result.value || [];
        const cols = columnsAttr.length ? columnsAttr : (rows[0]
          ? Object.keys(rows[0]).filter(function (k) { return ["is_deleted", "deleted_at"].indexOf(k) === -1; })
          : []);

        const thead = table.querySelector("thead");
        const tbody = table.querySelector("tbody");
        thead.innerHTML = "<tr>" + cols.map(function (c) { return "<th>" + c + "</th>"; }).join("") + "</tr>";
        tbody.innerHTML = rows.map(function (row) {
          return "<tr>" + cols.map(function (c) {
            const v = row[c];
            return "<td>" + (v == null ? "" : String(v)) + "</td>";
          }).join("") + "</tr>";
        }).join("");

        if (window.simpleDatatables && window.simpleDatatables.DataTable) {
          new window.simpleDatatables.DataTable(table);
        }
      });
    });
  }

  function initLists() {
    document.querySelectorAll("[data-list-comp]").forEach(function (ul) {
      const actionId = ul.getAttribute("data-data-action-id");
      const displayField = ul.getAttribute("data-display-field") || "name";
      if (!actionId) return;
      fetchDataAction(actionId).then(function (res) {
        if (!res.success) return;
        const rows = res.result.value || [];
        ul.innerHTML = rows.map(function (row) {
          const text = row[displayField] == null ? "" : String(row[displayField]);
          return '<li class="list-group-item">' + text.replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
          }) + "</li>";
        }).join("");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSelects();
    initRadioGroups();
    initFormContainers();
    initDatagrids();
    initLists();
  });

  window.DataBinding = {
    fetchDataAction: fetchDataAction,
    initSelects: initSelects,
    initRadioGroups: initRadioGroups,
    initFormContainers: initFormContainers,
    initDatagrids: initDatagrids,
    initLists: initLists,
  };
})(window);
