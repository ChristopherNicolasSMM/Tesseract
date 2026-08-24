/**
 * static/js/yeast_bank_painel/painel-cepas.js
 *
 * Aba "Cepas" do Painel do Yeast Bank (skill 21). Carrega a grid de
 * cepas; selecionar uma linha filtra (client-side — a API não tem
 * filtro por query param ainda, achado registrado na skill 21) a
 * grid de Itens do Banco daquela cepa, mostrando container,
 * dispositivo, posição, tipo e viabilidade — tudo já vem aninhado no
 * to_dict() do item, sem requisição extra por linha.
 */
(function () {
  'use strict';

  const cfg = TesseractData.config();
  let todosOsItens = [];

  function linhaCepa(cepa) {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.dataset.cepaId = cepa.id;
    tr.innerHTML =
      '<td>' + TesseractData.esc(cepa.name) + '</td>' +
      '<td>' + TesseractData.esc(cepa.family || '—') + '</td>' +
      '<td>' + TesseractData.esc(cepa.status || '—') + '</td>';
    tr.addEventListener('click', function () {
      document.querySelectorAll('#painel-tabela-cepas tbody tr').forEach(function (r) {
        r.classList.remove('table-active');
      });
      tr.classList.add('table-active');
      mostrarItensDaCepa(cepa.id, cepa.name);
    });
    return tr;
  }

  function linhaItem(item) {
    const container = item.container;
    const dispositivo = container && container.device;
    const viabilidade = item.estimated_viability_pct;
    const alerta = item.expiry_alert || item.low_viability_alert;

    const tr = document.createElement('tr');
    if (alerta) tr.classList.add('table-warning');
    tr.innerHTML =
      '<td>' + TesseractData.esc(container ? container.name : '—') + '</td>' +
      '<td>' + TesseractData.esc(dispositivo ? dispositivo.name : '—') + '</td>' +
      '<td>' + TesseractData.esc(item.storage_slot || '—') + '</td>' +
      '<td>' + TesseractData.esc(item.storage_type || '—') + '</td>' +
      '<td>' + (viabilidade !== null && viabilidade !== undefined ? viabilidade + '%' : '—') +
        (alerta ? ' <i class="bi bi-exclamation-triangle-fill text-warning" title="Alerta de validade/viabilidade"></i>' : '') +
      '</td>' +
      '<td>' + TesseractData.esc(item.status || '—') + '</td>' +
      '<td class="text-end"><a href="/brewstation/yeast-bank-items/' + item.id + '" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a></td>';
    return tr;
  }

  function mostrarItensDaCepa(strainId, nomeCepa) {
    const tbody = document.querySelector('#painel-tabela-itens tbody');
    const titulo = document.getElementById('painel-itens-titulo');
    titulo.textContent = 'Itens do Banco — ' + nomeCepa;

    const itens = todosOsItens.filter(function (i) { return i.strain_id === strainId; });

    tbody.innerHTML = '';
    if (itens.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Nenhum item cadastrado pra esta cepa.</td></tr>';
      return;
    }
    itens.forEach(function (item) { tbody.appendChild(linhaItem(item)); });
  }

  async function carregar() {
    try {
      const [cepasResp, itensResp] = await Promise.all([
        TesseractData.rest.listar(cfg.endpoints.strains),
        TesseractData.rest.listar(cfg.endpoints.bank_items),
      ]);
      todosOsItens = itensResp.items || [];

      const tbodyCepas = document.querySelector('#painel-tabela-cepas tbody');
      tbodyCepas.innerHTML = '';
      const cepas = cepasResp.items || [];
      if (cepas.length === 0) {
        tbodyCepas.innerHTML = '<tr><td colspan="3" class="text-muted">Nenhuma cepa cadastrada.</td></tr>';
        return;
      }
      cepas.forEach(function (cepa) { tbodyCepas.appendChild(linhaCepa(cepa)); });
    } catch (e) {
      TesseractData.aviso(e.message, 'error');
      document.querySelector('#painel-tabela-cepas tbody').innerHTML =
        '<tr><td colspan="3" class="text-danger">Erro ao carregar: ' + TesseractData.esc(e.message) + '</td></tr>';
    }
  }

  document.addEventListener('DOMContentLoaded', carregar);
})();
