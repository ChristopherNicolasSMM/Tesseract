/**
 * static/js/freestyle/freestyle-tesseract-data.js
 *
 * Helper de acesso a dado do Tesseract. Compartilhado por mais de um
 * modelo freestyle — por isso o prefixo é `freestyle-` e não o nome de
 * um HTML específico, como nos demais arquivos desta pasta.
 *
 * Expõe window.TesseractData com os três caminhos documentados na
 * skill 17, mais os utilitários que toda tela acaba reescrevendo:
 * escape de XSS, leitura do bloco de config e aviso ao usuário.
 *
 * Copie este arquivo para suas telas — a intenção é justamente não
 * reescrever fetch e tratamento de erro em cada uma.
 */
(function (window) {
  'use strict';

  const TesseractData = {

    /**
     * Escapa valor vindo do servidor antes de ir para innerHTML.
     *
     * O HTML da tela é confiável (você escreveu). O CONTEÚDO dos
     * registros não é: um nome cadastrado como `<img onerror=...>`
     * executa se for concatenado cru. Esta é a diferença que mais
     * passa despercebida — use em TODA interpolação de dado.
     */
    esc(valor) {
      if (valor === null || valor === undefined) return '';
      return String(valor).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    },

    /**
     * Lê o <script type="application/json"> que o template gerou a
     * partir do `config` do controller. Sem isso, os endpoints ficariam
     * hardcoded aqui e trocar de entidade exigiria mexer no JavaScript.
     */
    config(id) {
      const bloco = document.getElementById(id || 'freestyle-config');
      if (!bloco) return {};
      try {
        return JSON.parse(bloco.textContent);
      } catch (e) {
        console.error('Bloco de config inválido:', e);
        return {};
      }
    },

    aviso(mensagem, tipo) {
      if (window.__tesseractToast) window.__tesseractToast.show(mensagem, tipo || 'info');
      else console[tipo === 'error' ? 'error' : 'log'](mensagem);
    },

    /**
     * Núcleo das chamadas. Normaliza o erro para uma Exception com
     * mensagem legível, para a tela só precisar de try/catch.
     */
    async _json(url, opcoes) {
      let resposta;
      try {
        resposta = await fetch(url, opcoes);
      } catch (e) {
        // Falha de rede: o fetch nem chegou ao servidor.
        throw new Error('Não foi possível falar com o servidor. Verifique a conexão.');
      }

      // 401 e 403 pedem respostas diferentes do usuário: recarregar
      // resolve o primeiro (sessão expirada) e nunca o segundo (falta
      // de permissão). Tratar os dois como "erro genérico" faz a pessoa
      // recarregar em loop sem entender por quê.
      if (resposta.status === 401) throw new Error('Sessão expirada. Recarregue a página para entrar de novo.');
      if (resposta.status === 403) throw new Error('Você não tem permissão para esta operação.');

      let dado;
      try {
        dado = await resposta.json();
      } catch (e) {
        // Resposta não-JSON quase sempre é a tela de login em HTML —
        // sessão caiu e o servidor redirecionou.
        throw new Error('Resposta inesperada do servidor (sessão pode ter expirado).');
      }

      if (!resposta.ok || dado.success === false) {
        throw new Error(dado.error || ('Falha na requisição (HTTP ' + resposta.status + ').'));
      }
      return dado;
    },

    _corpoJson(dados) {
      return { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) };
    },

    /** 1) API REST do CrudGen — CRUD completo da entidade. */
    rest: {
      listar(base) { return TesseractData._json(base + '/'); },
      obter(base, id) { return TesseractData._json(base + '/' + id); },
      criar(base, dados) {
        return TesseractData._json(base + '/', Object.assign({ method: 'POST' }, TesseractData._corpoJson(dados)));
      },
      atualizar(base, id, dados) {
        return TesseractData._json(base + '/' + id, Object.assign({ method: 'PUT' }, TesseractData._corpoJson(dados)));
      },
      // Soft-delete: `trash` marca is_deleted, `restore` desfaz. Só use
      // `excluir` (DELETE) quando o registro precisar sumir de verdade.
      lixeira(base, id) { return TesseractData._json(base + '/' + id + '/trash', { method: 'POST' }); },
      restaurar(base, id) { return TesseractData._json(base + '/' + id + '/restore', { method: 'POST' }); },
      excluir(base, id) { return TesseractData._json(base + '/' + id, { method: 'DELETE' }); },
    },

    /**
     * 2) Ação de Dado — sempre server-side. O navegador manda só qual
     * ação disparar e os parâmetros; quem resolve conexão e credencial
     * é o servidor, então nenhum segredo passa por aqui.
     */
    acaoDeDado(id, corpo) {
      return TesseractData._json(
        '/admin/designer/data-action/' + id + '/execute',
        Object.assign({ method: 'POST' }, TesseractData._corpoJson(corpo || {})),
      );
    },

    /** 3) Opções de combo — mesmo endpoint dos combos do CrudGen. */
    opcoes(plural, busca) {
      return TesseractData._json('/api/options/' + plural + '?search=' + encodeURIComponent(busca || ''));
    },
  };

  window.TesseractData = TesseractData;
})(window);
