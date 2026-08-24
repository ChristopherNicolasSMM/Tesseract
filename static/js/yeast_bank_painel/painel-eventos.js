/**
 * static/js/yeast_bank_painel/painel-eventos.js
 *
 * Aba "Eventos do Banco" do Painel do Yeast Bank (skill 21). Carrega
 * a grid de eventos; selecionar uma linha mostra a cepa (derivada via
 * event.bank_item.strain — não é mais campo próprio do evento desde a
 * skill 21), status em cards, e as contagens de célula daquele item
 * (filtradas client-side, mesmo motivo do painel-cepas.js).
 */
(function () {
  'use strict';

  const cfg = TesseractData.config();
  let todasAsContagens = [];

  function badgeTipo(tipo) {
    const cores = {
      'Starter': 'bg-info',
      'Contagem de Células': 'bg-primary',
      'Descarte': 'bg-danger',
      'Outro': 'bg-secondary',
    };
    return '<span class="badge ' + (cores[tipo] || 'bg-secondary') + '">' + TesseractData.esc(tipo) + '</span>';
  }

  function formatarData(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }

  function linhaEvento(evento) {
    const item = evento.bank_item;
    const cepa = item && item.strain;

    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.innerHTML =
      '<td>' + badgeTipo(evento.event_type) + '</td>' +
      '<td>' + TesseractData.esc(item ? (item.identification || ('#' + item.id)) : '—') + '</td>' +
      '<td>' + TesseractData.esc(cepa ? cepa.name : '—') + '</td>' +
      '<td>' + formatarData(evento.created_at) + '</td>';
    tr.addEventListener('click', function () {
      document.querySelectorAll('#painel-tabela-eventos tbody tr').forEach(function (r) {
        r.classList.remove('table-active');
      });
      tr.classList.add('table-active');
      mostrarDetalheEvento(evento);
    });
    return tr;
  }

  function cardStatus(rotulo, valor, cor) {
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

  function mostrarDetalheEvento(evento) {
    const painel = document.getElementById('painel-evento-detalhe');
    const item = evento.bank_item;

    if (!item) {
      painel.innerHTML = '<p class="text-muted">Este evento não tem um Item do Banco vinculado.</p>';
      return;
    }

    const cepa = item.strain;
    const viabilidade = item.estimated_viability_pct;
    const alertaTexto = [];
    if (item.expiry_alert) alertaTexto.push('validade próxima');
    if (item.low_viability_alert) alertaTexto.push('viabilidade baixa');

    let html = '<div class="row g-2 mb-3">';
    html += cardStatus('Cepa', TesseractData.esc(cepa ? cepa.name : '—'));
    html += cardStatus('Status do Item', TesseractData.esc(item.status || '—'),
      item.status === 'active' ? 'border-success' : 'border-secondary');
    html += cardStatus('Viabilidade Estimada',
      (viabilidade !== null && viabilidade !== undefined ? viabilidade + '%' : '—'),
      alertaTexto.length ? 'border-warning' : '');
    html += cardStatus('Alerta',
      alertaTexto.length ? TesseractData.esc(alertaTexto.join(' + ')) : 'Nenhum',
      alertaTexto.length ? 'border-warning' : 'border-success');
    html += '</div>';

    if (evento.status_before || evento.status_after) {
      html += '<p><strong>Transição:</strong> ' +
        TesseractData.esc(evento.status_before || '—') + ' &rarr; ' +
        TesseractData.esc(evento.status_after || '—') + '</p>';
    }
    if (evento.notes) {
      html += '<p><strong>Observações:</strong> ' + TesseractData.esc(evento.notes) + '</p>';
    }

    const contagens = todasAsContagens.filter(function (c) { return c.bank_item_id === item.id; });
    html += '<h6 class="text-muted mt-3">Contagens deste item</h6>';
    if (contagens.length === 0) {
      html += '<p class="text-muted">Nenhuma contagem registrada ainda.</p>';
    } else {
      html += '<div class="table-responsive"><table class="table table-sm table-striped">' +
        '<thead><tr><th>Data</th><th>Viabilidade</th><th>Contaminado</th></tr></thead><tbody>';
      contagens.forEach(function (c) {
        html += '<tr><td>' + (c.sample_date || '—') + '</td>' +
          '<td>' + (c.viability_percent !== null && c.viability_percent !== undefined ? c.viability_percent + '%' : '—') + '</td>' +
          '<td>' + (c.contamination_detected ? '<span class="text-danger">Sim</span>' : 'Não') + '</td></tr>';
      });
      html += '</tbody></table></div>';
    }

    html += '<a href="/brewstation/yeast-bank-items/' + item.id + '" class="btn btn-sm btn-outline-secondary">' +
      '<i class="bi bi-box-arrow-up-right"></i> Abrir Item do Banco</a>';

    painel.innerHTML = html;
  }

  async function carregar() {
    try {
      const [eventosResp, contagensResp] = await Promise.all([
        TesseractData.rest.listar(cfg.endpoints.bank_events),
        TesseractData.rest.listar(cfg.endpoints.cell_counts),
      ]);
      todasAsContagens = contagensResp.items || [];

      const tbody = document.querySelector('#painel-tabela-eventos tbody');
      tbody.innerHTML = '';
      const eventos = eventosResp.items || [];
      if (eventos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Nenhum evento registrado ainda.</td></tr>';
        return;
      }
      eventos
        .slice()
        .sort(function (a, b) { return (b.created_at || '').localeCompare(a.created_at || ''); })
        .forEach(function (evento) { tbody.appendChild(linhaEvento(evento)); });
    } catch (e) {
      TesseractData.aviso(e.message, 'error');
      document.querySelector('#painel-tabela-eventos tbody').innerHTML =
        '<tr><td colspan="4" class="text-danger">Erro ao carregar: ' + TesseractData.esc(e.message) + '</td></tr>';
    }
  }

  document.addEventListener('DOMContentLoaded', carregar);
})();
