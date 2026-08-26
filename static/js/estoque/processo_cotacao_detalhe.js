/**
 * static/js/estoque/processo_cotacao_detalhe.js
 *
 * Detalhe de ProcessoCotacao (skill 24, Fase 6.2) — duas abas
 * desenhadas à mão (fora do CrudGen): "Cotações" (um convite por
 * fornecedor, com sub-modal de Itens por Cotacao) e "Comparação"
 * (grid único com todos os ItemCotacao do processo, agrupados por
 * Material, com ação de selecionar/desmarcar vencedor).
 */
(function () {
  "use strict";

  function fmt(numero) {
    if (numero === null || numero === undefined) return "—";
    return Number(numero).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  function init() {
    const configEl = document.getElementById("estoque-processo-cotacao-config");
    if (!configEl) return;
    const config = TesseractData.config("estoque-processo-cotacao-config");

    initAbaCotacoes(config);
    initAbaComparacao(config);
  }

  // ═══ Aba Cotações ═══════════════════════════════════════════════
  function initAbaCotacoes(config) {
    const tabelaEl = document.querySelector("#aba-cotacoes table[data-datatable]");
    const tbody = document.querySelector("[data-alvo='tabela-cotacoes']");
    const modalCotacaoEl = document.getElementById("modalCotacao");
    const modalCotacao = window.bootstrap ? new window.bootstrap.Modal(modalCotacaoEl) : null;
    const fornecedorHidden = modalCotacaoEl.querySelector("[data-campo='fornecedor_id']");
    let datatableInstancia = null;
    let cacheCotacoes = [];

    function linhaHtml(cotacao) {
      return (
        "<tr data-id=\"" + cotacao.id + "\">" +
        "<td>" + TesseractData.esc(cotacao.numero || "—") + "</td>" +
        "<td>" + TesseractData.esc(cotacao.fornecedor_nome || ("Fornecedor #" + cotacao.fornecedor_id)) + "</td>" +
        "<td>" + TesseractData.esc(cotacao.status) + "</td>" +
        "<td>" + (cotacao.prazo_entrega_dias ?? "—") + "</td>" +
        "<td class=\"text-end\">" +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-primary\" data-acao=\"itens-cotacao\" data-id=\"" + cotacao.id + "\">Itens</button>" +
        "</td></tr>"
      );
    }

    async function carregar() {
      try {
        const url = config.apiBaseCotacoes + "/?processo_cotacao_id=" + encodeURIComponent(config.processoCotacaoId);
        const dado = await TesseractData._json(url);
        cacheCotacoes = dado.items || [];

        const fornecedorIds = [...new Set(cacheCotacoes.map((c) => c.fornecedor_id))];
        const fornecedores = await Promise.all(
          fornecedorIds.map((id) => TesseractData._json("/api/estoque/fornecedores/" + id).catch(() => null))
        );
        const porId = {};
        fornecedorIds.forEach((id, i) => { porId[id] = fornecedores[i] ? fornecedores[i].item : null; });
        cacheCotacoes.forEach((c) => { c.fornecedor_nome = porId[c.fornecedor_id] ? porId[c.fornecedor_id].razao_social : null; });

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = cacheCotacoes.length
          ? cacheCotacoes.map(linhaHtml).join("")
          : '<tr><td colspan="5" class="text-muted">Nenhum fornecedor convidado ainda.</td></tr>';

        if (window.simpleDatatables && cacheCotacoes.length) {
          datatableInstancia = new window.simpleDatatables.DataTable(tabelaEl, {
            searchable: true, fixedHeight: false, perPage: 10, perPageSelect: [10, 25],
            labels: { placeholder: "Buscar…", perPage: "{select} por página", noRows: "Nenhum registro encontrado", info: "Mostrando {start} a {end} de {rows}" },
          });
          tabelaEl.dataset.datatableIniciado = "1";
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-danger">Erro ao carregar cotações: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    document.querySelector("[data-acao='nova-cotacao']").addEventListener("click", function () {
      fornecedorHidden.value = "";
      modalCotacaoEl.querySelector(".weakref-combo-search").value = "";
      modalCotacaoEl.querySelector("[data-campo='condicao_pagamento']").value = "";
      modalCotacaoEl.querySelector("[data-campo='prazo_entrega_dias']").value = "";
      modalCotacaoEl.querySelector("[data-alvo='erro-cotacao']").classList.add("d-none");
    });

    document.querySelector("[data-acao='salvar-cotacao']").addEventListener("click", async function () {
      const erroEl = modalCotacaoEl.querySelector("[data-alvo='erro-cotacao']");
      erroEl.classList.add("d-none");
      if (!fornecedorHidden.value) {
        erroEl.textContent = "Selecione um fornecedor.";
        erroEl.classList.remove("d-none");
        return;
      }
      try {
        await TesseractData.rest.criar(config.apiBaseCotacoes, {
          processo_cotacao_id: config.processoCotacaoId,
          fornecedor_id: Number(fornecedorHidden.value),
          condicao_pagamento: modalCotacaoEl.querySelector("[data-campo='condicao_pagamento']").value,
          prazo_entrega_dias: modalCotacaoEl.querySelector("[data-campo='prazo_entrega_dias']").value || null,
        });
        modalCotacao && modalCotacao.hide();
        await carregar();
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });

    document.addEventListener("click", function (evt) {
      const botao = evt.target.closest("[data-acao='itens-cotacao']");
      if (botao) {
        const cotacao = cacheCotacoes.find((c) => String(c.id) === botao.dataset.id);
        if (cotacao) abrirModalItens(config, cotacao);
      }
    });

    carregar();
    // Recarrega a lista de cotações quando um item é salvo (subtotal
    // pode ter mudado a exibição, e cobre o caso de reabrir a aba).
    document.addEventListener("estoque:item-cotacao-salvo", carregar);
  }

  // ═══ Sub-modal: Itens de uma Cotacao específica ═══════════════════
  function abrirModalItens(config, cotacao) {
    const modalEl = document.getElementById("modalItensCotacao");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const tbody = modalEl.querySelector("[data-alvo='tabela-itens-cotacao']");
    const selectUnidade = modalEl.querySelector("[data-campo='material_unidade_id']");
    const materialCombo = modalEl.querySelector(".weakref-combo[data-weakref-source='materials']");
    const materialHidden = materialCombo.querySelector(".weakref-combo-value");
    let cacheItens = [];

    modalEl.querySelector("[data-alvo='titulo-cotacao-numero']").textContent = cotacao.numero || ("#" + cotacao.id);

    function linhaHtml(item) {
      return (
        "<tr data-id=\"" + item.id + "\">" +
        "<td>" + TesseractData.esc(item.material_nome || ("#" + item.material_id)) + "</td>" +
        "<td>" + fmt(item.quantidade) + "</td>" +
        "<td>" + TesseractData.esc(item.unidade_nome || "") + "</td>" +
        "<td>" + fmt(item.preco_unitario) + "</td>" +
        "<td>" + fmt(item.subtotal) + "</td>" +
        "<td><button type=\"button\" class=\"btn btn-sm btn-outline-danger\" data-acao=\"remover-item-cotacao\" data-id=\"" + item.id + "\"><i class=\"bi bi-trash\"></i></button></td>" +
        "</tr>"
      );
    }

    async function carregarItens() {
      try {
        const dado = await TesseractData._json(config.apiBaseItens + "/?cotacao_id=" + cotacao.id);
        cacheItens = dado.items || [];
        const materialIds = [...new Set(cacheItens.map((i) => i.material_id))];
        const unidadeIds = [...new Set(cacheItens.map((i) => i.material_unidade_id))];
        const [materiais, unidades] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(unidadeIds.map((id) => TesseractData._json(config.apiBaseUnidades + "/" + id).catch(() => null))),
        ]);
        const materialPorId = {}; materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const unidadePorId = {}; unidadeIds.forEach((id, i) => { unidadePorId[id] = unidades[i] ? unidades[i].item : null; });
        cacheItens.forEach((item) => {
          item.material_nome = materialPorId[item.material_id] ? materialPorId[item.material_id].nome : null;
          item.unidade_nome = unidadePorId[item.material_unidade_id] ? unidadePorId[item.material_unidade_id].unidade : null;
        });
        tbody.innerHTML = cacheItens.length ? cacheItens.map(linhaHtml).join("") : '<tr><td colspan="6" class="text-muted">Nenhum item ainda.</td></tr>';
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-danger">' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    async function carregarUnidades(materialId) {
      selectUnidade.innerHTML = '<option value="">Carregando…</option>';
      selectUnidade.disabled = true;
      if (!materialId) {
        selectUnidade.innerHTML = '<option value="">— escolha o Material —</option>';
        return;
      }
      const dado = await TesseractData._json(config.apiBaseUnidades + "/?material_id=" + materialId).catch(() => ({ items: [] }));
      const unidades = dado.items || [];
      selectUnidade.innerHTML = unidades.length
        ? unidades.map((u) => "<option value=\"" + u.id + "\">" + TesseractData.esc(u.unidade) + (u.is_unidade_base ? " (base)" : "") + "</option>").join("")
        : '<option value="">Nenhuma unidade cadastrada</option>';
      selectUnidade.disabled = !unidades.length;
    }

    function limparFormItem() {
      modalEl.querySelector("[data-campo='item-id']").value = "";
      materialHidden.value = "";
      materialCombo.querySelector(".weakref-combo-search").value = "";
      modalEl.querySelector("[data-campo='quantidade']").value = "";
      modalEl.querySelector("[data-campo='preco_unitario']").value = "";
      modalEl.querySelector("[data-alvo='erro-item-cotacao']").classList.add("d-none");
      carregarUnidades(null);
    }

    async function salvarItem() {
      const erroEl = modalEl.querySelector("[data-alvo='erro-item-cotacao']");
      erroEl.classList.add("d-none");
      const materialId = materialHidden.value;
      const unidadeId = selectUnidade.value;
      const quantidade = modalEl.querySelector("[data-campo='quantidade']").value;
      const preco = modalEl.querySelector("[data-campo='preco_unitario']").value;
      if (!materialId || !unidadeId || !quantidade || !preco) {
        erroEl.textContent = "Preencha Material, Unidade, Quantidade e Preço.";
        erroEl.classList.remove("d-none");
        return;
      }
      try {
        await TesseractData.rest.criar(config.apiBaseItens, {
          cotacao_id: cotacao.id, material_id: Number(materialId), material_unidade_id: Number(unidadeId),
          quantidade: Number(quantidade), preco_unitario: Number(preco),
        });
        limparFormItem();
        await carregarItens();
        document.dispatchEvent(new CustomEvent("estoque:item-cotacao-salvo"));
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    }

    // Listeners re-atribuídos a cada abertura (modal reaproveitado
    // entre Cotacoes diferentes) — remove antes de adicionar de novo
    // pra não empilhar handlers.
    const botaoNovo = modalEl.querySelector("[data-acao='novo-item-cotacao']");
    const botaoSalvar = modalEl.querySelector("[data-acao='salvar-item-cotacao']");
    const novoNovo = botaoNovo.cloneNode(true);
    const novoSalvar = botaoSalvar.cloneNode(true);
    botaoNovo.replaceWith(novoNovo);
    botaoSalvar.replaceWith(novoSalvar);
    novoNovo.addEventListener("click", limparFormItem);
    novoSalvar.addEventListener("click", salvarItem);

    materialCombo.addEventListener("click", function (evt) {
      if (evt.target.closest(".weakref-combo-results li")) {
        carregarUnidades(materialHidden.value || null);
      }
    });

    tbody.addEventListener("click", async function (evt) {
      const botaoRemover = evt.target.closest("[data-acao='remover-item-cotacao']");
      if (botaoRemover && window.confirm("Remover este item?")) {
        await TesseractData.rest.lixeira(config.apiBaseItens, botaoRemover.dataset.id);
        await carregarItens();
        document.dispatchEvent(new CustomEvent("estoque:item-cotacao-salvo"));
      }
    });

    limparFormItem();
    carregarItens();
    modal && modal.show();
  }

  // ═══ Aba Comparação ═══════════════════════════════════════════════
  function initAbaComparacao(config) {
    const tabelaEl = document.querySelector("#aba-comparacao table[data-datatable]");
    const tbody = document.querySelector("[data-alvo='tabela-comparacao']");
    let datatableInstancia = null;

    function linhaHtml(item) {
      if (item.pedido_compra_item_id) {
        return (
          "<tr data-id=\"" + item.id + "\" class=\"table-secondary\">" +
          "<td>" + TesseractData.esc(item.material_nome || ("#" + item.material_id)) + "</td>" +
          "<td>" + TesseractData.esc(item.fornecedor_nome || "") + "</td>" +
          "<td>" + fmt(item.quantidade) + "</td>" +
          "<td>" + fmt(item.preco_unitario) + "</td>" +
          "<td>" + fmt(item.subtotal) + "</td>" +
          "<td>" + (item.prazo_entrega_dias ?? "—") + "</td>" +
          "<td><span class=\"badge bg-secondary\"><i class=\"bi bi-box-seam\"></i> Já gerado</span></td></tr>"
        );
      }
      const vencedorBtn = item.selecionado_como_vencedor
        ? "<button type=\"button\" class=\"btn btn-sm btn-success\" data-acao=\"desmarcar-vencedor\" data-id=\"" + item.id + "\"><i class=\"bi bi-check-circle-fill\"></i> Vencedor</button>"
        : "<button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-acao=\"selecionar-vencedor\" data-id=\"" + item.id + "\">Selecionar</button>";
      return (
        "<tr data-id=\"" + item.id + "\"" + (item.selecionado_como_vencedor ? " class=\"table-success\"" : "") + ">" +
        "<td>" + TesseractData.esc(item.material_nome || ("#" + item.material_id)) + "</td>" +
        "<td>" + TesseractData.esc(item.fornecedor_nome || "") + "</td>" +
        "<td>" + fmt(item.quantidade) + "</td>" +
        "<td>" + fmt(item.preco_unitario) + "</td>" +
        "<td>" + fmt(item.subtotal) + "</td>" +
        "<td>" + (item.prazo_entrega_dias ?? "—") + "</td>" +
        "<td>" + vencedorBtn + "</td></tr>"
      );
    }

    async function carregar() {
      try {
        const dado = await TesseractData._json(config.apiBaseItens + "/?processo_cotacao_id=" + config.processoCotacaoId);
        const itens = dado.items || [];

        const materialIds = [...new Set(itens.map((i) => i.material_id))];
        const cotacaoIds = [...new Set(itens.map((i) => i.cotacao_id))];
        const [materiais, cotacoes] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(cotacaoIds.map((id) => TesseractData._json(config.apiBaseCotacoes + "/" + id).catch(() => null))),
        ]);
        const materialPorId = {}; materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const cotacaoPorId = {}; cotacaoIds.forEach((id, i) => { cotacaoPorId[id] = cotacoes[i] ? cotacoes[i].item : null; });

        const fornecedorIds = [...new Set(Object.values(cotacaoPorId).filter(Boolean).map((c) => c.fornecedor_id))];
        const fornecedores = await Promise.all(
          fornecedorIds.map((id) => TesseractData._json("/api/estoque/fornecedores/" + id).catch(() => null))
        );
        const fornecedorPorId = {}; fornecedorIds.forEach((id, i) => { fornecedorPorId[id] = fornecedores[i] ? fornecedores[i].item : null; });

        itens.forEach((item) => {
          const material = materialPorId[item.material_id];
          const cotacao = cotacaoPorId[item.cotacao_id];
          const fornecedor = cotacao ? fornecedorPorId[cotacao.fornecedor_id] : null;
          item.material_nome = material ? material.nome : null;
          item.fornecedor_nome = fornecedor ? fornecedor.razao_social : null;
          item.prazo_entrega_dias = cotacao ? cotacao.prazo_entrega_dias : null;
        });

        // Agrupado por Material (mesmo nome consecutivo) — ordena por
        // nome do Material e, dentro dele, por preço crescente (mais
        // barato primeiro, facilita comparar visualmente).
        itens.sort((a, b) => {
          const nomeA = a.material_nome || "";
          const nomeB = b.material_nome || "";
          if (nomeA !== nomeB) return nomeA.localeCompare(nomeB);
          return (a.preco_unitario || 0) - (b.preco_unitario || 0);
        });

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = itens.length
          ? itens.map(linhaHtml).join("")
          : '<tr><td colspan="7" class="text-muted">Nenhum item cotado ainda — adicione itens nas Cotações antes de comparar.</td></tr>';

        if (window.simpleDatatables && itens.length) {
          datatableInstancia = new window.simpleDatatables.DataTable(tabelaEl, {
            searchable: true, fixedHeight: false, perPage: 15, perPageSelect: [15, 25, 50],
            labels: { placeholder: "Buscar…", perPage: "{select} por página", noRows: "Nenhum registro encontrado", info: "Mostrando {start} a {end} de {rows}" },
          });
          tabelaEl.dataset.datatableIniciado = "1";
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-danger">Erro ao carregar comparação: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    document.addEventListener("click", async function (evt) {
      const selecionar = evt.target.closest("[data-acao='selecionar-vencedor']");
      const desmarcar = evt.target.closest("[data-acao='desmarcar-vencedor']");
      if (selecionar) {
        try {
          await TesseractData._json(config.apiBaseItens + "/" + selecionar.dataset.id + "/selecionar-vencedor", { method: "POST" });
          await carregar();
        } catch (e) {
          TesseractData.aviso(e.message, "error");
        }
      } else if (desmarcar) {
        try {
          await TesseractData._json(config.apiBaseItens + "/" + desmarcar.dataset.id + "/desmarcar-vencedor", { method: "POST" });
          await carregar();
        } catch (e) {
          TesseractData.aviso(e.message, "error");
        }
      }
    });

    document.addEventListener("estoque:item-cotacao-salvo", carregar);

    carregar();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
