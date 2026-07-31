/**
 * static/js/actions_engine.js
 *
 * Motor de execução das Ações disparáveis por evento de um
 * DesignerComponent (core/actions_catalog.py). Cada elemento do
 * runtime pode ter um atributo `data-events` com o mesmo formato de
 * DesignerComponent.events:
 *   {"onClick": [{"action_type": "show_message", "params": {...}}, ...]}
 *
 * Ações executam em sequência, na ordem configurada. Uma ação
 * "call_data_action" (a única server-side, ver core/actions_catalog.py)
 * interrompe a cadeia se a resposta do servidor falhar — mostra um
 * toast de erro automático e para; as demais ações client-side
 * (navigate/show_message/set_component_value/toggle_component) nunca
 * falham de um jeito que precise interromper a cadeia.
 *
 * Escopo desta fase (BACKLOG.md, Fase 10): só "onClick" é disparado
 * pelo runtime hoje (templates/core/designer_runtime.html só usa
 * isso em `button`) — o motor em si já é genérico o bastante pra
 * "onChange"/"onLoad" quando um tipo de componente que dispare esses
 * eventos existir (Patch 4+, ver mapeamento_niceadmin_designer.md).
 */
(function (window) {
  "use strict";

  function runNavigate(params) {
    if (!params.url) return;
    if (params.target === "_blank") {
      window.open(params.url, "_blank");
    } else {
      window.location.href = params.url;
    }
  }

  function runShowMessage(params) {
    if (window.__tesseractToast && typeof window.__tesseractToast.show === "function") {
      window.__tesseractToast.show(params.message || "", params.variant || "info");
    }
  }

  function findComponentEl(targetId) {
    return document.getElementById("comp-" + targetId);
  }

  function runSetComponentValue(params) {
    const el = findComponentEl(params.target_component_id);
    if (!el) return;
    const input = el.querySelector("input, textarea, select");
    if (input) {
      input.value = params.value || "";
    } else {
      el.textContent = params.value || "";
    }
  }

  function runToggleComponent(params) {
    const el = findComponentEl(params.target_component_id);
    if (!el) return;
    const mode = params.mode || "toggle";
    if (mode === "show") {
      el.style.display = "";
    } else if (mode === "hide") {
      el.style.display = "none";
    } else {
      el.style.display = el.style.display === "none" ? "" : "none";
    }
  }

  function runCallDataAction(params) {
    let payload = {};
    try {
      payload = params.payload ? JSON.parse(params.payload) : {};
    } catch (e) {
      payload = {};
    }
    return fetch("/admin/designer/data-action/" + params.data_action_id + "/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: params.key || undefined, payload: payload }),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.success) {
          runShowMessage({ message: (res.data && res.data.error) || "Falha ao executar a Ação de Dado.", variant: "error" });
          return false;
        }
        return true;
      })
      .catch(function () {
        runShowMessage({ message: "Falha de comunicação ao executar a Ação de Dado.", variant: "error" });
        return false;
      });
  }

  function runAction(action) {
    const params = action.params || {};
    switch (action.action_type) {
      case "navigate": runNavigate(params); return Promise.resolve(true);
      case "show_message": runShowMessage(params); return Promise.resolve(true);
      case "set_component_value": runSetComponentValue(params); return Promise.resolve(true);
      case "toggle_component": runToggleComponent(params); return Promise.resolve(true);
      case "call_data_action": return runCallDataAction(params);
      default: return Promise.resolve(true);
    }
  }

  function runChain(actions) {
    let promise = Promise.resolve(true);
    actions.forEach(function (action) {
      promise = promise.then(function (continueChain) {
        if (continueChain === false) return false;
        return runAction(action);
      });
    });
    return promise;
  }

  function fire(el, eventName) {
    const raw = el.getAttribute("data-events");
    if (!raw) return;
    let events;
    try {
      events = JSON.parse(raw);
    } catch (e) {
      return;
    }
    const actions = events[eventName];
    if (!actions || !actions.length) return;
    runChain(actions);
  }

  function attachRuntimeListeners(root) {
    root.querySelectorAll("[data-events]").forEach(function (el) {
      el.addEventListener("change", function () { fire(el, "onChange"); });
      fire(el, "onLoad");
    });
  }

  window.ActionsEngine = { fire: fire, attachRuntimeListeners: attachRuntimeListeners };
})(window);
