/**
 * static/js/estoque/pedido_compra_detalhe-itens.js
 *
 * Grid de Itens do Pedido de Compra (skill 23, Fase 5) — inspirado em
 * SAP MM: seleção de Material via busca, unidade de compra dependente
 * do Material escolhido, adicionar/editar em modal (decisão da
 * sessão — não inline no grid).
 *
 * fator_conversao_aplicado/quantidade_convertida_base/subtotal são
 * sempre calculados no servidor (hook de
 * item_pedido_compra_service_hooks.py) — o "Subtotal previsto" aqui é
 * só uma prévia client-side pra UX, nunca o valor gravado de verdade.
 */
(function () {
  "use strict";

  function init() {
    const configEl = document.getElementById("estoque-item-pedido-config");
    if (!configEl) return; // página sem aba de itens

    const config = TesseractData.config("estoque-item-pedido-config");
    const tabelaEl = document.querySelector("#aba-itens table[data-datatable]");
    const tbody = document.querySelector("[data-alvo='tabela-itens']");
    const modalEl = document.getElementById("modalItem");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const selectUnidade = modalEl.querySelector("[data-campo='material_unidade_id']");
    const materialCombo = modalEl.querySelector(".weakref-combo[data-weakref-source='materials']");
    const materialHidden = materialCombo.querySelector(".weakref-combo-value");
    let datatableInstancia = null;
    let cache = [];

    function fmt(numero) {
      if (numero === null || numero === undefined) return "—";
      return Number(numero).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    }

    function linhaHtml(item) {
      return (
        "<tr data-id=\"" + item.id + "\">" +
        "<td>" + TesseractData.esc(item.material_nome || ("Material #" + item.material_id)) + "</td>" +
        "<td>" + fmt(item.quantidade) + "</td>" +
        "<td>" + TesseractData.esc(item.unidade_nome || "") + "</td>" +
        "<td>" + fmt(item.preco_unitario) + "</td>" +
        "<td>" + fmt(item.subtotal) + "</td>" +
        "<td class=\"text-end\">" +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-acao=\"editar-item\" data-id=\"" + item.id + "\"><i class=\"bi bi-pencil\"></i></button> " +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-danger\" data-acao=\"remover-item\" data-id=\"" + item.id + "\"><i class=\"bi bi-trash\"></i></button>" +
        "</td></tr>"
      );
    }

    async function carregar() {
      try {
        const url = config.apiBaseItens + "/?pedido_compra_id=" + encodeURIComponent(config.pedidoCompraId);
        const dado = await TesseractData._json(url);
        cache = dado.items || [];

        // Mesmo raciocínio do grid de Endereços: a API de item não
        // devolve nome de Material/Unidade (tabela enxuta de
        // propósito) — busca em paralelo por id distinto.
        const materialIds = [...new Set(cache.map((i) => i.material_id))];
        const unidadeIds = [...new Set(cache.map((i) => i.material_unidade_id))];
        const [materiais, unidades] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(unidadeIds.map((id) => TesseractData._json(config.apiBaseUnidades + "/" + id).catch(() => null))),
        ]);
        const materialPorId = {};
        materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const unidadePorId = {};
        unidadeIds.forEach((id, i) => { unidadePorId[id] = unidades[i] ? unidades[i].item : null; });

        cache.forEach((item) => {
          const m = materialPorId[item.material_id];
          const u = unidadePorId[item.material_unidade_id];
          item.material_nome = m ? m.nome : null;
          item.unidade_nome = u ? u.unidade : null;
        });

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = cache.length
          ? cache.map(linhaHtml).join("")
          : '<tr><td colspan="6" class="text-muted">Nenhum item adicionado.</td></tr>';

        if (window.simpleDatatables && cache.length) {
          datatableInstancia = new window.simpleDatatables.DataTable(tabelaEl, {
            searchable: true, fixedHeight: false, perPage: 10, perPageSelect: [10, 25, 50],
            labels: { placeholder: "Buscar…", perPage: "{select} por página", noRows: "Nenhum registro encontrado", info: "Mostrando {start} a {end} de {rows}" },
          });
          tabelaEl.dataset.datatableIniciado = "1";
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-danger">Erro ao carregar itens: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    async function carregarUnidades(materialId, unidadeSelecionadaId) {
      selectUnidade.innerHTML = '<option value="">Carregando…</option>';
      selectUnidade.disabled = true;
      if (!materialId) {
        selectUnidade.innerHTML = '<option value="">— escolha o Material primeiro —</option>';
        return;
      }
      try {
        const dado = await TesseractData._json(config.apiBaseUnidades + "/?material_id=" + encodeURIComponent(materialId));
        const unidades = dado.items || [];
        if (!unidades.length) {
          selectUnidade.innerHTML = '<option value="">Nenhuma unidade cadastrada para este Material</option>';
          return;
        }
        selectUnidade.innerHTML = unidades.map((u) =>
          "<option value=\"" + u.id + "\"" + (String(u.id) === String(unidadeSelecionadaId) ? " selected" : "") + ">" +
          TesseractData.esc(u.unidade) + (u.is_unidade_base ? " (base)" : "") + "</option>"
        ).join("");
        selectUnidade.disabled = false;
      } catch (e) {
        selectUnidade.innerHTML = '<option value="">Erro ao carregar unidades</option>';
      }
    }

    function atualizarPreviaSubtotal() {
      const qtd = parseFloat(modalEl.querySelector("[data-campo='quantidade']").value) || 0;
      const preco = parseFloat(modalEl.querySelector("[data-campo='preco_unitario']").value) || 0;
      modalEl.querySelector("[data-alvo='subtotal-preview']").textContent =
        (qtd * preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
    }

    function limparModal() {
      modalEl.querySelector("[data-campo='item-id']").value = "";
      materialHidden.value = "";
      materialCombo.querySelector(".weakref-combo-search").value = "";
      modalEl.querySelector("[data-campo='quantidade']").value = "";
      modalEl.querySelector("[data-campo='preco_unitario']").value = "";
      modalEl.querySelector("[data-alvo='erro-item']").classList.add("d-none");
      carregarUnidades(null);
      atualizarPreviaSubtotal();
    }

    async function preencherModal(item) {
      modalEl.querySelector("[data-campo='item-id']").value = item.id;
      materialHidden.value = item.material_id;
      materialCombo.querySelector(".weakref-combo-search").value = item.material_nome || "";
      modalEl.querySelector("[data-campo='quantidade']").value = item.quantidade;
      modalEl.querySelector("[data-campo='preco_unitario']").value = item.preco_unitario;
      await carregarUnidades(item.material_id, item.material_unidade_id);
      atualizarPreviaSubtotal();
    }

    async function salvar() {
      const erroEl = modalEl.querySelector("[data-alvo='erro-item']");
      erroEl.classList.add("d-none");

      const materialId = materialHidden.value;
      const unidadeId = selectUnidade.value;
      const quantidade = modalEl.querySelector("[data-campo='quantidade']").value;
      const preco = modalEl.querySelector("[data-campo='preco_unitario']").value;

      if (!materialId || !unidadeId || !quantidade || !preco) {
        erroEl.textContent = "Preencha Material, Unidade, Quantidade e Preço Unitário.";
        erroEl.classList.remove("d-none");
        return;
      }

      const payload = {
        pedido_compra_id: config.pedidoCompraId,
        material_id: Number(materialId),
        material_unidade_id: Number(unidadeId),
        quantidade: Number(quantidade),
        preco_unitario: Number(preco),
      };

      const itemId = modalEl.querySelector("[data-campo='item-id']").value;
      try {
        if (itemId) {
          await TesseractData.rest.atualizar(config.apiBaseItens, itemId, payload);
        } else {
          await TesseractData.rest.criar(config.apiBaseItens, payload);
        }
        modal && modal.hide();
        await carregar();
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    }

    async function remover(id) {
      if (!window.confirm("Remover este item do pedido?")) return;
      try {
        await TesseractData.rest.lixeira(config.apiBaseItens, id);
        await carregar();
      } catch (e) {
        TesseractData.aviso(e.message, "error");
      }
    }

    document.querySelector("[data-acao='novo-item']").addEventListener("click", limparModal);

    materialHidden.addEventListener("change", function () {
      carregarUnidades(materialHidden.value || null);
    });
    // weak_ref_combo.js grava no hidden via clique no <li> de resultado
    // (propriedade .value, não atributo — MutationObserver com
    // attributeFilter não pega isso). Listener delegado no container do
    // combo: como o clique no <li> borbulha, este listener roda DEPOIS
    // do próprio weak_ref_combo.js já ter atualizado o hidden.
    materialCombo.addEventListener("click", function (evt) {
      if (evt.target.closest(".weakref-combo-results li")) {
        carregarUnidades(materialHidden.value || null);
      }
    });

    modalEl.querySelector("[data-campo='quantidade']").addEventListener("input", atualizarPreviaSubtotal);
    modalEl.querySelector("[data-campo='preco_unitario']").addEventListener("input", atualizarPreviaSubtotal);

    document.addEventListener("click", function (evt) {
      const botaoEditar = evt.target.closest("[data-acao='editar-item']");
      if (botaoEditar) {
        const item = cache.find((i) => String(i.id) === botaoEditar.dataset.id);
        if (item) {
          preencherModal(item);
          modal && modal.show();
        }
        return;
      }
      const botaoRemover = evt.target.closest("[data-acao='remover-item']");
      if (botaoRemover) {
        remover(botaoRemover.dataset.id);
        return;
      }
      if (evt.target.closest("[data-acao='salvar-item']")) {
        salvar();
      }
    });

    carregar();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
