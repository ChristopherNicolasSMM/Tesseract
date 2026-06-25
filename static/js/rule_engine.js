/**
 * static/js/rule_engine.js
 *
 * Motor de validação client-side — implementa as funções do grupo
 * "Validação" do catálogo de regras (core/rules_catalog.py).
 *
 * Cada campo de formulário gerado pelo CrudGen pode ter um atributo
 * data-rules='[{"id":"obrigatorio","params":{"message":"..."}}]'
 * (preenchido pelo controller a partir de FieldRule, model/core/
 * field_rule.py). No submit, RuleEngine.validateForm() roda todas as
 * regras de todos os campos e impede o envio se alguma falhar,
 * mostrando o erro inline (Bootstrap `is-invalid`/`invalid-feedback`).
 *
 * Escopo desta fase (BACKLOG.md): só Validação. Visibilidade/Cálculo
 * ficam para quando o Designer (Fase 7c) existir — não tente chamar
 * RuleEngine.rules.visibleIf/calculate/etc., elas não existem aqui.
 */
(function (window) {
  "use strict";

  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function validateCpfDigits(cpf) {
    const digits = onlyDigits(cpf);
    if (digits.length !== 11) return false;
    if (digits === digits[0].repeat(11)) return false;

    function checkDigit(slice, weightStart) {
      let total = 0;
      for (let i = 0; i < slice.length; i++) {
        total += parseInt(slice[i], 10) * (weightStart - i);
      }
      const remainder = (total * 10) % 11;
      return remainder === 10 ? 0 : remainder;
    }

    const firstCheck = checkDigit(digits.slice(0, 9), 10);
    if (firstCheck !== parseInt(digits[9], 10)) return false;

    const secondCheck = checkDigit(digits.slice(0, 10), 11);
    return secondCheck === parseInt(digits[10], 10);
  }

  function validateCnpjDigits(cnpj) {
    const digits = onlyDigits(cnpj);
    if (digits.length !== 14) return false;
    if (digits === digits[0].repeat(14)) return false;

    function checkDigit(slice, weights) {
      let total = 0;
      for (let i = 0; i < slice.length; i++) {
        total += parseInt(slice[i], 10) * weights[i];
      }
      const remainder = total % 11;
      return remainder < 2 ? 0 : 11 - remainder;
    }

    const w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

    const d1 = checkDigit(digits.slice(0, 12), w1);
    if (d1 !== parseInt(digits[12], 10)) return false;

    const d2 = checkDigit(digits.slice(0, 13), w2);
    return d2 === parseInt(digits[13], 10);
  }

  function fillTemplate(message, params) {
    return (message || "").replace(/\{(\w+)\}/g, function (_, key) {
      return params && params[key] !== undefined ? params[key] : "";
    });
  }

  /**
   * Cada função recebe (el, params) e retorna `null` se válido, ou a
   * mensagem de erro (já com os placeholders substituídos) se inválido.
   */
  const rules = {
    required: function (el, params) {
      const value = (el.value || "").trim();
      if (value === "") return fillTemplate(params.message, params);
      return null;
    },
    minLength: function (el, params) {
      const value = el.value || "";
      if (value !== "" && value.length < parseInt(params.min, 10)) {
        return fillTemplate(params.message, params);
      }
      return null;
    },
    maxLength: function (el, params) {
      const value = el.value || "";
      if (value.length > parseInt(params.max, 10)) {
        return fillTemplate(params.message, params);
      }
      return null;
    },
    email: function (el, params) {
      const value = (el.value || "").trim();
      if (value === "") return null; // combine com "obrigatorio" se for o caso
      const re = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
      if (!re.test(value)) return fillTemplate(params.message, params);
      return null;
    },
    cpf: function (el, params) {
      const value = el.value || "";
      if (value === "") return null;
      if (!validateCpfDigits(value)) return fillTemplate(params.message, params);
      return null;
    },
    cnpj: function (el, params) {
      const value = el.value || "";
      if (value === "") return null;
      if (!validateCnpjDigits(value)) return fillTemplate(params.message, params);
      return null;
    },
    onlyNumbers: function (el, params) {
      const value = el.value || "";
      if (value !== "" && !/^\d+$/.test(value)) {
        return fillTemplate(params.message, params);
      }
      return null;
    },
    minValue: function (el, params) {
      const value = el.value;
      if (value !== "" && Number(value) < Number(params.min)) {
        return fillTemplate(params.message, params);
      }
      return null;
    },
    maxValue: function (el, params) {
      const value = el.value;
      if (value !== "" && Number(value) > Number(params.max)) {
        return fillTemplate(params.message, params);
      }
      return null;
    },
    validDate: function (el, params) {
      const value = el.value;
      if (value === "") return null;
      const d = new Date(value);
      if (isNaN(d.getTime())) return fillTemplate(params.message, params);
      return null;
    },
  };

  function clearFieldError(el) {
    el.classList.remove("is-invalid");
    const feedback = el.parentElement.querySelector(".invalid-feedback[data-rule-engine]");
    if (feedback) feedback.remove();
  }

  function showFieldError(el, message) {
    el.classList.add("is-invalid");
    let feedback = el.parentElement.querySelector(".invalid-feedback[data-rule-engine]");
    if (!feedback) {
      feedback = document.createElement("div");
      feedback.className = "invalid-feedback";
      feedback.setAttribute("data-rule-engine", "1");
      el.parentElement.appendChild(feedback);
    }
    feedback.textContent = message;
  }

  function validateField(el) {
    clearFieldError(el);
    const raw = el.getAttribute("data-rules");
    if (!raw) return true;

    let ruleList;
    try {
      ruleList = JSON.parse(raw);
    } catch (e) {
      console.warn("data-rules inválido em", el, e);
      return true;
    }

    for (const ruleSpec of ruleList) {
      const fn = rules[ruleSpec.js_function];
      if (!fn) continue; // regra não conectada nesta fase (Visibilidade/Cálculo)
      const error = fn(el, ruleSpec.params || {});
      if (error) {
        showFieldError(el, error);
        return false;
      }
    }
    return true;
  }

  /**
   * Valida todos os campos com data-rules dentro de um <form>. Retorna
   * true se tudo passou. Usar no listener de submit, chamando
   * event.preventDefault() se retornar false.
   */
  function validateForm(formEl) {
    const fields = formEl.querySelectorAll("[data-rules]");
    let allValid = true;
    fields.forEach(function (el) {
      if (!validateField(el)) allValid = false;
    });
    return allValid;
  }

  window.RuleEngine = {
    rules: rules,
    validateField: validateField,
    validateForm: validateForm,
  };
})(window);
