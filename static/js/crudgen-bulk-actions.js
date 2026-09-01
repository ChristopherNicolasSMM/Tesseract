/**
 * static/js/crudgen-bulk-actions.js
 *
 * Skill 25 — seleção de linha + apagar/inativar em massa, genérico
 * pra qualquer manage.html gerado pelo CrudGen. Não depende de
 * TesseractData (só disponível em telas que a incluem manualmente,
 * ex.: materials/manage.html) — usa window.__tesseractToast
 * (core_toast.js), sempre carregado por templates/core/base.html.
 *
 * Config lida de <script type="application/json" id="crudgen-bulk-actions-config">,
 * escrito por manage.html.j2: {"bulkTrashUrl": "...", "bulkInactivateUrl": "..."|null,
 * "reloadOnSuccess": true}.
 *
 * Botões extras específicos de uma entidade (ex.: os 4 de Materiais,
 * vindos de _acoes_em_massa_extra.html) têm seu próprio JS — este
 * arquivo só cuida do genérico (seleção, contagem, apagar, inativar).
 */
(function () {
  'use strict';

  function init() {
    var configEl = document.getElementById('crudgen-bulk-actions-config');
    var barra = document.getElementById('barraAcoesEmMassa');
    if (!configEl || !barra) return; // página sem ações em massa

    var config = JSON.parse(configEl.textContent);
    var contagemEl = barra.querySelector('[data-alvo="contagem-selecionados"]');
    var checkboxTodos = document.getElementById('crudgenCheckboxSelecionarTodos');
    var btnApagar = barra.querySelector('[data-crudgen-acao-massa="apagar"]');
    var btnInativar = barra.querySelector('[data-crudgen-acao-massa="inativar"]');

    function checkboxesLinha() {
      return Array.prototype.slice.call(document.querySelectorAll('.crudgen-checkbox-selecionar-item'));
    }

    function idsSelecionados() {
      return checkboxesLinha()
        .filter(function (cb) { return cb.checked; })
        .map(function (cb) { return Number(cb.dataset.itemId); });
    }

    function atualizarBarra() {
      var n = idsSelecionados().length;
      if (contagemEl) contagemEl.textContent = n;
      barra.classList.toggle('d-none', n === 0);
      barra.classList.toggle('d-flex', n > 0);
      // Mantido em sincronia pro core_confirm_dialog.js (skill 15)
      // ler o valor certo no momento do click, sem precisar calcular
      // de novo ali (o listener de confirmação só lê dataset).
      if (btnApagar) btnApagar.dataset.confirmParamCount = String(n);
      if (btnInativar) btnInativar.dataset.confirmParamCount = String(n);
    }

    if (checkboxTodos) {
      checkboxTodos.addEventListener('change', function () {
        checkboxesLinha().forEach(function (cb) { cb.checked = checkboxTodos.checked; });
        atualizarBarra();
      });
    }
    document.addEventListener('change', function (evt) {
      if (evt.target.classList && evt.target.classList.contains('crudgen-checkbox-selecionar-item')) {
        atualizarBarra();
      }
    });

    function aviso(mensagem, categoria) {
      if (window.__tesseractToast) window.__tesseractToast.show(mensagem, categoria);
    }

    function executarAcaoMassa(url, botao) {
      var ids = idsSelecionados();
      if (!ids.length || !url) return;
      var textoOriginal = botao.innerHTML;
      botao.disabled = true;
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ids }),
      })
        .then(function (r) { return r.json(); })
        .then(function (dado) {
          if (dado.success) {
            aviso('Ação em massa concluída com sucesso.', 'success');
            if (config.reloadOnSuccess) {
              window.location.reload();
              return;
            }
          } else {
            aviso(dado.error || 'Algumas linhas falharam — veja o detalhe.', 'warning');
          }
        })
        .catch(function () {
          aviso('Erro ao executar a ação em massa.', 'error');
        })
        .finally(function () {
          botao.disabled = false;
          botao.innerHTML = textoOriginal;
        });
    }

    // Confirmação (skill 15, core_confirm_dialog.js) intercepta o
    // primeiro click de qualquer elemento com data-confirm-key e só
    // deixa o click "de verdade" passar depois de confirmado — este
    // listener roda normalmente, sem se preocupar com o modal.
    if (btnApagar) {
      btnApagar.addEventListener('click', function () {
        executarAcaoMassa(config.bulkTrashUrl, btnApagar);
      });
    }
    if (btnInativar) {
      btnInativar.addEventListener('click', function () {
        executarAcaoMassa(config.bulkInactivateUrl, btnInativar);
      });
    }

    atualizarBarra();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
