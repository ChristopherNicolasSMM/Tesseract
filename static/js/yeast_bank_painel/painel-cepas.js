/**
 * static/js/yeast_bank_painel/painel-cepas.js
 *
 * Aba "Cepas" do Painel do Yeast Bank (skill 21). Carrega a grid de
 * cepas; selecionar uma linha filtra (client-side — a API não tem
 * filtro por query param ainda, achado registrado na skill 21) a
 * grid de Itens do Banco daquela cepa, mostrando container,
 * dispositivo, posição, tipo e viabilidade — tudo já vem aninhado no
 * to_dict() do item, sem requisição extra por linha.
 *
 * Mini dashboard (feedback de uso real, 2026-08-24): abaixo da grid
 * de itens, um card com agregados da cepa (total/status/viabilidade
 * média) e, ao clicar num item, um card com o detalhe daquele item
 * (última leitura, contagem anterior, estimativa atual, próximo
 * starter) + atalho pra registrar uma nova contagem.
 */
(function () {
  'use strict';

  const cfg = TesseractData.config();
  let todosOsItens = [];
  let todasAsContagens = [];

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
    tr.style.cursor = 'pointer';
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
      '<td class="text-end"><a href="/brewstation/yeast-bank-items/' + item.id + '" class="btn btn-sm btn-outline-secondary" onclick="event.stopPropagation()"><i class="bi bi-pencil"></i></a></td>';
    tr.addEventListener('click', function () {
      document.querySelectorAll('#painel-tabela-itens tbody tr').forEach(function (r) {
        r.classList.remove('table-active');
      });
      tr.classList.add('table-active');
      mostrarDetalheItem(item);
    });
    return tr;
  }

  function cardMini(rotulo, valor, cor) {
    return (
      '<div class="col-6 col-lg-3">' +
        '<div class="card ' + (cor || '') + '">' +
          '<div class="card-body py-2">' +
            '<div class="text-muted small">' + TesseractData.esc(rotulo) + '</div>' +
            '<div class="fs-5">' + valor + '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function mostrarDashboardCepa(itens) {
    const painel = document.getElementById('painel-cepa-dashboard');
    const total = itens.length;
    const ativos = itens.filter(function (i) { return i.status === 'active'; }).length;
    const descartados = itens.filter(function (i) { return i.status === 'discarded'; }).length;
    const contaminados = itens.filter(function (i) { return i.status === 'contaminated'; }).length;

    const comViabilidade = itens.filter(function (i) {
      return i.estimated_viability_pct !== null && i.estimated_viability_pct !== undefined;
    });
    const media = comViabilidade.length
      ? (comViabilidade.reduce(function (soma, i) { return soma + i.estimated_viability_pct; }, 0) / comViabilidade.length)
      : null;

    let html = '<h6 class="text-muted">Resumo da Cepa</h6><div class="row g-2">';
    html += cardMini('Total de Itens', total);
    html += cardMini('Ativos', ativos, 'border-success');
    html += cardMini('Descartados/Contaminados', descartados + contaminados, (descartados + contaminados) ? 'border-danger' : '');
    html += cardMini('Viabilidade Média', media !== null ? media.toFixed(1) + '%' : '—');
    html += '</div>';
    painel.innerHTML = html;
  }

  function mostrarDetalheItem(item) {
    const painel = document.getElementById('painel-item-detalhe');

    const contagensDoItem = todasAsContagens
      .filter(function (c) { return c.bank_item_id === item.id; })
      .slice()
      .sort(function (a, b) { return (b.sample_date || '').localeCompare(a.sample_date || ''); });

    const ultima = contagensDoItem[0];
    const anterior = contagensDoItem[1];

    let html = '<h6 class="text-muted">Item selecionado</h6><div class="row g-2">';
    html += cardMini(
      'Última Leitura',
      ultima ? (ultima.sample_date || '—') + (ultima.viability_percent !== null && ultima.viability_percent !== undefined ? ' (' + ultima.viability_percent + '%)' : '') : 'Nenhuma',
    );
    html += cardMini(
      'Contagem Anterior',
      anterior ? (anterior.sample_date || '—') + (anterior.viability_percent !== null && anterior.viability_percent !== undefined ? ' (' + anterior.viability_percent + '%)' : '') : '—',
    );
    html += cardMini(
      'Estimativa Atual',
      item.estimated_viability_pct !== null && item.estimated_viability_pct !== undefined ? item.estimated_viability_pct + '%' : '—',
    );
    html += cardMini(
      'Próximo Starter',
      item.next_starter_days !== null && item.next_starter_days !== undefined
        ? (item.next_starter_days === 0 ? 'Agora' : 'em ' + item.next_starter_days + ' dia(s)')
        : '—',
      item.next_starter_days === 0 ? 'border-warning' : '',
    );
    html += '</div>';

    // Atalho: registra uma Contagem de Células pra este item sem
    // precisar passar pela aba Eventos — reaproveita o fluxo já
    // pronto (post_create_redirect da skill 21) via form HTML normal.
    html +=
      '<form method="post" action="' + cfg.links.new_event + '" class="mt-2">' +
        '<input type="hidden" name="bank_item_id" value="' + item.id + '">' +
        '<input type="hidden" name="event_type" value="Contagem de Células">' +
        '<button type="submit" class="btn btn-sm btn-outline-primary">' +
          '<i class="bi bi-clipboard-plus"></i> Nova Contagem pra este Item' +
        '</button>' +
      '</form>';

    painel.innerHTML = html;
  }

  function mostrarItensDaCepa(strainId, nomeCepa) {
    const tbody = document.querySelector('#painel-tabela-itens tbody');
    const titulo = document.getElementById('painel-itens-titulo');
    titulo.textContent = 'Itens do Banco — ' + nomeCepa;
    document.getElementById('painel-item-detalhe').innerHTML = '';

    const itens = todosOsItens.filter(function (i) { return i.strain_id === strainId; });

    tbody.innerHTML = '';
    if (itens.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Nenhum item cadastrado pra esta cepa.</td></tr>';
      document.getElementById('painel-cepa-dashboard').innerHTML = '';
      return;
    }
    itens.forEach(function (item) { tbody.appendChild(linhaItem(item)); });
    mostrarDashboardCepa(itens);
  }

  async function carregar() {
    try {
      const [cepasResp, itensResp, contagensResp] = await Promise.all([
        TesseractData.rest.listar(cfg.endpoints.strains),
        TesseractData.rest.listar(cfg.endpoints.bank_items),
        TesseractData.rest.listar(cfg.endpoints.cell_counts),
      ]);
      todosOsItens = itensResp.items || [];
      todasAsContagens = contagensResp.items || [];

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
