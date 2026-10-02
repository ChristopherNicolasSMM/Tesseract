# Entrega 3B — Lixeira e restauração de painéis

## Escopo

Aba Dashboard incorpora enviar o painel escolhido à lixeira e restaurar
painéis da planta. Reutiliza serviço existente, por extensão manual, sem
editar artefatos gerados. Confirmação pelo modal do Core e catálogo i18n;
permissões dashboard_layouts.trash/restore conferidas no servidor.

Pertencimento e estado validados. Repetição de ação incompatível retorna
400 sem mudar a primeira remoção; outra planta/inexistente/planta apagada
retorna 404. Falha de gravação faz rollback. Painéis, widgets/configurações
não são excluídos fisicamente. Widgets já apagados individualmente continuam
apagados; a ação não restaura todos os widgets em cascata.

Ao remover o painel aberto, retorna padrão ativo ou primeiro restante;
nenhum restante abre estado vazio com lixeira acessível. Restauração abre
painel recuperado e não substitui padrão ativo da planta. Sem outro padrão,
preserva marcação original. Lixeira tem 20 itens/página, trash_page com limites
válidos, sem misturar outras plantas. URL explicitamente inválida continua
retornando erro, sem seleção silenciosa. Retornos AJAX/normais preservados.

Não altera sessão/etapas/controles, timers persistidos, MQTT ou estoque.
Cleanup de timers/listeners da UI usa o helper existente. Sem exclusão
permanente, ocultação de menu ou migration. Standby 3A.2 e etapas 4–6 continuam
pendentes. Implementado; validação visual/local pendente. Pedido de próximo
patch não marca entregas anteriores como aprovadas visualmente.

## Aplicar e testar

Aplicar sobre 3A.1. **Não requer db upgrade**.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-dashboard-lixeira-restauracao-3b.patch
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py -q
node --test tests/js/test_dashboard_maintenance.cjs
```

Após aplicar, reinicie a aplicação e recarregue a página do workspace: o
catálogo de mensagens do Core fica em cache. O teste JavaScript acima usa
Node, sem pacotes adicionais.

URLs:

- `/brewstation/plant-workspace/<ID_PLANTA>?tab=dashboard&layout_id=<ID_LAYOUT>`
- `/brewstation/plant-workspace/<ID_PLANTA>/tab/dashboard?layout_id=<ID_LAYOUT>&trash_page=2`
- POST `/brewstation/plant-workspace/<ID_PLANTA>/dashboard-layouts/<ID_LAYOUT>/trash`
- POST `/brewstation/plant-workspace/<ID_PLANTA>/dashboard-layouts/<ID_LAYOUT>/restore`

Roteiro visual em planta de teste:

1. Usar dois painéis com widgets/tubulação. Abrir secundário, Configurar
   layouts, Enviar painel à lixeira; cancelar modal e conferir que nada mudou.
2. Confirmar: deve abrir padrão/primeiro restante. Painel removido deve
   aparecer na lixeira; seu ID explícito na aba deve retornar erro.
3. Restaurar: abre o recuperado; conferir nome, fundo, dimensões e widgets.
   Padrão atual permanece. Para escolhê-lo como padrão, usar configuração 3A.1.
4. Enviar todos os painéis à lixeira: sem painel ativo, lixeira continua
   disponível. Restaurar um sem precisar abrir cadastro genérico.
5. Com mais de 20 removidos, navegar na lixeira e conferir seleção, contagem
   e lista da própria planta. Temas claro/escuro e tela estreita devem ser legíveis.
6. Conferir usuário sem trash/restore: botão correspondente ausente, POST
   negado. Conferir outra planta não alterada e sessão ativa preservada.
7. Alternar abas e restaurar novamente: polling/listeners não duplicam;
   confirmações não enviam formulário que foi removido ao trocar de aba.

## Validação do assistente

Execução final: **268 testes pytest aprovados** em workspace/runtime e
**3 testes Node aprovados** para confirmação/envio/cancelamento/troca de aba.
Recorte final de manutenção/estado vazio: 9 aprovados. Asserção antiga de
mensagem do estado vazio foi atualizada para refletir painéis indisponíveis,
com lixeira acessível, e a suíte completa foi executada novamente.
Sintaxe Python/Jinja/JSON/JavaScript e diff conferidos; entrega inclui
verificação por git am em worktree isolado e comparação de tree.
Não houve validação visual de aplicação em execução; roteiro deve ser
realizado localmente.
