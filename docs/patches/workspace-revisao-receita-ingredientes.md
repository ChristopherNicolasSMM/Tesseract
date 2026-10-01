# Workspace — revisão completa e dados planejados de ingredientes (1C)

Data: 30/09/2026. Base funcional: 1B aplicado e validado pelo usuário.
1C aplicado e validado pelo usuário em 01/10/2026. Pytest não foi
executado pelo assistente: pytest/Flask/SQLAlchemy/Jinja não estão disponíveis
nesse ambiente, e o usuário executará as suítes localmente.

## Escopo e lacunas corrigidas

- Revisão completa por ação explícita no workspace, com modal Bootstrap do
  Core, operador e observação; abre a nova versão na mesma aba/planta.
- Correção de `criar_nova_versao()`: preserva volume planejado e todos os
  campos de ingredientes ativos, timeline, fermentação e contextos de água.
  Remapeia IDs de pai e ingrediente dos alertas, preservando alertas manuais.
  Lixeira não é copiada. A nova versão usa máximo do mesmo nome + 1, inclusive
  versões apagadas; referência externa/apagada bloqueia com rollback.
- Edição local de quantidade, unidade, tempo de adição, tipo, etapa, uso
  detalhado, EBC, rendimento, ácidos alfa e atenuação. Formulários separados
  para dados planejados e vínculo/decisão, com mensagens e helpers existentes.
- Unidade pelo `weakref-combo` padrão (`unidades_catalogo`, campo `codigo`);
  tipos/etapas por `form-select`. Validação pelo lookup público do estoque.
  Unidade conhecida usa código canônico; legado não alterado pode permanecer.
  Nenhuma conversão é inventada ao selecionar unidade, inclusive PCT.
- Dados, alertas automáticos de lúpulo e snapshot gravados na mesma transação.
  Números precisam ser finitos/não negativos; tempo usa minutos inteiros.
  Salvar sem alterações não gera novo histórico. Campo vazio pode continuar
  pendente, conforme conferência existente; zero não autoriza consumo.
- Edição local bloqueada para qualquer sessão da receita, inclusive na
  lixeira. Nova revisão não troca receita, timers, etapas ou custo do lote.
  Consulta da timeline de receita usada deixa de sincronizar alertas.
- Documentação técnica, manual, primeiros passos, backlog e plano atualizados;
  corrigida a descrição antiga de consumo parcial na documentação técnica.

## Rotas e permissões

Substitua os IDs reais. As receitas são globais: a planta é contexto de
navegação/destino de próxima sessão, não sua proprietária.

