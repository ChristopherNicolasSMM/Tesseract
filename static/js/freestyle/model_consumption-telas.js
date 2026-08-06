/**
 * static/js/freestyle/model_consumption-telas.js
 *
 * As quatro seções de /freestyle/consumption. Cada uma é uma função
 * isolada — a intenção é você copiar só a que precisa.
 *
 * Depende de freestyle-tesseract-data.js (carregado antes no template).
 * Endpoints vêm do bloco de config gerado pelo controller, nunca
 * hardcoded aqui.
 */
(function (window) {
  'use strict';

  const T = window.TesseractData;
  const cfg = T.config();
  const esc = T.esc.bind(T);

  // Seletores por data-attribute em vez de id: o HTML pode ser copiado
  // pra outra tela sem colidir com ids já existentes lá.
  const alvo = (nome) => document.querySelector('[data-alvo="' + nome + '"]');
  const campo = (nome) => document.querySelector('[data-campo="' + nome + '"]');

  // Estado compartilhado entre a lista e os indicadores — evita uma
  // segunda chamada só pra contar.
  let registros = [];

  // ═══ 1. Lista via API REST ══════════════════════════════════════
  async function carregarLista() {
    const corpo = alvo('tabela-rest');
    if (!corpo) return;

    corpo.innerHTML = '<tr><td colspan="4" class="text-muted">Carregando…</td></tr>';
    try {
      const dado = await T.rest.listar(cfg.restBase);
      registros = dado.items || [];

      // Filtro e paginação aplicados no cliente porque este endpoint do
      // CrudGen devolve a coleção inteira. Se a entidade crescer, o
      // certo é paginar no servidor (hook do CrudGen) em vez de trazer
      // tudo e cortar aqui.
      const busca = (cfg.search || '').toLowerCase();
      const filtrados = busca
        ? registros.filter((r) => String(r.name || '').toLowerCase().includes(busca))
        : registros;

      const inicio = ((cfg.page || 1) - 1) * (cfg.perPage || 20);
      const pagina = filtrados.slice(inicio, inicio + (cfg.perPage || 20));

      corpo.innerHTML = pagina.length
        ? pagina.map(linhaHtml).join('')
        : '<tr><td colspan="4" class="text-muted">Nenhum registro encontrado.</td></tr>';

      const contagem = alvo('contagem-rest');
      if (contagem) {
        contagem.textContent = filtrados.length + ' registro(s)' +
          (busca ? ' para "' + busca + '"' : '') + '.';
      }
      atualizarIndicadores();
    } catch (e) {
      // Erro vai para a própria área de conteúdo: um toast some, e a
      // tabela ficaria "Carregando…" para sempre.
      corpo.innerHTML = '<tr><td colspan="4" class="text-danger">' + esc(e.message) + '</td></tr>';
    }
  }

  function linhaHtml(r) {
    const cor = r.status === 'disponivel' ? 'success' : 'secondary';
    return '<tr>' +
      '<th scope="row">' + esc(r.id) + '</th>' +
      '<td>' + esc(r.name) + '</td>' +
      '<td><span class="badge bg-' + cor + '">' + esc(r.status) + '</span></td>' +
      '<td class="text-end">' +
        '<button class="btn btn-sm btn-outline-primary" data-editar="' + esc(r.id) + '">Editar</button>' +
      '</td>' +
    '</tr>';
  }

  // ═══ 2. Ação de Dado ════════════════════════════════════════════
  async function carregarViaAcao() {
    const lista = alvo('lista-acao');
    if (!lista || !cfg.dataActionId) return;

    lista.innerHTML = '<li class="list-group-item text-muted">Carregando…</li>';
    try {
      const status = (campo('filtro-status') || {}).value;
      const params = { '$top': 50, '$orderby': 'name asc' };
      // O $filter do provedor local aceita só `campo eq 'valor'`, com
      // condições unidas por ` and ` — sem gt/lt/or (skill 17, §4).
      if (status && status.trim()) params['$filter'] = "status eq '" + status.trim() + "'";

      const dado = await T.acaoDeDado(cfg.dataActionId, { params: params });
      const linhas = (dado.result && dado.result.value) || [];

      const contagem = alvo('contagem-acao');
      if (contagem) {
        const total = (dado.result && dado.result['@odata.count']);
        contagem.textContent = (total !== undefined ? total : linhas.length) + ' registro(s) no total.';
      }

      lista.innerHTML = linhas.length
        ? linhas.map((r) =>
            '<li class="list-group-item d-flex justify-content-between align-items-center">' +
              esc(r.name) +
              '<span class="badge bg-light text-dark">' + esc(r.status) + '</span>' +
            '</li>').join('')
        : '<li class="list-group-item text-muted">Nenhum registro.</li>';
    } catch (e) {
      lista.innerHTML = '<li class="list-group-item text-danger">' + esc(e.message) + '</li>';
    }
  }

  // ═══ 3. Formulário ══════════════════════════════════════════════
  async function carregarOpcoes() {
    const select = campo('registro');
    if (!select) return;
    try {
      const dado = await T.opcoes(cfg.optionsPlural);
      // O endpoint pode devolver `items` ou `results` conforme a versão;
      // e cada opção traz id/value e text/label. Normalizamos aqui.
      const itens = dado.items || dado.results || [];
      select.insertAdjacentHTML('beforeend', itens.map((o) =>
        '<option value="' + esc(o.id !== undefined ? o.id : o.value) + '">' +
          esc(o.text || o.label || o.name) +
        '</option>').join(''));
    } catch (e) {
      T.aviso(e.message, 'error');
    }
  }

  async function selecionarRegistro(id) {
    const select = campo('registro');
    if (select) select.value = id || '';
    if (!id) { limparFormulario(); return; }
    try {
      const dado = await T.rest.obter(cfg.restBase, id);
      campo('nome').value = dado.item.name || '';
      campo('status').value = dado.item.status || 'disponivel';
    } catch (e) {
      T.aviso(e.message, 'error');
    }
  }

  function limparFormulario() {
    const select = campo('registro');
    if (select) select.value = '';
    if (campo('nome')) campo('nome').value = '';
    if (campo('status')) campo('status').value = 'disponivel';
  }

  async function salvar() {
    const id = (campo('registro') || {}).value;
    const dados = {
      name: (campo('nome').value || '').trim(),
      status: campo('status').value,
    };
    if (!dados.name) { T.aviso('Informe o nome.', 'warning'); return; }

    try {
      // Sem id → cria (POST); com id → atualiza (PUT). É a diferença
      // entre `<plural>.create` e `<plural>.update` na permissão.
      if (id) await T.rest.atualizar(cfg.restBase, id, dados);
      else await T.rest.criar(cfg.restBase, dados);
      T.aviso('Salvo.', 'success');
      limparFormulario();
      carregarLista();
    } catch (e) {
      T.aviso(e.message, 'error');
    }
  }

  // ═══ 4. Indicadores, derivados do que já está em memória ════════
  function atualizarIndicadores() {
    const total = alvo('ind-total');
    const disponiveis = alvo('ind-disponiveis');
    if (total) total.textContent = registros.length;
    if (disponiveis) disponiveis.textContent = registros.filter((r) => r.status === 'disponivel').length;
  }

  // ═══ Eventos ════════════════════════════════════════════════════
  // Delegação no document: os botões "Editar" nascem dentro de um
  // innerHTML que é reescrito a cada carga. Listener anexado direto
  // neles morreria no primeiro recarregamento.
  document.addEventListener('click', function (ev) {
    const editar = ev.target.closest('[data-editar]');
    if (editar) { selecionarRegistro(editar.getAttribute('data-editar')); return; }

    const acao = ev.target.closest('[data-acao]');
    if (!acao) return;
    switch (acao.getAttribute('data-acao')) {
      case 'recarregar-rest': carregarLista(); break;
      case 'filtrar-acao': carregarViaAcao(); break;
      case 'salvar': salvar(); break;
      case 'limpar': limparFormulario(); break;
    }
  });

  document.addEventListener('change', function (ev) {
    if (ev.target.matches('[data-campo="registro"]')) selecionarRegistro(ev.target.value);
  });

  // ═══ Carga inicial ══════════════════════════════════════════════
  carregarLista();
  carregarViaAcao();
  carregarOpcoes();
})(window);
