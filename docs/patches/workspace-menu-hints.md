# Dicas nos itens de menu

Correção posterior à revisão de menus: restaura os rótulos curtos de regras,
layouts e histórico. Avançado/global passam para description do catálogo.
O menu lateral do Core usa o tooltip Bootstrap existente para descrições de
itens navegáveis, com escape Jinja padrão. Grupos mantêm seu collapse.
Sem migration; reiniciar para sincronizar os rótulos. Visibilidade preservada.

Aplicar após brewstation-revisao-workspace-menus.patch.

Teste: python -m pytest tests/test_hide_legacy_mash_control_menu.py -q
Visual: passar o mouse em Regras de Automação, Layouts de Dashboard e Histórico
de Regras. Conferir dica, nome curto, contraste nos temas e navegação normal.

Verificação: 8 testes de menus passaram; teste de renderização ampliado passou
separadamente. Diff e aplicação do format-patch conferidos. Validação visual
no navegador permanece local.
