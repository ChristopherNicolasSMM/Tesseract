/**
 * static/js/estoque/material-unidades-embutido.js
 *
 * Grid de Unidades desenhado à mão (fora do CrudGen), embutido no
 * detalhe de Material — correção pós skill 24 (achado do Christopher:
 * "para cadastrar material tem de associar a unidade"). Mesmo padrão
 * de estoque-endereco-embutido.js (Fase 5).
 */
(function () {
  "use strict";

  function fmt(numero) {
    if (numero === null || numero === undefined) return "—";
    return Number(numero).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 4 });
  }

  const TIPO_USO_LABEL = { compra: "Compra", consumo: "Consumo", ambos: "Ambos" };

  function init() {
    const configEl = document.getElementById("estoque-material-unidades-config");
    if (!configEl) return;
    const config = TesseractData.config("estoque-material-unidades-config");

    const tabelaEl = document.querySelector("table[data-datatable]");
    const tbody = document.querySelector("[data-alvo='tabela-unidades']");
    const modalEl = document.getElementById("modalUnidade");
    const modal = window.bootstrap ? new window.bootstrap.Modal(modalEl) : null;
    let datatableInstancia = null;
    let cache = [];

    function linhaHtml(u) {
      const base = u.is_unidade_base
        ? '<span class="badge bg-success">Base</span>'
        : "";
      const ativo = u.ativo
        ? '<span class="badge bg-success">Sim</span>'
        : '<span class="badge bg-secondary">Não</span>';
      return (
        "<tr data-id=\"" + u.id + "\">" +
        "<td>" + TesseractData.esc(u.unidade) + "</td>" +
        "<td>" + fmt(u.fator_para_base) + "</td>" +
        "<td>" + base + "</td>" +
        "<td>" + TesseractData.esc(TIPO_USO_LABEL[u.tipo_uso] || u.tipo_uso) + "</td>" +
        "<td>" + ativo + "</td>" +
        "<td class=\"text-end\">" +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-acao=\"editar-unidade\" data-id=\"" + u.id + "\"><i class=\"bi bi-pencil\"></i></button> " +
        "<button type=\"button\" class=\"btn btn-sm btn-outline-danger\" data-acao=\"remover-unidade\" data-id=\"" + u.id + "\"><i class=\"bi bi-trash\"></i></button>" +
        "</td></tr>"
      );
    }

    async function carregar() {
      try {
        const dado = await TesseractData._json(config.apiBase + "/?material_id=" + config.materialId);
        cache = dado.items || [];

        if (datatableInstancia) {
          datatableInstancia.destroy();
          datatableInstancia = null;
          tabelaEl.dataset.datatableIniciado = "";
        }

        tbody.innerHTML = cache.length
          ? cache.map(linhaHtml).join("")
          : '<tr><td colspan="6" class="text-muted">Nenhuma unidade cadastrada ainda.</td></tr>';

        if (window.simpleDatatables && cache.length) {
          datatableInstancia = new window.simpleDatatables.DataTable(tabelaEl, {
            searchable: false, fixedHeight: false, perPage: 10, perPageSelect: [10, 25],
            labels: { perPage: "{select} por página", noRows: "Nenhum registro encontrado", info: "Mostrando {start} a {end} de {rows}" },
          });
          tabelaEl.dataset.datatableIniciado = "1";
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-danger">Erro ao carregar unidades: ' + TesseractData.esc(e.message) + "</td></tr>";
      }
    }

    function limparModal() {
      modalEl.querySelector("[data-campo='unidade-id']").value = "";
      modalEl.querySelector("[data-campo='unidade']").value = "";
      modalEl.querySelector("[data-campo='fator_para_base']").value = "1";
      modalEl.querySelector("[data-campo='tipo_uso']").value = "ambos";
      modalEl.querySelector("[data-campo='is_unidade_base']").checked = false;
      modalEl.querySelector("[data-campo='ativo']").checked = true;
      modalEl.querySelector("[data-alvo='erro-unidade']").classList.add("d-none");
    }

    function preencherModal(u) {
      modalEl.querySelector("[data-campo='unidade-id']").value = u.id;
      modalEl.querySelector("[data-campo='unidade']").value = u.unidade;
      modalEl.querySelector("[data-campo='fator_para_base']").value = u.fator_para_base;
      modalEl.querySelector("[data-campo='tipo_uso']").value = u.tipo_uso;
      modalEl.querySelector("[data-campo='is_unidade_base']").checked = !!u.is_unidade_base;
      modalEl.querySelector("[data-campo='ativo']").checked = !!u.ativo;
    }

    document.querySelector("[data-acao='nova-unidade']").addEventListener("click", limparModal);

    modalEl.querySelector("[data-acao='salvar-unidade']").addEventListener("click", async function () {
      const erroEl = modalEl.querySelector("[data-alvo='erro-unidade']");
      erroEl.classList.add("d-none");

      const unidade = modalEl.querySelector("[data-campo='unidade']").value.trim();
      const fator = modalEl.querySelector("[data-campo='fator_para_base']").value;
      if (!unidade || !fator) {
        erroEl.textContent = "Preencha Unidade e Fator para Unidade-Base.";
        erroEl.classList.remove("d-none");
        return;
      }

      const payload = {
        material_id: config.materialId,
        unidade: unidade,
        fator_para_base: Number(fator),
        tipo_uso: modalEl.querySelector("[data-campo='tipo_uso']").value,
        is_unidade_base: modalEl.querySelector("[data-campo='is_unidade_base']").checked,
        ativo: modalEl.querySelector("[data-campo='ativo']").checked,
      };

      const unidadeId = modalEl.querySelector("[data-campo='unidade-id']").value;
      try {
        if (unidadeId) {
          await TesseractData.rest.atualizar(config.apiBase, unidadeId, payload);
        } else {
          await TesseractData.rest.criar(config.apiBase, payload);
        }
        modal && modal.hide();
        await carregar();
      } catch (e) {
        erroEl.textContent = e.message;
        erroEl.classList.remove("d-none");
      }
    });

    document.addEventListener("click", function (evt) {
      const botaoEditar = evt.target.closest("[data-acao='editar-unidade']");
      if (botaoEditar) {
        const u = cache.find((x) => String(x.id) === botaoEditar.dataset.id);
        if (u) {
          preencherModal(u);
          modal && modal.show();
        }
        return;
      }
      const botaoRemover = evt.target.closest("[data-acao='remover-unidade']");
      if (botaoRemover) {
        if (window.confirm("Remover esta unidade?")) {
          TesseractData.rest.lixeira(config.apiBase, botaoRemover.dataset.id)
            .then(carregar)
            .catch((e) => TesseractData.aviso(e.message, "error"));
        }
      }
    });

    carregar();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
