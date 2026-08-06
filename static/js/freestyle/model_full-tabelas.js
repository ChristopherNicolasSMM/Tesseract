/**
 * static/js/freestyle/model_full-tabelas.js
 *
 * Simple DataTables (busca, ordenação e paginação no cliente).
 *
 * A lib vem do layout, mas NÃO se inicializa sozinha aqui — o
 * auto-init por classe `.datatable` existe no main.js dos arquivos de
 * referência do NiceAdmin, que este projeto não usa. Inicializar
 * explicitamente é melhor: você controla quando, e pode popular o
 * <tbody> com dado do servidor ANTES de indexar.
 */
(function () {
  'use strict';

  if (!window.simpleDatatables) return;

  document.querySelectorAll('[data-datatable]').forEach(function (tabela) {
    // Guarda contra dupla inicialização: se a tela recarregar a tabela
    // por AJAX e chamar isto de novo, a lib duplica os controles.
    if (tabela.dataset.datatableIniciado === '1') return;
    tabela.dataset.datatableIniciado = '1';

    new window.simpleDatatables.DataTable(tabela, {
      searchable: true,
      fixedHeight: false,
      perPage: 5,
      perPageSelect: [5, 10, 25],
      // A lib é em inglês por padrão.
      labels: {
        placeholder: 'Buscar…',
        perPage: '{select} registros por página',
        noRows: 'Nenhum registro encontrado',
        info: 'Mostrando {start} a {end} de {rows} registros',
      },
    });
  });

  /**
   * Para popular com dado do servidor, o caminho é este — popular
   * primeiro, indexar depois:
   *
   *   const dado = await TesseractData.rest.listar(base);
   *   tabela.querySelector('tbody').innerHTML = dado.items
   *     .map(r => `<tr><td>${TesseractData.esc(r.name)}</td></tr>`).join('');
   *   new simpleDatatables.DataTable(tabela);
   *
   * Inicializar antes faz a lib indexar uma tabela vazia: a busca e a
   * ordenação passam a ignorar as linhas que chegaram depois.
   */
})();
