# 27 — Proposta: Sincronização Seletiva de Receitas do BrewFather

> **Status: [EXECUTADO] (2026-09-01).** Implementado e testado —
> `brewfather_client.list_recipes_basico()`/`get_recipe_normalizado()`
> novos (get_recipes() refatorado pra compor os dois, sem duplicar
> lógica de normalização), `sync_service.listar_receitas_disponiveis()`/
> `sincronizar_selecionadas()`, tela nova
> `brewfather_syncs/disponiveis.html`. 8 testes novos, suíte completa
> sem regressão.
>
> **Achado real ao implementar, fora do escopo original desta skill
> mas corrigido junto**: as rotas `/sincronizar` e `/pendentes` (De-Para)
> já existiam no código, mas **nenhum template linkava pra elas** —
> só acessíveis por URL direta, órfãs na UI. `_acoes_em_massa_extra.html`
> de `brewfather_syncs` (hook criado na skill 25, nunca preenchido) foi
> populado com os 3 links (Selecionar/Sincronizar Tudo/Pendentes),
> resolvendo isso junto com a tela nova.
>
> Nasceu do pedido do Christopher por uma forma de filtrar
> o que é sincronizado do BrewFather. Investigação da API v2 mostrou
> que o filtro não pode acontecer no servidor (BrewFather não expõe
> filtro por tag/pasta na API) — a solução é uma tela de seleção prévia
> no próprio Tesseract, reaproveitando o mesmo padrão de checkbox em
> massa formalizado na skill 25.
>
> Convenção de status igual às skills 05/19/24/25/26: **[DECIDIDO]**
> fechado, pronto pra executar quando autorizado. **[EXECUTADO]** já no
> código. **[ABERTO]** ainda sem decisão.

---

## 0. Motivação e limite real da API do BrewFather

`sync_service.sync_recipes()` hoje chama `brewfather_client.get_recipes()`
→ `GET /recipes?limit=50`, sem nenhum filtro, e importa tudo que
vier — sem chance de escolher um subconjunto.

Verificação na documentação oficial da API v2 (a mesma versão que o
`brewfather_client.py` do Tesseract já usa,
`https://api.brewfather.app/v2`): **`GET /v2/recipes` não expõe filtro
por tag nem por pasta como parâmetro de servidor** — só `include`,
`complete`, paginação (`start_after`, sucessor de `offset`) e
`order_by`/`order_by_direction`. Tag/pasta são recursos de organização
da UI do BrewFather (`docs.brewfather.app/recipes/folders`), não
parâmetros de query da API pública — diferente de `GET /v2/batches`,
que aceita `status` no servidor. Ou seja: **o filtro não pode ser
resolvido na origem** — precisa ser feito no Tesseract, depois de
listar.

---

## 1. Fluxo decidido — listar barato, selecionar, importar só o escolhido [EXECUTADO]

Fluxo atual (`sincronizar()` → `sync_recipes()` → importa tudo) passa a
virar dois passos:

### 1.1 Passo 1 — listagem enxuta

Nova função `listar_receitas_disponiveis()`, chamando `/recipes` com
`complete=false` — retorno enxuto (nome/autor/estilo/tipo), sem gastar
as chamadas mais caras de detalhe por receita (a API tem limite de 150
chamadas/hora por chave, `docs.brewfather.app/api/v1`). Essa lista
alimenta uma tela nova, **não** a importação direta.

### 1.2 Passo 2 — seleção, reaproveitando o padrão da skill 25

A tela nova mostra a listagem enxuta com **checkbox por linha** —
mesmo componente genérico de seleção (`crudgen-bulk-actions.js` /
padrão de barra de ações) já formalizado na skill 25, mesmo fora do
contexto CrudGen puro (é uma tela de sync, não uma listagem de
entidade gerada, mas a mecânica de seleção é a mesma). Filtro local
(nome/estilo/tipo) aplicado sobre essa listagem enxuta — não depende
de nada novo da API.

Um botão "Sincronizar selecionadas" dispara a busca do detalhe
completo (`/recipes/:id`) **só** das receitas marcadas, e roda
`_importar_receita()` só nelas.

### 1.3 Sinalização de "já importada" antes de selecionar [EXECUTADO]

Na listagem enxuta, cada linha é cruzada contra
`MashRecipe.origem_receita_id` já conhecidos no Tesseract, mostrando
um indicador (ex.: badge "Já importada" / "Apagada — pendente de
reimportar" / "Nova"). Isso depende diretamente da correção já
decidida na skill 25 (seção 3.1: `is_deleted=False` no filtro de
`_importar_receita`) — sem ela, uma receita apagada continuaria
aparecendo como "já importada" mesmo depois de removida, escondendo a
real necessidade de reimportar.

---

## 2. Fora de escopo desta skill

- Nenhuma mudança no formato de importação em si
  (`_importar_receita`, resolução de ingredientes via
  `ingredient_resolution_service`) — só o que decide **quais** receitas
  chegam até essa função.
- Filtro por tag/pasta do lado do BrewFather fica descartado
  como abordagem (API não suporta) — não é um "ainda não decidido", é
  uma opção fechada por limitação externa confirmada.
- Aplicação do mesmo padrão de seleção prévia a outros importadores
  futuros (BeerSmith/BeerXML, citados em `MashRecipe.origem_receita`)
  não foi discutida — quando esses importadores existirem, reavaliar
  se cabe o mesmo fluxo de duas etapas.