| Método | Rota | Validação / permissão |
| --- | --- | --- |
| GET | `/brewstation/plant-workspace/` | Entrada existente |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe&recipe_id=<ID_RECEITA>` | Casca existente; aba exige `recipe_steps.list` |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>/tab/recipe?recipe_id=<ID_RECEITA>` | Fragmento existente; seleção inválida/apagada retorna 404 |
| POST | `/brewstation/plant-workspace/<ID_PLANTA>/recipes/<ID_RECEITA>/revise` | Login, `mash_recipes.create` e `recipe_steps.list`; planta/receita não apagadas |
| POST | `/brewstation/plant-workspace/<ID_PLANTA>/recipes/<ID_RECEITA>/ingredients/<ID_INGREDIENTE>/edit-data` | Login, `recipe_ingredients.update`; contexto válido e receita sem sessões |
| POST | `/brewstation/plant-workspace/<ID_PLANTA>/recipes/<ID_RECEITA>/ingredients/<ID_INGREDIENTE>/sanitize` | Existente 1B; vínculo/decisão de estoque separado |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_LOTE_ANTIGO>` | Retorno ao lote para verificar preservação |
| GET | `/brewstation/recipe-timeline/<ID_RECEITA>` | Consulta existente; receita usada não sincroniza alertas automaticamente |

Os POST são acionados pelos formulários, não pela barra de endereço.
Com `X-Requested-With: XMLHttpRequest`, sucesso retorna `ok/message`; revisão
inclui `recipe_id` da cópia para abrir a seleção. Erros retornam `ok=false/error`:
403 por permissão, 404 por contexto inexistente/apagado/incompatível, 409 por
receita em uso ou conflito de versão, 400 por dados inválidos e 500 por falha
inesperada sem expor detalhe interno. Retorno sem AJAX redireciona à receita
com flash, incluindo a nova seleção no sucesso da revisão.

## Aplicação e banco

```powershell
git am --keep-cr .\brewstation-revisao-receita-ingredientes-1c.patch
```

**Não precisa de `flask db upgrade`.** Nenhuma coluna/tabela/migration nova.
Snapshots usam o JSON existente, preservando o formato de históricos antigos.
Menus, importadores, de-para global, cadastros gerados e runtime permanecem
com seus fluxos avançados atuais. Sem novos caminhos de movimentação.

## Pytest local

Na raiz do projeto e com o ambiente habitual ativado:

```powershell
python -m pytest tests/test_mash_control_ingredient_resolution.py tests/test_plant_workspace.py tests/test_recipe_timeline.py tests/test_weak_ref_value_field.py
python -m pytest tests/test_dashboard_runtime.py tests/test_feature_brew_father.py tests/test_feature_envase.py tests/test_addon_estoque.py
```

Os novos casos verificam cópia completa/remapeamento, versões antigas e
lixeira, isolamento do lote/custo/etapas, unidades, números inválidos, campos
fora do escopo, permissões, pertencimento, histórico/operador, consulta de
receita usada, rollback inclusive de alertas/histórico e `commit=False`.
As demais suítes cobrem compatibilidade com importação, consumo, envase e
runtime. Não usar banco fornecido em modo somente leitura como alvo de escrita
para criar fixtures; usar o ambiente de testes isolado habitual.

## Roteiro visual com resultado esperado

1. Abra a casca GET da planta com receita sem sessões. Em **Sanear ingrediente**,
   confirme os dois formulários separados. Busque unidade pelo combo; não
   deve haver datalist nem lista fixa de referências. Salve uma quantidade
   válida e unidade compatível com o material. A seleção permanece, e a
   conferência/estimativa refletem os dados sem movimentação de estoque.
2. Em uma receita de teste com fervura e lúpulo, altere quantidade e tempo
   (minutos restantes). O alerta automático deve atualizar nome/tempo sem
   duplicar; alerta manual deve permanecer igual. Ao mudar etapa para
   fermentação, o automático deixa a timeline por soft delete. Uso detalhado
   mantém o texto específico importado; segue a regra existente por tipo/etapa.
3. Teste quantidade vazia/zero: deve manter pendência quando o item consome
   estoque, impedindo confirmação. Unidade PCT não deve virar kg/litros;
   ausência de conversão do material continua como aviso. Valores negativos
   são rejeitados no formulário e no servidor; payload inválido não salva
   parcialmente. Vincular material continua sendo uma ação independente.
4. Abra uma receita usada por lote antigo. Os formulários locais ficam
   bloqueados. Abra **Criar revisão desta receita** e cancele o modal:
   nenhuma nova versão deve existir. Repita, anote o motivo e confirme.
   A cópia abre na mesma planta com versão nova e volume correto.
5. Confira os ingredientes/vínculos/especificações, timeline (incluindo
   alertas), fermentação e contextos de água na cópia. Faça uma mudança nela
   e volte ao GET do lote antigo: receita, ingredientes originais, etapas,
   status, timers, confirmação e custo registrado devem permanecer iguais.
   Abrir a receita antiga também não deve criar/alterar alertas automáticos.
6. Consulte Histórico de versões na cópia: snapshot inicial e snapshots
   após alterações devem mostrar operador/motivo e dados planejados completos.
   Revise novamente a versão antiga com versões mais novas existentes: não
   deve colidir com um número já usado. A nova revisão não herda sessões.
7. Confira usuário sem `mash_recipes.create` (ação revisão oculta/POST 403)
   e sem `recipe_ingredients.update` (formulários ocultos/POST 403).
   Verifique temas claro/escuro e navegue Receita → Dashboard → Sessões →
   Receita: combos continuam funcionais, sem listeners/polling duplicados.
8. Com dados saneados na cópia, gere uma sessão em planta de teste. Ela deve
   referenciar a versão nova. Gerar, consultar e estimar continuam sem baixa;
   confirmação continua pela ação existente do lote, com modal e regra única.
   Repetir confirmação não pode consumir duas vezes (regressão nas suítes).

## Verificação da entrega e pendências

Entrega por `git format-patch`; sintaxe Python/JSON, scripts JavaScript,
`git diff --check` e aplicação com `git am --keep-cr` em checkout isolado
verificados pelo assistente. Pytest e renderização visual não executados aqui.

Etapas 2–6 continuam pendentes: envase/estorno dentro do contexto do lote,
dashboards avançados/manutenção, operações restantes de sessões/automação e
matriz de cobertura de menus. O 1C não adiciona/remove ingredientes nem edita
água/fermentação ou todos os campos básicos da receita no workspace; essas
manutenções avançadas continuam pelos acessos existentes. Proteção local não
é uma nova política universal para importadores, de-para global ou operações
explícitas de edição/ressincronização de timeline no runtime. Nenhum menu foi
ocultado nesta entrega. Reconhecimento de alarmes não foi refeito.
