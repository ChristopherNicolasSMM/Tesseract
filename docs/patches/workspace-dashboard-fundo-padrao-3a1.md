# Entrega 3A.1 — Fundo e painel padrão da planta

## Mudança e limites

Workspace incorpora cor hexadecimal, URL da imagem de fundo e painel padrão
por planta, em formulário próprio. Nome/dimensões permanecem na edição
básica. Imagem agora é renderizada no workspace e view própria, atrás de
widgets/tubulação, sem interceptar eventos. Não há upload de arquivos.

Configuração exige dashboard_layouts.update, valida pertencimento e registros
não apagados. Campo padrão limpa somente outros painéis ativos da mesma
planta, na mesma transação; erro reverte ambos. Widgets, layout_data,
proprietário, dimensões, standby, sessão/controles e estoque preservados.
Retorno normal/AJAX mantém o painel selecionado. Sem padrão, mantém fallback
para o primeiro painel cadastrado. O acesso global continua com seu mecanismo
existente; não foi criado painel padrão global independente nem feita limpeza
de dados antigos. Duplicatas criadas pelo CRUD completo são consolidadas ao
escolher explicitamente um padrão no workspace.

Cor aceita #RGB/#RRGGBB/#RRGGBBAA. URL admite HTTP/HTTPS sem credenciais ou
caminho iniciado por /, sem espaços/controles ou prefixo //. Vazio remove
imagem. Leitura valida legados: cor inválida usa fallback escuro e URL inválida
não é renderizada; consulta nunca corrige registros no banco.

O plano 3A foi dividido por lacuna real: is_standby_enabled e duração estão
no model, sem comportamento encontrado no runtime. 3A.2 deve definir e
implementar essa função; 3B cobre lixeira/restauração. Nenhum menu foi ocultado.
3A.1 implementado, validação visual/local pendente. Não marca 2C.1/2C.2 como
validados por ausência de confirmação específica.

## Aplicar e testar

Patch válido format-patch, sobre 2C.2. **Não requer db upgrade**; usa campos
existentes. A migration pendente do 2C.2 deve ter sido aplicada normalmente.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-dashboard-fundo-padrao-3a1.patch
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py -q
```

Rotas:

- `/brewstation/plant-workspace/<ID_PLANTA>?tab=dashboard&layout_id=<ID_LAYOUT>`
- `/brewstation/plant-workspace/<ID_PLANTA>/tab/dashboard?layout_id=<ID_LAYOUT>`
- `/brewstation/dashboards/<ID_LAYOUT>/view`
- POST `/brewstation/plant-workspace/<ID_PLANTA>/dashboard-layouts/<ID_LAYOUT>/appearance`

Roteiro visual:

1. Escolher painel secundário da planta, abrir Configurar layouts; salvar
   cor #123456 e imagem `/static/img/slides-2.jpg` (arquivo existente no
   checkout conferido), ou URL real de outra imagem. Conferir fundo e
   widgets/tubulação preservados.
2. Definir painel como padrão, salvar e reabrir aba Dashboard sem layout_id:
   esse painel deve abrir. Conferir que padrão de outra planta permaneceu.
3. Desmarcar padrão; sem outro padrão, abrir primeiro painel cadastrado.
   Painel editado deve continuar selecionado imediatamente após salvar.
4. Limpar URL para remover imagem. Cor permanece. Abrir view própria e
   conferir o mesmo fundo, sem formulário de configuração do workspace.
5. Tentar cor inválida ou javascript: na URL: mensagem de erro; configuração
   e padrão anteriores preservados. Usuário sem update não vê formulário e
   POST é negado. Layout externo/apagado retorna erro, sem escolher outro.
6. Alternar Dashboard/Sessões/Planta e retornar. Polling e listeners não
   devem duplicar; controles e leituras existentes continuam funcionando.
   Conferir contraste nos temas e formulário em largura pequena.

## Verificação no ambiente do assistente

Execução final com código estabilizado: **260 testes aprovados** em
`tests/test_plant_workspace.py` e `tests/test_dashboard_runtime.py` (296,25 s).
Recorte inicial dos casos novos: 10 aprovados; retorno/casca: 6 aprovados.
Sintaxe Python, Jinja e JavaScript e diff verificados. Patch será conferido
por aplicação em worktree isolado e comparação do tree com a entrega.
Validação visual com aplicação em execução não foi realizada; usar roteiro
acima localmente.
