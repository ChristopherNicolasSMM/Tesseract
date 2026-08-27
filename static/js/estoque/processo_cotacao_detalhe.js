/**
 * static/js/estoque/processo_cotacao_detalhe.js
 *
 * Detalhe de ProcessoCotacao (skill 24, Fase 6.2 + correção pós-Fase
 * 6.3) — abas desenhadas à mão (fora do CrudGen):
 *
 * "Cotações" — duas seções: Itens Pedidos (Material+quantidade,
 * definidos UMA VEZ no processo — nunca redigitados por fornecedor) e
 * Cotações (um convite por fornecedor; "Responder Preços" abre um
 * modal listando os Itens Pedidos com um campo de preço por linha).
 *
 * "Comparação" — grid único com todos os ItemCotacao do processo,
 * agrupados pelo item pedido (FK real, não mais nome de Material),
 * com ação de selecionar/desmarcar vencedor.
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

    initItensProcesso(config);
    initAbaCotacoes(config);
    initAbaComparacao(config);
  }

  // ═══ Itens Pedidos (Material+quantidade, uma vez no processo) ═══
  function initItensProcesso(config) {
    const tbody = document.querySelector("[data-alvo='tabela-itens-processo']");
    const modalEl = document.getElementById("modalItemProcesso");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const materialCombo = modalEl.querySelector(".weakref-combo[data-weakref-source='materials']");
    const materialHidden = materialCombo.querySelector(".weakref-combo-value");
    const selectUnidade = modalEl.querySelector("[data-campo='ip-material_unidade_id']");
    let cache = [];

    async function carregarUnidades(materialId) {
      selectUnidade.innerHTML = '<option value="">Carregando…</option>';
      selectUnidade.disabled = true;
      if (!materialId) {
        selectUnidade.innerHTML = '<option value="">— escolha o Material primeiro —</option>';
        return;
      }
      const dado = await TesseractData._json(config.apiBaseUnidades + "/?material_id=" + materialId).catch(() => ({ items: [] }));
      const unidades = dado.items || [];
      selectUnidade.innerHTML = unidades.length
        ? unidades.map((u) => "<option value=\"" + u.id + "\">" + TesseractData.esc(u.unidade) + (u.is_unidade_base ? " (base)" : "") + "</option>").join("")
        : '<option value="">Nenhuma unidade cadastrada</option>';
      selectUnidade.disabled = !unidades.length;
    }

    function linhaHtml(item) {
      return (
        "<tr>" +
        "<td>" + TesseractData.esc(item.material_nome || ("#" + item.material_id)) + "</td>" +
        "<td>" + fmt(item.quantidade_desejada) + "</td>" +
        "<td>" + TesseractData.esc(item.unidade_nome || "") + "</td>" +
        "</tr>"
      );
    }

    async function carregar() {
      try {
        const dado = await TesseractData._json(config.apiBaseItensProcesso + "/?processo_cotacao_id=" + config.processoCotacaoId);
        cache = dado.items || [];

        const materialIds = [...new Set(cache.map((i) => i.material_id))];
        const unidadeIds = [...new Set(cache.map((i) => i.material_unidade_id))];
        const [materiais, unidades] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(unidadeIds.map((id) => TesseractData._json(config.apiBaseUnidades + "/" + id).catch(() => null))),
        ]);
        const materialPorId = {}; materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const unidadePorId = {}; unidadeIds.forEach((id, i) => { unidadePorId[id] = unidades[i] ? unidades[i].item : null; });
        cache.forEach((item) => {
          item.material_nome = materialPorId[item.material_id] ? materialPorId[item.material_id].nome : null;
          item.unidade_nome = unidadePorId[item.material_unidade_id] ? unidadePorId[item.material_unidade_id].unidade : null;
        });

        tbody.innerHTML = cache.length
          ? cache.map(linhaHtml).join("")
          : '<tr><td colspan="3" class="text-muted">Nenhum item pedido ainda.</td></tr>';
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-danger">Erro: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    document.querySelector("[data-acao='novo-item-processo']").addEventListener("click", function () {
      materialHidden.value = "";
      materialCombo.querySelector(".weakref-combo-search").value = "";
      modalEl.querySelector("[data-campo='ip-quantidade_desejada']").value = "";
      modalEl.querySelector("[data-alvo='erro-item-processo']").classList.add("d-none");
      carregarUnidades(null);
    });

    materialCombo.addEventListener("click", function (evt) {
      if (evt.target.closest(".weakref-combo-results li")) {
        carregarUnidades(materialHidden.value || null);
      }
    });

    modalEl.querySelector("[data-acao='salvar-item-processo']").addEventListener("click", async function () {
      const erroEl = modalEl.querySelector("[data-alvo='erro-item-processo']");
      erroEl.classList.add("d-none");
      const materialId = materialHidden.value;
      const unidadeId = selectUnidade.value;
      const quantidade = modalEl.querySelector("[data-campo='ip-quantidade_desejada']").value;
      if (!materialId || !unidadeId || !quantidade) {
        erroEl.textContent = "Preencha Material, Unidade e Quantidade Desejada.";
        erroEl.classList.remove("d-none");
        return;
      }
      try {
        await TesseractData.rest.criar(config.apiBaseItensProcesso, {
          processo_cotacao_id: config.processoCotacaoId,
          material_id: Number(materialId), material_unidade_id: Number(unidadeId),
          quantidade_desejada: Number(quantidade),
        });
        modal && modal.hide();
        await carregar();
        document.dispatchEvent(new CustomEvent("estoque:item-processo-salvo"));
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });

    carregar();
  }

  // ═══ Aba Cotações (convites por fornecedor) ═══════════════════════
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
        "<button type=\"button\" class=\"btn btn-sm btn-outline-primary\" data-acao=\"itens-cotacao\" data-id=\"" + cotacao.id + "\">Responder Preços</button>" +
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

    modalCotacaoEl.querySelector("[data-acao='salvar-cotacao']").addEventListener("click", async function () {
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
        if (cotacao) abrirModalResponderPrecos(config, cotacao);
      }
    });

    carregar();
    document.addEventListener("estoque:item-processo-salvo", carregar); // recarrega prazo/status se algo mudou
    document.addEventListener("estoque:item-cotacao-salvo", carregar);
  }

  // ═══ Sub-modal: Responder Preços de uma Cotacao específica ═══════
  function abrirModalResponderPrecos(config, cotacao) {
    const modalEl = document.getElementById("modalItensCotacao");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const tbody = modalEl.querySelector("[data-alvo='tabela-itens-cotacao']");
    const erroEl = modalEl.querySelector("[data-alvo='erro-item-cotacao']");

    modalEl.querySelector("[data-alvo='titulo-cotacao-numero']").textContent = cotacao.numero || ("#" + cotacao.id);

    function linhaHtml(itemPedido, resposta) {
      const precoValor = resposta ? resposta.preco_unitario : "";
      const qtdOfertadaValor = resposta && resposta.quantidade_ofertada !== null && resposta.quantidade_ofertada !== undefined
        ? resposta.quantidade_ofertada : "";
      return (
        "<tr data-item-processo-id=\"" + itemPedido.id + "\"" + (resposta ? " data-item-cotacao-id=\"" + resposta.id + "\"" : "") + ">" +
        "<td>" + TesseractData.esc(itemPedido.material_nome || ("#" + itemPedido.material_id)) + "</td>" +
        "<td>" + fmt(itemPedido.quantidade_desejada) + "</td>" +
        "<td>" + TesseractData.esc(itemPedido.unidade_nome || "") + "</td>" +
        "<td><input type=\"number\" step=\"0.01\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"preco\" value=\"" + precoValor + "\"></td>" +
        "<td><input type=\"number\" step=\"0.001\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"qtd-ofertada\" placeholder=\"" + itemPedido.quantidade_desejada + "\" value=\"" + qtdOfertadaValor + "\"></td>" +
        "<td><button type=\"button\" class=\"btn btn-sm btn-primary\" data-acao=\"salvar-linha-resposta\">Salvar</button></td>" +
        "</tr>"
      );
    }

    async function carregar() {
      try {
        const [itensPedidosDado, respostasDado] = await Promise.all([
          TesseractData._json(config.apiBaseItensProcesso + "/?processo_cotacao_id=" + config.processoCotacaoId),
          TesseractData._json(config.apiBaseItens + "/?cotacao_id=" + cotacao.id),
        ]);
        const itensPedidos = itensPedidosDado.items || [];
        const respostas = respostasDado.items || [];
        const respostaPorItemPedido = {};
        respostas.forEach((r) => { respostaPorItemPedido[r.item_processo_cotacao_id] = r; });

        const materialIds = [...new Set(itensPedidos.map((i) => i.material_id))];
        const unidadeIds = [...new Set(itensPedidos.map((i) => i.material_unidade_id))];
        const [materiais, unidades] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(unidadeIds.map((id) => TesseractData._json(config.apiBaseUnidades + "/" + id).catch(() => null))),
        ]);
        const materialPorId = {}; materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const unidadePorId = {}; unidadeIds.forEach((id, i) => { unidadePorId[id] = unidades[i] ? unidades[i].item : null; });
        itensPedidos.forEach((i) => {
          i.material_nome = materialPorId[i.material_id] ? materialPorId[i.material_id].nome : null;
          i.unidade_nome = unidadePorId[i.material_unidade_id] ? unidadePorId[i.material_unidade_id].unidade : null;
        });

        tbody.innerHTML = itensPedidos.length
          ? itensPedidos.map((i) => linhaHtml(i, respostaPorItemPedido[i.id])).join("")
          : '<tr><td colspan="6" class="text-muted">Nenhum item pedido neste processo ainda — adicione na seção "Itens Pedidos".</td></tr>';
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-danger">' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    tbody.addEventListener("click", async function (evt) {
      const botao = evt.target.closest("[data-acao='salvar-linha-resposta']");
      if (!botao) return;
      erroEl.classList.add("d-none");

      const linha = botao.closest("tr");
      const itemProcessoId = linha.dataset.itemProcessoId;
      const itemCotacaoId = linha.dataset.itemCotacaoId;
      const preco = linha.querySelector("[data-campo-linha='preco']").value;
      const qtdOfertada = linha.querySelector("[data-campo-linha='qtd-ofertada']").value;

      if (!preco) {
        erroEl.textContent = "Preencha o preço unitário.";
        erroEl.classList.remove("d-none");
        return;
      }

      const payload = {
        cotacao_id: cotacao.id,
        item_processo_cotacao_id: Number(itemProcessoId),
        preco_unitario: Number(preco),
        quantidade_ofertada: qtdOfertada ? Number(qtdOfertada) : null,
      };

      try {
        if (itemCotacaoId) {
          await TesseractData.rest.atualizar(config.apiBaseItens, itemCotacaoId, payload);
        } else {
          await TesseractData.rest.criar(config.apiBaseItens, payload);
        }
        await carregar();
        document.dispatchEvent(new CustomEvent("estoque:item-cotacao-salvo"));
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });

    carregar();
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

        // Correção pós-Fase 6.3: material/unidade não vêm mais direto
        // no ItemCotacao — busca via item_processo_cotacao_id.
        const itemProcessoIds = [...new Set(itens.map((i) => i.item_processo_cotacao_id))];
        const cotacaoIds = [...new Set(itens.map((i) => i.cotacao_id))];
        const [itensProcesso, cotacoes] = await Promise.all([
          Promise.all(itemProcessoIds.map((id) => TesseractData._json(config.apiBaseItensProcesso + "/" + id).catch(() => null))),
          Promise.all(cotacaoIds.map((id) => TesseractData._json(config.apiBaseCotacoes + "/" + id).catch(() => null))),
        ]);
        const itemProcessoPorId = {}; itemProcessoIds.forEach((id, i) => { itemProcessoPorId[id] = itensProcesso[i] ? itensProcesso[i].item : null; });
        const cotacaoPorId = {}; cotacaoIds.forEach((id, i) => { cotacaoPorId[id] = cotacoes[i] ? cotacoes[i].item : null; });

        const materialIds = [...new Set(Object.values(itemProcessoPorId).filter(Boolean).map((ip) => ip.material_id))];
        const fornecedorIds = [...new Set(Object.values(cotacaoPorId).filter(Boolean).map((c) => c.fornecedor_id))];
        const [materiais, fornecedores] = await Promise.all([
          Promise.all(materialIds.map((id) => TesseractData._json("/api/estoque/materials/" + id).catch(() => null))),
          Promise.all(fornecedorIds.map((id) => TesseractData._json("/api/estoque/fornecedores/" + id).catch(() => null))),
        ]);
        const materialPorId = {}; materialIds.forEach((id, i) => { materialPorId[id] = materiais[i] ? materiais[i].item : null; });
        const fornecedorPorId = {}; fornecedorIds.forEach((id, i) => { fornecedorPorId[id] = fornecedores[i] ? fornecedores[i].item : null; });

        itens.forEach((item) => {
          const itemProcesso = itemProcessoPorId[item.item_processo_cotacao_id];
          const cotacao = cotacaoPorId[item.cotacao_id];
          const material = itemProcesso ? materialPorId[itemProcesso.material_id] : null;
          const fornecedor = cotacao ? fornecedorPorId[cotacao.fornecedor_id] : null;
          item.material_id = itemProcesso ? itemProcesso.material_id : item.material_id;
          item.material_nome = material ? material.nome : null;
          item.fornecedor_nome = fornecedor ? fornecedor.razao_social : null;
          item.prazo_entrega_dias = cotacao ? cotacao.prazo_entrega_dias : null;
        });

        // Agrupado por item pedido (nome do Material, já garantido ser
        // o mesmo item_processo_cotacao_id) e, dentro dele, por preço
        // crescente — mais barato primeiro, facilita comparar.
        itens.sort((a, b) => {
          if (a.item_processo_cotacao_id !== b.item_processo_cotacao_id) {
            return (a.material_nome || "").localeCompare(b.material_nome || "");
          }
          return (a.preco_unitario || 0) - (b.preco_unitario || 0);
        });

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = itens.length
          ? itens.map(linhaHtml).join("")
          : '<tr><td colspan="7" class="text-muted">Nenhum item cotado ainda — responda preços nas Cotações antes de comparar.</td></tr>';

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
