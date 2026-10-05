# Workspace — Automação 4B.1 e inventário 4A

05/10/2026. Etapas anteriores confirmadas pelo usuário. Novo incremento
implementado, aguardando sua validação. Sem migration ou `db upgrade`.

## Mudança

A aba Automação permitia consultar apenas os últimos 20 disparos e carregava
todas as regras. Agora regras e disparos têm paginação independente de 20
itens. Nome (busca literal), regra pelo weakref-combo, status e vínculo filtram
ambos; resultado Sucesso/Erro filtra somente disparos. Links mantêm os filtros
e a outra página; envio de filtros/limpeza reinicia ambas as páginas.

Seleção explícita inválida/externa/apagada devolve 404. Enums inválidos: 400.
Regras vinculadas a sessões apagadas ficam fora do escopo. Histórico exige
`automation_rule_logs.list`, além de `automation_rules.list` para abrir a aba.
Atalhos de cadastro/detalhes respeitam create/detail. Classes de cards,
tabelas e itens usam os temas do Core. Consulta não escreve nem aciona hardware.

## Inventário 4A — operações existentes

Prefixo das rotas abaixo: `/brewstation/dashboards`.

| Operação existente | POST | Permissão | Implementação |
| --- | --- | --- | --- |
| Avançar etapa | `/sessions/<ID>/advance-step` | `dashboard_layouts.update` | `dashboard_runtime.py` → `recipe_timeline_service` |
| Voltar etapa | `/sessions/<ID>/go-back-step` | `dashboard_layouts.update` | Mesmo serviço |
| Ressincronizar etapas | `/sessions/<ID>/resync-steps` | `dashboard_layouts.update` | Mesmo serviço; não duplicar controles |
| Pausar/retomar | `/sessions/<ID>/toggle-pause` | `brew_sessions.update` | Só active/paused; deslocamento do timer no serviço |
| Parar | `/sessions/<ID>/stop` | `brew_sessions.update` | Só active/paused; marca completed |

Esse inventário identifica os pontos existentes; não declara concluída a
revisão de integridade/escopo de todas as operações. Este patch não muda essas
rotas nem cria botões concorrentes.

`automation_engine.py` busca regras ativas/não apagadas por sensor e executa
condição/cooldown; **não usa session_id para restringir execução**. A interface
identifica vínculo de cadastro sem prometer isolamento por sessão. Logs têm
regra/horário/resultado, sem planta/sessão de origem; histórico global é
compartilhado. Rever essa semântica antes de 4B.2 criação/edição/ativação.
Standby 3A.2 e revisão final de menus permanecem pendentes.

## Testes

```powershell
python -m pytest tests/test_plant_workspace.py -k automation -q
python -m pytest tests/test_plant_workspace.py tests/test_phase9f_automation_engine.py -q
```

Os testes novos conferem páginas antigas, filtros preservados, seleção
inválida, exclusão, busca literal, escopo do combo, permissões e consulta sem
acionamento/escrita. Neste ambiente pytest não está disponível nos intérpretes
verificados; não foi executado com sucesso. Sintaxe e aplicação do patch são
verificadas separadamente. Validação visual deve ocorrer no ambiente do usuário.

## Rotas e conferência visual

- `/brewstation/plant-workspace/<ID_PLANTA>` → Automação.
- Fragmento: `/brewstation/plant-workspace/<ID_PLANTA>/tab/automation`.
- Exemplo: fragmento + `?scope=session&active=active&outcome=error&logs_page=2`.

1. Abra Automação nos temas claro/escuro. Confira rótulos e legibilidade.
2. Busque regra pelo combo; somente globais e sessões não apagadas desta planta
   devem aparecer. Limpe a referência; combine nome/status/vínculo/resultado.
3. Com mais de 20 itens, alterne páginas de regras/disparos; os filtros e a outra
   página devem permanecer. Filtrar/Limpar volta à primeira página.
4. Verifique regras globais com indicação de compartilhamento e regras com
   nome/ID da sessão. Consulta não deve alterar controles, sessão ou contadores.
5. Sem permissão de logs, a lista de regras abre sem conteúdo do histórico.
   Atalhos Nova Regra/Detalhes aparecem somente conforme suas permissões.
6. Passe rule_id de outra planta/apagado/inválido: erro, sem selecionar outra
   regra. Troque Dashboard → Automação → Dashboard e confira limpeza/reinício
   dos listeners e timers existentes.
