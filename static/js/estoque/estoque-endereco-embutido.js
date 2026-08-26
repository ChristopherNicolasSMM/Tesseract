/**
 * static/js/estoque/estoque-endereco-embutido.js
 *
 * Grid de Endereços desenhado à mão (skill 23, Fase 5) — embutido no
 * detalhe de Fornecedor e de Transportadora, em vez de uma tela CRUD
 * própria de FornecedorEndereco/TransportadoraEndereco (removida
 * nesta fase). Um único arquivo serve os dois donos: a diferença
 * (endpoint, nome do campo de FK) vem do bloco de config
 * (`#estoque-endereco-config`, ver skill 18 seção 6 — "Bloco JSON").
 *
 * Fluxo de dado: sempre API REST do CrudGen (skill 17) — nunca
 * renderizado no servidor a partir do banco. A tabela é populada
 * primeiro, `simpleDatatables` é inicializado depois (skill 18,
 * model_full-tabelas.js) — inicializar antes indexaria uma tabela
 * vazia.
 */
(function () {
  "use strict";

  const TIPO_LABEL = {
    cobranca: "Cobrança",
    entrega: "Entrega",
    correspondencia: "Correspondência",
    faturamento: "Faturamento",
    outro: "Outro",
  };

  function init() {
    const config = TesseractData.config("estoque-endereco-config");
    if (!config.apiBase) return; // página sem grid de endereço (não é fornecedor/transportadora)

    const tabelaEl = document.querySelector("table[data-datatable]");
    const tbody = document.querySelector("[data-alvo='tabela-enderecos']");
    const modalEl = document.getElementById("modalEndereco");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    let datatableInstancia = null;

    function linhaHtml(vinculo) {
      const e = vinculo.endereco || {};
      const endStr = [e.logradouro, e.numero, e.bairro, e.cidade && (e.cidade + "/" + e.estado)]
        .filter(Boolean).map(TesseractData.esc).join(", ");
      const principal = vinculo.principal
        ? '<span class="badge bg-success">Principal</span>' : "";
      return (
        "<tr data-id=\"" + vinculo.id + "\">" +
        "<td>" + TesseractData.esc(TIPO_LABEL[vinculo.tipo_endereco] || vinculo.tipo_endereco) + "</td>" +
        "<td>" + endStr + "</td>" +
        "<td>" + principal + "</td>" +
        "<td class=\"text-end\">" +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-acao=\"editar-endereco\" data-id=\"" + vinculo.id + "\"><i class=\"bi bi-pencil\"></i></button> " +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-danger\" data-acao=\"remover-endereco\" data-id=\"" + vinculo.id + "\"><i class=\"bi bi-trash\"></i></button>" +
        "</td></tr>"
      );
    }

    let cache = []; // último GET, usado pro modal de edição sem round-trip novo

    async function carregar() {
      try {
        const url = config.apiBase + "/?" + config.ownerIdField + "=" + encodeURIComponent(config.ownerId);
        const dado = await TesseractData._json(url);
        cache = dado.items || [];

        // A API devolve só endereco_id — o detalhe do endereço em si
        // precisa de um segundo carregamento (a tabela de vínculo é
        // enxuta de propósito, skill 23 seção 4). Busca em paralelo,
        // uma vez por endereco_id distinto.
        const idsUnicos = [...new Set(cache.map((v) => v.endereco_id))];
        const enderecos = await Promise.all(
          idsUnicos.map((id) => TesseractData._json("/api/estoque/enderecos/" + id).catch(() => null))
        );
        const porId = {};
        idsUnicos.forEach((id, i) => { porId[id] = enderecos[i] ? enderecos[i].item : null; });
        cache.forEach((v) => { v.endereco = porId[v.endereco_id]; });

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = cache.length
          ? cache.map(linhaHtml).join("")
          : '<tr><td colspan="4" class="text-muted">Nenhum endereço cadastrado.</td></tr>';

        if (window.simpleDatatables && cache.length) {
          datatableInstancia = new window.simpleDatatables.DataTable(tabelaEl, {
            searchable: true, fixedHeight: false, perPage: 5, perPageSelect: [5, 10, 25],
            labels: { placeholder: "Buscar…", perPage: "{select} por página", noRows: "Nenhum registro encontrado", info: "Mostrando {start} a {end} de {rows}" },
          });
          tabelaEl.dataset.datatableIniciado = "1";
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-danger">Erro ao carregar endereços: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    function limparModal() {
      modalEl.querySelector("[data-campo='vinculo-id']").value = "";
      modalEl.querySelector("[data-campo='endereco_id']").value = "";
      modalEl.querySelector(".weakref-combo-search").value = "";
      modalEl.querySelector("[data-campo='tipo_endereco']").value = "cobranca";
      modalEl.querySelector("[data-campo='principal']").checked = false;
      modalEl.querySelector("[data-campo='observacoes']").value = "";
      modalEl.querySelector("[data-alvo='erro-endereco']").classList.add("d-none");
    }

    function preencherModal(vinculo) {
      modalEl.querySelector("[data-campo='vinculo-id']").value = vinculo.id;
      modalEl.querySelector("[data-campo='endereco_id']").value = vinculo.endereco_id;
      const e = vinculo.endereco || {};
      modalEl.querySelector(".weakref-combo-search").value = [e.logradouro, e.cidade].filter(Boolean).join(", ");
      modalEl.querySelector("[data-campo='tipo_endereco']").value = vinculo.tipo_endereco;
      modalEl.querySelector("[data-campo='principal']").checked = !!vinculo.principal;
      modalEl.querySelector("[data-campo='observacoes']").value = vinculo.observacoes || "";
    }

    async function salvar() {
      const erroEl = modalEl.querySelector("[data-alvo='erro-endereco']");
      erroEl.classList.add("d-none");

      const enderecoId = modalEl.querySelector("[data-campo='endereco_id']").value;
      if (!enderecoId) {
        erroEl.textContent = "Selecione um endereço.";
        erroEl.classList.remove("d-none");
        return;
      }

      const payload = {};
      payload[config.ownerIdField] = config.ownerId;
      payload.endereco_id = Number(enderecoId);
      payload.tipo_endereco = modalEl.querySelector("[data-campo='tipo_endereco']").value;
      payload.principal = modalEl.querySelector("[data-campo='principal']").checked;
      payload.observacoes = modalEl.querySelector("[data-campo='observacoes']").value;

      const vinculoId = modalEl.querySelector("[data-campo='vinculo-id']").value;
      try {
        if (vinculoId) {
          await TesseractData.rest.atualizar(config.apiBase, vinculoId, payload);
        } else {
          await TesseractData.rest.criar(config.apiBase, payload);
        }
        modal && modal.hide();
        await carregar();
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    }

    async function remover(id) {
      if (!window.confirm("Remover este endereço?")) return;
      try {
        await TesseractData.rest.lixeira(config.apiBase, id);
        await carregar();
      } catch (e) {
        TesseractData.aviso(e.message, "error");
      }
    }

    document.querySelector("[data-acao='novo-endereco']").addEventListener("click", limparModal);

    document.addEventListener("click", function (evt) {
      const botaoEditar = evt.target.closest("[data-acao='editar-endereco']");
      if (botaoEditar) {
        const vinculo = cache.find((v) => String(v.id) === botaoEditar.dataset.id);
        if (vinculo) {
          preencherModal(vinculo);
          modal && modal.show();
        }
        return;
      }
      const botaoRemover = evt.target.closest("[data-acao='remover-endereco']");
      if (botaoRemover) {
        remover(botaoRemover.dataset.id);
        return;
      }
      if (evt.target.closest("[data-acao='salvar-endereco']")) {
        salvar();
      }
    });

    carregar();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
