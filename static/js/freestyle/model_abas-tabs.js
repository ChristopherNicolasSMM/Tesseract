/**
 * static/js/freestyle/model_abas-tabs.js
 *
 * Persistência da aba ativa na URL — comportamento que o Bootstrap não
 * traz de fábrica. Ligado por `data-abas-persistir` na <ul> das abas;
 * grupos sem o atributo seguem o comportamento padrão.
 *
 * Como funciona: ao trocar de aba, o alvo do botão (ex.: "#persist-b")
 * vai para o hash da URL via history.replaceState — `replaceState` e
 * não `pushState` de propósito, senão cada clique em aba viraria uma
 * entrada no histórico e o botão "voltar" do navegador passaria a
 * desfazer trocas de aba em vez de sair da página.
 */
(function () {
  'use strict';

  const ATRIBUTO = 'data-abas-persistir';

  function ativar(botao) {
    // bootstrap.Tab é exposto globalmente pelo bundle carregado no layout.
    if (window.bootstrap && window.bootstrap.Tab) {
      window.bootstrap.Tab.getOrCreateInstance(botao).show();
    } else {
      botao.click();
    }
  }

  function restaurarDoHash(grupo) {
    const hash = window.location.hash;
    if (!hash || hash.length < 2) return;

    // Só restaura se o hash apontar para um painel DESTE grupo — a
    // página pode ter vários grupos, e um hash de outro grupo (ou uma
    // âncora comum) não pode disparar troca de aba aqui.
    const botao = grupo.querySelector('[data-bs-target="' + CSS.escape(hash) + '"]');
    if (botao && !botao.disabled) ativar(botao);
  }

  function ligar(grupo) {
    restaurarDoHash(grupo);

    // 'shown.bs.tab' dispara depois da transição concluída, e cobre
    // tanto o clique do usuário quanto a ativação por código.
    grupo.addEventListener('shown.bs.tab', function (evento) {
      const alvo = evento.target.getAttribute('data-bs-target');
      if (!alvo) return;
      window.history.replaceState(null, '', window.location.pathname + window.location.search + alvo);
    });
  }

  document.querySelectorAll('[' + ATRIBUTO + ']').forEach(ligar);
})();
