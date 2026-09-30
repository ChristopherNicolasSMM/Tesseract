# Saneamento de ingredientes — 1B: aba Receita

A aba Receita apresenta um formulário expansível por ingrediente para
selecionar Material de Estoque (`weakref-combo`, fonte `materials`) ou marcar
Não consumir do estoque (`form-select`). Vincular não cria Material, não
atualiza o de-para global e não confirma consumo. Quantidade/unidade continuam
iguais e eventuais pendências permanecem visíveis após salvar.

Reutiliza `ingredient_sanitation_service.sanear_ingrediente()` do patch 1A.
Receitas referenciadas por sessões, inclusive de outras plantas e na lixeira,
mostram mensagem de bloqueio e não exibem formulário local. O servidor aplica
a mesma proteção. Receitas são globais; a planta fornece o contexto de navegação.
O cadastro avançado continua disponível com seu comportamento anterior.

Nova rota autenticada, exige `recipe_ingredients.update`:

`POST /brewstation/plant-workspace/<ID_PLANTA>/recipes/<ID_RECEITA>/ingredients/<ID_INGREDIENTE>/sanitize`

Aceita apenas os valores usados pelo serviço para `material_id` e
`status_resolucao`. Campos adicionais não são aplicados. Planta/receita/linha
apagadas ou linha de outra receita retornam 404 no AJAX; receita em uso retorna
409; dados inválidos retornam 400. Falha inesperada retorna mensagem genérica
e faz rollback. A rota não registra usuário enviado pelo formulário nem permite
alterar quantidade, receita ou custos por payload adicional.

Salvar usa `__workspaceSubmitForm` e recarrega o fragmento atual com conferência
e estimativa atualizadas. Não consumir exige o modal padrão do Core; cancelamento
não envia requisição. A UI bloqueia envios durante confirmação/envio e inicializa
combos no fragmento pelo helper público. O retorno sem AJAX preserva receita/planta.

A casca agora propaga `recipe_id` quando abre a aba Receita. Uma seleção explícita
inválida/apagada retorna fragmento de erro com 404; não abre o seletor silenciosamente.

Não há migration, `db upgrade`, alteração de menu nem arquivo CrudGen gerado editado.
Revisão de receitas em uso e edição de quantidade/unidade/especificações continuam
pendentes para o 1C. O 1A foi validado pelo usuário; o 1B ainda requer validação local.

## Testes

```shell
python -m pytest tests/test_plant_workspace.py tests/test_mash_control_ingredient_resolution.py tests/test_weak_ref_value_field.py
python -m pytest tests/test_feature_brew_father.py tests/test_feature_envase.py tests/test_addon_estoque.py tests/test_dashboard_runtime.py
```

Cobertura nova: formulário/combos, vínculo/Não consumir sem baixa, preservação
de campos, consulta atualizada, permissão, contextos inválidos/lixeira, bloqueio
de receita usada por outra planta, retorno com receita selecionada e rollback.
Os testes antigos de erro de seleção foram ajustados para o status HTTP 404.

Sintaxe Python/JSON/JavaScript, diff e aplicação do patch foram verificados no
ambiente do assistente. Pytest não foi executado por falta das dependências.
A confirmação/cancelamento do modal e interação com combo precisam de teste visual.

## Roteiro visual

Abrir `http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe&recipe_id=<ID_RECEITA>`.

1. Usar receita sem sessão, abrir Sanear ingrediente, buscar material e salvar.
   Conferir vínculo, pendências e estimativa; permanecer na mesma receita.
2. Escolher Não consumir; cancelar o modal e verificar ausência de alteração.
   Repetir confirmando: a linha deve aparecer como Não consumir, sem baixa.
3. Voltar a Vincular material e salvar uma seleção válida. Unidade incompatível
   ou quantidade ausente deve continuar pendente; não supor que vínculo basta.
4. Reabrir receita já vinculada a sessão: mensagem de bloqueio, sem formulário local.
5. Conferir usuário sem permissão, temas existentes e troca de abas. Dashboard
   mantém sua limpeza de timers/listeners. Conferir reload da URL direta de receita.

Essas ações de saneamento não movimentam estoque. Não é necessário confirmar
ingredientes ou gerar lote para validar a edição da receita neste patch.
