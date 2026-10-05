# Dashboard — descanso visual 3A.2

## Comportamento definido nesta entrega

O pedido de continuidade não especificou a semântica do standby. Este patch
adota descanso visual por inatividade, conforme comunicado ao usuário:
suaviza o canvas em 20% após o intervalo, mantendo conteúdo visível. Não é
rotação de layouts, desligamento de tela, pausa de brassagem ou economia de
polling. Cabeçalho, timers da sessão e navegação continuam na aparência normal.
Não há camada bloqueadora nem alteração de controles, alarmes ou dispositivos.
Mouse, toque (pointerdown), teclado, foco ou rolagem restauram a aparência.
Retorno à aba do navegador reinicia o intervalo. Modo Edição suspende o descanso.

## Configuração e limites

Na aba Dashboard → Configuração dos dashboards desta planta, ativar
Descanso visual e informar segundos inteiros entre 10 e 86400. Campos reais:
is_standby_enabled e standby_duration_seconds; não cria schema novo.
Salvar descanso é independente de fundo/padrão e edição básica. Preserva
widgets, configuração, proprietário, vínculos, padrão e estado de sessões.
Valores antigos inválidos desativam o descanso somente na renderização;
consulta não corrige o banco. O formulário apresenta 30 segundos para correção.
Layouts antigos habilitados com duração válida passam a executar o descanso.

POST /brewstation/plant-workspace/<PLANTA>/dashboard-layouts/<LAYOUT>/standby
exige dashboard_layouts.update, planta/painel existentes e não apagados e
pertencimento. Falha de gravação faz rollback. AJAX retorna layout_id, mantendo
a seleção; retorno normal também conserva o painel.

Runtime reutilizável em static/js/dashboard_standby.js, carregado pela casca e pela view antes dos scripts do dashboard; serve ao workspace e à view própria. Sem requests, sem
setInterval adicional; timeout local rearmado por interação. __tabCleanup
remove timeout/listeners/classe junto à limpeza existente do dashboard.
Não altera controllers/templates gerados. Permissões e menus preservados.

## Aplicação e testes

Aplicar após as correções de hints. Sem db upgrade.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-dashboard-standby-3a2.patch
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py -q
node tests/js/test_dashboard_standby.cjs
```

Alternativa curta para esta entrega:

```powershell
python -m pytest tests/test_plant_workspace.py -k "standby or dashboard_aparencia or dashboard_fundo" -q
```

## Roteiro visual

1. /brewstation/plant-workspace/<PLANTA>?tab=dashboard: selecionar painel,
   abrir configuração, ativar descanso e salvar 10 segundos.
2. Deixar sem interação: apenas canvas suaviza. Conferir leituras atualizando,
   cabeçalho/timer visível e ausência de mudança no estado da sessão.
3. Mover mouse, tocar ou pressionar tecla: aparência normal e contagem reinicia.
4. Entrar em Modo Edição e aguardar: descanso suspenso. Sair e testar novamente.
5. Trocar de aba/painel e voltar várias vezes: nenhum comportamento residual.
6. /brewstation/dashboards/<LAYOUT>/view: mesmo comportamento salvo.
7. Desativar e salvar: não suaviza mais. Testar claro/escuro, acesso limitado e
   painel de outra planta. Duração inválida deve ser rejeitada sem salvar.

Sem testes com hardware nem validação visual em navegador nesta entrega.
Permanece auditoria integrada ponta a ponta, manutenção avançada listada na
matriz de menus, proveniência física dos eventos e PID contínuo.


## Verificação executada

- Recorte final workspace: **22 passed, 199 deselected** (inclui limpeza da casca).
- Suíte completa test_dashboard_runtime.py: **111 passed**.
- Teste Node: inatividade, despertar, edição, desativação, canvas removido e
  limpeza idempotente passaram.
- Python/Jinja/JavaScript e git diff --check verificados; format-patch aplicado
  em checkout isolado e árvore comparada à entrega.

A suíte completa de workspace/estoque/envase não foi repetida nesta entrega.
