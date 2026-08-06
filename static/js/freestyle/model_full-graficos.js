/**
 * static/js/freestyle/model_full-graficos.js
 *
 * Inicialização dos gráficos de /freestyle/full.
 *
 * ApexCharts vem do layout; ECharts é carregado no extra_js da página.
 * Cada gráfico é achado por data-attribute — nenhum id, para o bloco
 * poder ser copiado para outra tela sem colidir.
 *
 * Dado real: troque os arrays fixos por uma chamada de
 * TesseractData (ver /freestyle/consumption) e chame `.updateSeries()`
 * do Apex em vez de recriar o gráfico — recriar vaza memória e perde a
 * animação.
 */
(function () {
  'use strict';

  const alvo = (nome) => document.querySelector('[data-grafico="' + nome + '"]');

  // Deixa o gráfico legível nos dois temas. O layout marca o tema no
  // <body data-theme>, então não dá para fixar cor de texto no código.
  const temaEscuro = document.body.getAttribute('data-theme') === 'dark';
  const corTexto = temaEscuro ? '#e5e7eb' : '#444444';
  const baseTema = { chart: { foreColor: corTexto, toolbar: { show: false } } };

  function apex(elemento, opcoes) {
    if (!elemento || !window.ApexCharts) return null;
    const grafico = new window.ApexCharts(elemento, Object.assign({}, baseTema, opcoes));
    grafico.render();
    return grafico;
  }

  // ── Área ────────────────────────────────────────────────────────
  apex(alvo('area'), {
    series: [
      { name: 'Produção', data: [31, 40, 28, 51, 42, 82, 56] },
      { name: 'Vendas', data: [11, 32, 45, 32, 34, 52, 41] },
    ],
    chart: { height: 300, type: 'area', foreColor: corTexto, toolbar: { show: false } },
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 2 },
    xaxis: { categories: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul'] },
    // Sem isto o eixo Y mostra "31.0000000004" em série com decimal.
    yaxis: { labels: { formatter: (v) => Math.round(v) } },
    tooltip: { theme: temaEscuro ? 'dark' : 'light' },
  });

  // ── Barras ──────────────────────────────────────────────────────
  apex(alvo('barras'), {
    series: [{ name: 'Litros', data: [440, 505, 414, 671, 227] }],
    chart: { type: 'bar', height: 300, foreColor: corTexto, toolbar: { show: false } },
    plotOptions: { bar: { borderRadius: 4, horizontal: false, columnWidth: '45%' } },
    dataLabels: { enabled: false },
    xaxis: { categories: ['Pilsen', 'IPA', 'Weiss', 'Stout', 'Sour'] },
    tooltip: { theme: temaEscuro ? 'dark' : 'light' },
  });

  // ── Rosca ───────────────────────────────────────────────────────
  apex(alvo('rosca'), {
    series: [44, 55, 13, 33],
    chart: { type: 'donut', height: 300, foreColor: corTexto },
    labels: ['Malte', 'Lúpulo', 'Levedura', 'Outros'],
    legend: { position: 'bottom' },
    tooltip: { theme: temaEscuro ? 'dark' : 'light' },
  });

  // ── ECharts ─────────────────────────────────────────────────────
  const alvoEcharts = document.querySelector('[data-grafico-echarts="pizza"]');
  if (alvoEcharts && window.echarts) {
    const grafico = window.echarts.init(alvoEcharts, temaEscuro ? 'dark' : null);
    grafico.setOption({
      // ECharts pinta fundo próprio no tema dark; transparente deixa o
      // card aparecer por trás, como no resto do sistema.
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: { top: 'bottom', textStyle: { color: corTexto } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        itemStyle: { borderRadius: 8, borderColor: 'transparent', borderWidth: 2 },
        label: { color: corTexto },
        data: [
          { value: 1048, name: 'Fermentação' },
          { value: 735, name: 'Maturação' },
          { value: 580, name: 'Envase' },
          { value: 484, name: 'Expedição' },
        ],
      }],
    });
    // ECharts não redimensiona sozinho — sem isto o gráfico fica
    // cortado ao abrir/fechar o menu lateral ou girar o celular.
    window.addEventListener('resize', () => grafico.resize());
  }
})();
