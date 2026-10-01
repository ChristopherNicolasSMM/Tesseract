# BrewStation — seletores padrão e largura da aba Sessões

Correção posterior ao 2A.1 validado pelo usuário. Base: `86e1c90`.
Não exige `flask db upgrade`. Sem alterações de estoque, modelos ou menus.

## Inventário da revisão

Busca em HTML/JavaScript/Python de todo o addon, incluindo controles dinâmicos.

| Área | Ajuste/classificação |
| --- | --- |
| Planta: criar/editar mapeamento | Tanque usa `weakref-combo`, limitado aos tanques da planta |
| Receita: gerar sessão | Planta usa combo; preserva a seleção inicial do workspace |
| Dashboard: escolher painel | Combo com seleção atual e navegação por URL existente; workspace preserva a planta |
| Dashboard: escolher sessão | Combo limitado às sessões disponíveis no snapshot; botão Detecção automática |
| Editor de widgets | Tanque, função e sessão do gráfico usam combo; valores existentes preenchidos |
| Tubulação | Origem/destino usam tanques da planta; função pesquisa somente atuadores, gravando `name` |
| Brewfather: de-para de ingredientes | Autocomplete próprio removido; material usa componente padrão e API pública do Core |
| Envase, precificação, ingredientes, inventário Brewfather e cadastros gerados/YeastBank | Referências já usam componente padrão; correção compartilhada de contraste também as atende |
| Status, enums, booleanos, tipos, papéis, fonte/formato de widget e filtros dos portais Brewfather | Permanecem `form-select`; não são referências a cadastros |

Os 173 elementos `<select>` restantes nos templates são controles de opções
fixas/filtros e usam `form-select`. Nenhum `datalist` foi introduzido.
Controllers/services/templates gerados não foram editados.

## Comportamento e manutenção

- O combo consulta `/api/options/<plural>`, com `value_field=name` para funções.
- A extensão genérica opcional `ids` restringe a busca ANTES da paginação.
  `ids=` devolve vazio; IDs inválidos devolvem 400. Registros apagados continuam
  excluídos. O parâmetro delimita opções da interface, **não é autorização**:
  permissões e pertencimento continuam sob responsabilidade das rotas de gravação.
- As listas de IDs vêm do contexto já existente: tanques/painéis da planta e
  atuadores. Sessões do seletor principal preservam a janela do snapshot atual.
  Um registro novo aparece após recarregar o contexto; não se ampliou a cobertura
  do runtime neste patch. A sessão opcional do gráfico mantém a consulta geral
  que antes era possível por ID, sem criar regra de vínculo nova.
- Seleção/limpeza emite `change`; texto digitado sem selecionar não é referência
  válida. Inicialização AJAX permanece idempotente, com descarte de respostas
  antigas ou destinadas a fragmentos removidos.
- Resultados recebem `list-group` e cores explícitas por tema, inclusive hover.
- Na aba Sessões, apenas lista e resumo dividem a primeira linha. Edição,
  ingredientes, envase, etapas e histórico ocupam a largura abaixo; em telas
  estreitas, as colunas empilham. Helpers AJAX e `__tabCleanup` preservados.

## Validação e aplicação

Executados no ambiente de desenvolvimento: três testes Node do componente,
AST dos Python alterados, sintaxe JS (arquivo Core e scripts extraídos dos
partials em dois cenários condicionais), balanceamento dos blocos Jinja e
`git diff --check`. A checagem dos partials não equivale a renderizar Jinja.
Pytest/renderização Flask não executados: dependências indisponíveis.
Patch gerado por `git format-patch`, com aplicação isolada por `git am` e
comparação das árvores. Não há validação visual real concluída neste ambiente.

```powershell
git am --keep-cr .\brewstation-seletores-layout-workspace.patch
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_weak_ref_value_field.py tests/test_weak_ref_display_field.py tests/test_feature_brew_father.py tests/test_feature_envase.py tests/test_precificacao_envase.py -q
node --test tests/js/test_weak_ref_combo.cjs
```

## Roteiro visual e rotas

Use IDs reais e, após aplicar, recarregue os assets com Ctrl+F5.
Repita nos temas claro/escuro e com janela estreita.

1. `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_SESSAO>`:
   lista e resumo na mesma linha; cards seguintes ocupam toda a largura.
   Abra produto resultante na prévia de envase: resultados e hover legíveis;
   selecionar/apagar produto invalida a prévia, sem qualquer baixa de estoque.
2. `/brewstation/plant-workspace/<ID_PLANTA>?tab=plant`:
   criar/editar mapeamento; pesquisar tanque e função. Tanques de outra planta
   não aparecem. Digitar sem selecionar não deve enviar referência inválida.
3. `/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe&recipe_id=<ID_RECEITA>`:
   planta atual pré-preenchida ao gerar sessão; busca de planta funcional.
   Confirmar a seleção e conferir que o lote fica na planta escolhida.
4. `/brewstation/plant-workspace/<ID_PLANTA>?tab=dashboard` e
   `/brewstation/dashboards/<ID_LAYOUT>/view`: selecionar painel e sessão,
   voltar à detecção automática e alternar abas sem polling duplicado.
   O combo de painéis dentro do workspace só oferece a própria planta.
5. Dashboard em Modo Edição: abrir widget existente, conferir nomes de tanque,
   função e sessão do gráfico, alterar/salvar/reabrir. Função persiste pelo nome.
   Na Tubulação: adicionar linha, escolher origem/destino/atuador, salvar e
   reabrir. Tanques de outra planta e sensores não aparecem nas opções de fluxo;
   geometria existente preservada. Referência obrigatória vazia bloqueia envio.
6. `/brewstation/recipe-timeline/<ID_RECEITA>`: verificar combo também fora
   do workspace. `/brewstation/brewfather-syncs/pendentes`: pesquisar material
   e resolver ingrediente; alternativa de cadastrar novo material preservada.
7. `/brewstation/precificacao-envase/?lote_id=<ID_SESSAO>` e cadastros de
   ingredientes/YeastBank: conferir contraste das referências. Filtros de
   status e opções fixas continuam com select padrão.

## Pendências

Aguardam validação local deste patch. 2A.2 (registro de envase), 2B (estorno),
dashboards avançados e demais etapas do plano continuam pendentes.
