/**
 * static/js/estoque/materials-acoes-em-massa.js
 *
 * Ações em massa a partir da seleção de linhas na lista de Materiais
 * (achado do Christopher): Movimentar Estoque, Criar Cotação, Criar
 * Pedido, Modificação em Massa. 4 modais, cada um com seu próprio
 * fluxo — este arquivo cobre os 4.
 */
(function () {
  "use strict";

  function init() {
    const configEl = document.getElementById("estoque-materials-massa-config");
    if (!configEl) return; // página sem seleção em massa (ex.: outra lista)
    const config = TesseractData.config("estoque-materials-massa-config");

    const barra = document.getElementById("barraAcoesEmMassa");
    const contagemEl = barra.querySelector("[data-alvo='contagem-selecionados']");
    const checkboxTodos = document.getElementById("checkboxSelecionarTodos");

    function checkboxesLinha() {
      return Array.from(document.querySelectorAll(".checkbox-selecionar-material"));
    }

    function selecionados() {
      return checkboxesLinha()
        .filter((cb) => cb.checked)
        .map((cb) => ({ id: Number(cb.dataset.materialId), nome: cb.dataset.materialNome }));
    }

    function atualizarBarra() {
      const n = selecionados().length;
      contagemEl.textContent = n;
      barra.classList.toggle("d-none", n === 0);
      barra.classList.toggle("d-flex", n > 0);
    }

    checkboxTodos.addEventListener("change", function () {
      checkboxesLinha().forEach((cb) => { cb.checked = checkboxTodos.checked; });
      atualizarBarra();
    });
    document.addEventListener("change", function (evt) {
      if (evt.target.classList.contains("checkbox-selecionar-material")) atualizarBarra();
    });

    initMovimentar(config, selecionados);
    initCotacao(config, selecionados);
    initPedido(config, selecionados);
    initModificar(config, selecionados);
  }

  function fmt(numero) {
    if (numero === null || numero === undefined) return "—";
    return Number(numero).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 4 });
  }

  async function unidadesDoMaterial(config, materialId) {
    const dado = await TesseractData._json(config.apiBaseUnidades + "/?material_id=" + materialId).catch(() => ({ items: [] }));
    return dado.items || [];
  }

  function selectUnidadesHtml(unidades, classe) {
    if (!unidades.length) return '<span class="text-danger small">Sem unidade cadastrada</span>';
    return (
      '<select class="form-select form-select-sm ' + classe + '">' +
      unidades.map((u) => "<option value=\"" + u.id + "\">" + TesseractData.esc(u.unidade) + (u.is_unidade_base ? " (base)" : "") + "</option>").join("") +
      "</select>"
    );
  }

  // ═══ 1) Movimentar Estoque ═══════════════════════════════════════
  function initMovimentar(config, selecionados) {
    const modalEl = document.getElementById("modalMovimentarMassa");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const tbody = modalEl.querySelector("[data-alvo='tabela-movimentar-massa']");
    const erroEl = modalEl.querySelector("[data-alvo='erro-movimentar-massa']");
    const resultadoEl = modalEl.querySelector("[data-alvo='resultado-movimentar-massa']");

    document.querySelector("[data-acao-massa='movimentar']").addEventListener("click", function () {
      erroEl.classList.add("d-none");
      resultadoEl.innerHTML = "";
      const itens = selecionados();
      tbody.innerHTML = itens.map((item) =>
        "<tr data-material-id=\"" + item.id + "\">" +
        "<td>" + TesseractData.esc(item.nome) + "</td>" +
        "<td><input type=\"number\" step=\"0.0001\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"quantidade\"></td>" +
        "</tr>"
      ).join("");
      modal && modal.show();
    });

    modalEl.querySelector("[data-acao='confirmar-movimentar-massa']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");
      resultadoEl.innerHTML = "";
      const tipo = document.getElementById("massaMovimentarTipo").value;
      const linhas = Array.from(tbody.querySelectorAll("tr[data-material-id]"))
        .map((tr) => ({
          material_id: Number(tr.dataset.materialId),
          quantidade: tr.querySelector("[data-campo-linha='quantidade']").value,
        }))
        .filter((l) => l.quantidade !== "" && l.quantidade !== null)
        .map((l) => ({ material_id: l.material_id, quantidade: Number(l.quantidade) }));

      if (!linhas.length) {
        erroEl.textContent = "Preencha a quantidade de ao menos um material.";
        erroEl.classList.remove("d-none");
        return;
      }

      try {
        const resposta = await TesseractData._json(
          "/estoque/materials/acoes-em-massa/movimentar",
          { method: "POST", ...TesseractData._corpoJson({ tipo_movimentacao: tipo, itens: linhas }) }
        );
        const falhas = resposta.resultados.filter((r) => !r.sucesso);
        if (falhas.length) {
          resultadoEl.innerHTML = '<div class="alert alert-warning mt-2">' +
            (resposta.resultados.length - falhas.length) + " de " + resposta.resultados.length + " movimentação(ões) aplicada(s). Falhas: " +
            falhas.map((f) => "material #" + f.material_id + " (" + TesseractData.esc(f.erro) + ")").join("; ") +
            "</div>";
        } else {
          TesseractData.aviso("Movimentação registrada para " + resposta.resultados.length + " material(is).", "success");
          modal && modal.hide();
          window.location.reload();
        }
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });
  }

  // ═══ 2) Criar Cotação ═════════════════════════════════════════════
  function initCotacao(config, selecionados) {
    const modalEl = document.getElementById("modalCotacaoMassa");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const tbody = modalEl.querySelector("[data-alvo='tabela-cotacao-massa']");
    const erroEl = modalEl.querySelector("[data-alvo='erro-cotacao-massa']");
    const blocoNovo = document.getElementById("cotacaoMassaBlocoNovo");
    const blocoExistente = document.getElementById("cotacaoMassaBlocoExistente");

    modalEl.querySelectorAll("input[name='cotacaoMassaModo']").forEach((radio) => {
      radio.addEventListener("change", function () {
        const existente = this.value === "existente";
        blocoNovo.classList.toggle("d-none", existente);
        blocoExistente.classList.toggle("d-none", !existente);
      });
    });

    document.querySelector("[data-acao-massa='cotacao']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");
      const itens = selecionados();
      tbody.innerHTML = itens.map((item) =>
        "<tr data-material-id=\"" + item.id + "\">" +
        "<td>" + TesseractData.esc(item.nome) + "</td>" +
        "<td class=\"celula-unidade\">Carregando…</td>" +
        "<td><input type=\"number\" step=\"0.0001\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"quantidade\" value=\"1\"></td>" +
        "</tr>"
      ).join("");
      modal && modal.show();

      // Preenche as unidades depois de abrir (não trava a abertura do modal)
      for (const item of itens) {
        const unidades = await unidadesDoMaterial(config, item.id);
        const linha = tbody.querySelector("tr[data-material-id='" + item.id + "'] .celula-unidade");
        if (linha) linha.innerHTML = selectUnidadesHtml(unidades, "campo-unidade-cotacao");
      }
    });

    modalEl.querySelector("[data-acao='confirmar-cotacao-massa']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");
      const modoExistente = document.getElementById("cotacaoMassaModoExistente").checked;

      const itens = [];
      let erroLinha = null;
      tbody.querySelectorAll("tr[data-material-id]").forEach((tr) => {
        const selectUnidade = tr.querySelector(".campo-unidade-cotacao");
        const quantidade = tr.querySelector("[data-campo-linha='quantidade']").value;
        if (!selectUnidade || !selectUnidade.value) { erroLinha = "Todo material precisa ter uma unidade cadastrada."; return; }
        if (!quantidade) { erroLinha = "Preencha a quantidade desejada de todos os materiais."; return; }
        itens.push({
          material_id: Number(tr.dataset.materialId),
          material_unidade_id: Number(selectUnidade.value),
          quantidade_desejada: Number(quantidade),
        });
      });
      if (erroLinha) { erroEl.textContent = erroLinha; erroEl.classList.remove("d-none"); return; }

      const payload = { itens: itens };
      if (modoExistente) {
        const processoId = document.getElementById("massaCotacaoProcessoId").value;
        if (!processoId) { erroEl.textContent = "Selecione um Processo de Cotação."; erroEl.classList.remove("d-none"); return; }
        payload.processo_cotacao_id = Number(processoId);
      } else {
        const descricao = document.getElementById("massaCotacaoDescricao").value.trim();
        const dataAbertura = document.getElementById("massaCotacaoDataAbertura").value;
        if (!descricao || !dataAbertura) { erroEl.textContent = "Preencha Descrição e Data de Abertura."; erroEl.classList.remove("d-none"); return; }
        payload.novo_processo = { descricao: descricao, data_abertura: dataAbertura };
      }

      try {
        const resposta = await TesseractData._json(
          "/estoque/materials/acoes-em-massa/criar-cotacao",
          { method: "POST", ...TesseractData._corpoJson(payload) }
        );
        TesseractData.aviso("Cotação criada com " + resposta.itens.length + " item(ns).", "success");
        window.location.href = "/estoque/processo-cotacaos/" + resposta.processo_cotacao.id;
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });
  }

  // ═══ 3) Criar Pedido ══════════════════════════════════════════════
  function initPedido(config, selecionados) {
    const modalEl = document.getElementById("modalPedidoMassa");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const tbody = modalEl.querySelector("[data-alvo='tabela-pedido-massa']");
    const erroEl = modalEl.querySelector("[data-alvo='erro-pedido-massa']");
    const blocoNovo = document.getElementById("pedidoMassaBlocoNovo");
    const blocoExistente = document.getElementById("pedidoMassaBlocoExistente");

    modalEl.querySelectorAll("input[name='pedidoMassaModo']").forEach((radio) => {
      radio.addEventListener("change", function () {
        const existente = this.value === "existente";
        blocoNovo.classList.toggle("d-none", existente);
        blocoExistente.classList.toggle("d-none", !existente);
      });
    });

    document.querySelector("[data-acao-massa='pedido']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");
      const itens = selecionados();
      tbody.innerHTML = itens.map((item) =>
        "<tr data-material-id=\"" + item.id + "\">" +
        "<td>" + TesseractData.esc(item.nome) + "</td>" +
        "<td class=\"celula-unidade\">Carregando…</td>" +
        "<td><input type=\"number\" step=\"0.0001\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"quantidade\"></td>" +
        "<td><input type=\"number\" step=\"0.01\" min=\"0\" class=\"form-control form-control-sm\" data-campo-linha=\"preco\"></td>" +
        "</tr>"
      ).join("");
      modal && modal.show();

      for (const item of itens) {
        const unidades = await unidadesDoMaterial(config, item.id);
        const linha = tbody.querySelector("tr[data-material-id='" + item.id + "'] .celula-unidade");
        if (linha) linha.innerHTML = selectUnidadesHtml(unidades, "campo-unidade-pedido");
      }
    });

    modalEl.querySelector("[data-acao='confirmar-pedido-massa']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");
      const modoExistente = document.getElementById("pedidoMassaModoExistente").checked;

      const itens = [];
      let erroLinha = null;
      tbody.querySelectorAll("tr[data-material-id]").forEach((tr) => {
        const selectUnidade = tr.querySelector(".campo-unidade-pedido");
        const quantidade = tr.querySelector("[data-campo-linha='quantidade']").value;
        const preco = tr.querySelector("[data-campo-linha='preco']").value;
        if (!selectUnidade || !selectUnidade.value) { erroLinha = "Todo material precisa ter uma unidade cadastrada."; return; }
        if (!quantidade || !preco) { erroLinha = "Preencha Quantidade e Preço Unitário de todos os materiais."; return; }
        itens.push({
          material_id: Number(tr.dataset.materialId),
          material_unidade_id: Number(selectUnidade.value),
          quantidade: Number(quantidade),
          preco_unitario: Number(preco),
        });
      });
      if (erroLinha) { erroEl.textContent = erroLinha; erroEl.classList.remove("d-none"); return; }

      const payload = { itens: itens };
      if (modoExistente) {
        const pedidoId = document.getElementById("massaPedidoPedidoId").value;
        if (!pedidoId) { erroEl.textContent = "Selecione um Pedido de Compra."; erroEl.classList.remove("d-none"); return; }
        payload.pedido_compra_id = Number(pedidoId);
      } else {
        const fornecedorId = document.getElementById("massaPedidoFornecedorId").value;
        const dataPedido = document.getElementById("massaPedidoDataPedido").value;
        if (!fornecedorId || !dataPedido) { erroEl.textContent = "Preencha Fornecedor e Data do Pedido."; erroEl.classList.remove("d-none"); return; }
        payload.novo_pedido = { fornecedor_id: Number(fornecedorId), data_pedido: dataPedido };
      }

      try {
        const resposta = await TesseractData._json(
          "/estoque/materials/acoes-em-massa/criar-pedido",
          { method: "POST", ...TesseractData._corpoJson(payload) }
        );
        TesseractData.aviso("Pedido criado com " + resposta.itens.length + " item(ns).", "success");
        window.location.href = "/estoque/pedido-compras/" + resposta.pedido_compra.id;
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });
  }

  // ═══ 4) Modificação em Massa ══════════════════════════════════════
  function initModificar(config, selecionados) {
    const modalEl = document.getElementById("modalModificarMassa");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    const erroEl = modalEl.querySelector("[data-alvo='erro-modificar-massa']");
    let idsSelecionadosNoMomentoDaAbertura = [];

    document.querySelector("[data-acao-massa='modificar']").addEventListener("click", function () {
      erroEl.classList.add("d-none");
      idsSelecionadosNoMomentoDaAbertura = selecionados().map((s) => s.id);
      modal && modal.show();
    });

    modalEl.querySelector("[data-acao='confirmar-modificar-massa']").addEventListener("click", async function () {
      erroEl.classList.add("d-none");

      const alteracoes = {};
      const fabricanteId = document.getElementById("massaModFabricanteId").value;
      const origemId = document.getElementById("massaModOrigemId").value;
      const tipoProdutoId = document.getElementById("massaModTipoProdutoId").value;
      const categoriaId = document.getElementById("massaModCategoriaId").value;
      const ativo = document.getElementById("massaModAtivo").value;

      if (fabricanteId) alteracoes.fabricante_id = Number(fabricanteId);
      if (origemId) alteracoes.origem_id = Number(origemId);
      if (tipoProdutoId) alteracoes.tipo_produto_id = Number(tipoProdutoId);
      if (categoriaId) alteracoes.categoria_id = Number(categoriaId);
      if (ativo) alteracoes.ativo = ativo === "true";

      if (!Object.keys(alteracoes).length) {
        erroEl.textContent = "Preencha ao menos um campo pra aplicar.";
        erroEl.classList.remove("d-none");
        return;
      }

      try {
        const resposta = await TesseractData._json(
          "/estoque/materials/acoes-em-massa/modificar",
          { method: "POST", ...TesseractData._corpoJson({ material_ids: idsSelecionadosNoMomentoDaAbertura, alteracoes: alteracoes }) }
        );
        TesseractData.aviso(resposta.atualizados + " material(is) atualizado(s).", "success");
        modal && modal.hide();
        window.location.reload();
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
