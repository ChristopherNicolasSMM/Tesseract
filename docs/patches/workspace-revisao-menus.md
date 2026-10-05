# Revisão do workspace e menus — 05/10/2026

Base: patch combinado 4B.3/4B.4/4C, aprovado nos testes pelo usuário.
Esta revisão fecha o inventário de navegação; não declara toda a manutenção
avançada integrada. Não altera schema, estoque, runtime ou permissões.

## Matriz de cobertura

| Menu/código | Coberto no workspace | Operação/acesso restante | Decisão |
| --- | --- | --- | --- |
| TX_BREW_PLANTS | Criar e editar dados básicos na aba Planta | Manutenção completa, inclusive registros apagados, pelo cadastro | Manter ocultação existente; cadastros de tanques/mapeamentos preservados |
| TX_RECIPE_INGREDIENTS | Conferência, vínculo local e dados planejados; revisão protege receitas usadas | Operações avançadas pelo contexto da receita; de-para compartilhado separado | Manter ocultação existente |
| TX_RECIPE_STEPS / TX_FERMENTATION_STEPS / TX_RECIPE_TIMELINE | Timeline e edição contextual da receita | Editor existente permanece acessível pelo fluxo | Manter ocultação existente |
| TX_DASHBOARD_VIEW / TX_DASHBOARD_WIDGETS | Dashboard, editor visual, widgets e tubulação | Editor visual existente é reutilizado | Manter ocultação existente |
| TX_BREW_PLANT_VESSELS / TX_BREW_PLANT_MAPPINGS | Criar/editar com validação de pertencimento | Lixeira/restauração e manutenção completa fora da aba | Preservar menu |
| TX_DASHBOARD_LAYOUTS | Criar/editar, fundo/padrão, lixeira/restauração por planta | Cadastro completo e exclusão permanente; standby sem runtime | Preservar; identificar como avançado |
| TX_BREW_SESSIONS | Histórico, edição básica, ingredientes, custos, envase e controles | Lixeira/restauração e manutenção global | Preservar menu e link ao cadastro da sessão |
| TX_BREW_SESSION_STEPS | Consultar, ajustar nome/temperatura/duração e controles existentes | Demais campos/manutenção no cadastro | Preservar menu |
| TX_BREW_SESSION_LOGS / TX_BREW_SESSION_ALARMS | Histórico paginado; reconhecimento de alarmes | Cadastro/manutenção e consulta global | Preservar menu |
| TX_AUTOMATION_RULES | Criar/editar inativas, ativar/desativar, lixeira/restauração | Cadastro completo e exclusão permanente | Preservar; identificar como avançado |
| TX_AUTOMATION_RULE_LOGS | Histórico filtrado/paginado no contexto da planta | Histórico global, inclusive fora das sessões disponíveis no workspace | Preservar; identificar como global |
| TX_MASH_RECIPES / TX_RECIPE_HISTORYS | Consulta/revisão no contexto da receita | Cadastro e histórico global | Preservar menu |
| TX_WATER_PROFILES / TX_INGREDIENT_MAPPINGS | Água por receita e saneamento local | Manutenção dos perfis e de-para compartilhado | Preservar menu |
| Envase e precificação | Registro/detalhes/estorno no lote; retorno da precificação | Cadastros globais e tela própria de precificação | Preservar menus |
| Brewfather / YeastBank | Portais próprios existentes | Auditorias específicas futuras | Fora da ocultação |

Não há novo código ocultado: todos os candidatos adicionais têm uso ainda
não substituído. A lista do comando permanece com os sete códigos anteriores.
A presença de um item no catálogo não prova sua visibilidade no banco local.

## Mudanças de navegação

Novo `TX_AUTOMATION_FLOW`: `/brewstation/plant-workspace/?tab=automation`,
no grupo Automação. Usa `brew_plants.list`, exigida pela escolha da planta;
a aba continua exigindo `automation_rules.list` e cada mutação sua permissão.
A abertura do fluxo não concede acesso às regras nem aciona dispositivos.

Metadados do catálogo manual identificam regras/layouts como avançados e
histórico como global. Foram removidas descrições desatualizadas que diziam
que automação não tinha motor e dashboards estavam em construção.
Sincronização no boot cria a nova entrada e atualiza metadados sem reativar
transações existentes. Não editar catálogo gerado nem controllers CrudGen.

## Aplicação e testes

Sem `db upgrade`: não existe migration nova. Reiniciar a aplicação para
sincronizar o catálogo. Configurações existentes de visibilidade são mantidas.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-revisao-workspace-menus.patch
python -m pytest tests/test_hide_legacy_mash_control_menu.py -q
flask hide-legacy-mash-control-menu --dry-run
flask hide-legacy-mash-control-menu
```

O último comando aplica somente os sete códigos cobertos; repetir é idempotente.
Não altera transações fora da lista nem reativa itens desativados pelo operador.
Reversão de visibilidade: `/admin/menu-settings`.

### Roteiro visual

1. Reiniciar e abrir Automação → Abrir fluxo de automação. Escolher uma planta;
   conferir que abre a aba Automação em `/brewstation/plant-workspace/<ID>`.
2. Verificar Regras de Automação — avançado e Histórico de Regras — global.
   Conferir Layouts de Dashboard — avançado em configuração de plantas.
3. Abrir `/brewstation/plant-workspace/?tab=plant` e
   `/brewstation/plant-workspace/?tab=sessions`; conferir cadastros avançados
   preservados. Links e menus continuam sujeitos às permissões existentes.
4. Comparar dry-run com o menu, executar ocultação e conferir que workspace,
   tanques, mapeamentos, sessões, históricos e cadastros avançados permanecem
   disponíveis quando anteriormente ativos. Nenhuma rota é apagada.
5. Com usuário limitado, verificar que acesso ao seletor de plantas não concede
   leitura/edição de regras sem as permissões correspondentes.

Pendências: standby 3A.2, manutenção local de tanques/mapeamentos/sessões,
campos avançados de etapas, proveniência física dos eventos e auditoria ponta
a ponta. PID contínuo e exclusão permanente não foram incorporados.


## Verificação da entrega

Executado no ambiente do assistente: suíte de menus **8 passed**; recorte
`tests/test_plant_workspace.py -k 'landing or automation_permissoes'`:
**4 passed, 207 deselected**. Sintaxe Python e `git diff --check` verificados.
Patch gerado por `git format-patch` e aplicação conferida em checkout isolado.
Não foi executada validação visual em navegador nem a suíte funcional inteira,
pois não houve mudanças de serviços, templates ou runtime.
