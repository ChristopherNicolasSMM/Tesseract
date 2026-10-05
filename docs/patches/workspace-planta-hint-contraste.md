# Ajuda do campo da planta e contraste de hints

Corrige a interpretação anterior: a orientação da Função do dispositivo na
aba Planta passa do texto permanente para ícone de ajuda junto ao rótulo.
Tooltip Bootstrap com hover/foco, inicialização após fragmento AJAX e dispose
via __tabCleanup, preservando limpeza anterior. Combo padrão inalterado.

Core: tooltips usam superfícies/texto claros e escuros, borda e sombra conforme
cards do projeto. Descrições de menu continuam dicas, com nomes curtos.
Sem migration. Aplicar após brewstation-menu-hints.patch.

Teste: python -m pytest tests/test_plant_workspace.py -k 'tab_plant or shell_js_tem_hook' -q
Visual: /brewstation/plant-workspace/1?tab=plant. Passar mouse ou focar ícone ao
lado de Função do dispositivo; conferir orientação completa nos temas claro e
escuro. Trocar de aba enquanto a dica está aberta: não deve sobrar balão.
Verificar também tooltips do menu. Cadastro e estoque não são alterados.
Imagem enviada indisponível no ambiente; campo identificado pelo código,
sem alegar validação visual da captura ou do navegador.

Verificado: 6 testes passaram, 205 não selecionados. Sintaxe Jinja/JavaScript
e diff conferidos; format-patch aplicado em checkout isolado.
