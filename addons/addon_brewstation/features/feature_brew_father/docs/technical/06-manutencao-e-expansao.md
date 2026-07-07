# 06 — Manutenção e Expansão (Feature Brew Father)

## Como funciona o de-para (visão prática)

O diagrama de sequência completo já vive em
`features/feature_mash_control/docs/technical/03-fluxos.md` ("Sequência:
importação de receita + resolução de ingrediente") — não duplicado
aqui. Esta seção é o complemento prático: **onde cada passo mora no
código real** e como operar o fluxo manualmente quando precisar
debugar.

1. **Sincronizar** (`POST /brewstation/brewfather-syncs/sincronizar`,
   `controller/brewfather_syncs_hooks.py::sincronizar`) chama
   `sync_service.sync_recipes()`, que busca receitas via
   `brewfather_client.get_recipes()` e, pra cada uma, chama
   `_importar_receita()`.
2. **Por ingrediente**, `_importar_receita()` chama
   `ingredient_resolution_service.resolver_ingrediente(...)`, que:
   - Consulta `IngredientMapping` (cache de-para: `origem_receita` +
     `descricao_origem` → `material_id`). Se já existe, cria o
     `RecipeIngredient` direto com `status_resolucao="resolvido"`.
   - Se não existe, cria com `status_resolucao="pendente_depara"` e
     `material_id` nulo — **nunca** resolve por aproximação sozinho,
     só por mapeamento já confirmado antes.
3. **Tela de-para** (`GET /brewstation/brewfather-syncs/pendentes`,
   `controller/brewfather_syncs_hooks.py::pendentes`) lista os
   `RecipeIngredient` pendentes, agrupados por `descricao_origem`
   (evita mostrar a mesma string N vezes se apareceu em várias
   receitas).
4. **Resolver manualmente** (`POST /brewstation/brewfather-syncs/pendentes/resolver`,
   `::resolver_pendente`) aceita dois caminhos, escolhidos pelo
   formulário:
   - `material_id` de um Material já existente (busca via
     `GET /api/brewstation/brewfather-syncs/buscar-materiais` —
     `material_lookup.buscar_material_por_termo`, combo de busca na
     tela).
   - `novo_material_nome` — cadastra um Material novo em
     `addon_estoque` na hora, resolvendo os campos obrigatórios
     (`sku`/`origem_id`/`tipo_produto_id`/`categoria_id`) pelo mesmo
     caminho do autocreate (seção abaixo), com `pendente_revisao=True`.
   Qualquer um dos dois caminhos termina chamando
   `ingredient_resolution_service.confirmar_mapeamento(...)`, que grava
   o de-para em `IngredientMapping` **e** resolve, na mesma operação,
   todos os `RecipeIngredient` pendentes com a mesma
   origem+descrição — não só o que motivou a chamada.
5. **Cadastrar todos automaticamente** (`POST /brewstation/brewfather-syncs/pendentes/cadastrar-todos`,
   `::cadastrar_todos_automaticamente` → `ingredient_autocreate_service.cadastrar_todos_pendentes`)
   é o atalho em lote — cria um Material novo pra cada
   `descricao_origem` pendente sem passar pela tela, um por um. Ver
   seção seguinte pra como cada campo obrigatório é resolvido nesse
   caminho.

### Onde o de-para "vaza" pra fora desta Feature

`IngredientMapping` e `RecipeIngredient` são tabelas de
`feature_mash_control`, não desta Feature — `feature_brew_father` só
orquestra a chamada. Isso é proposital (skill 02: FK real só dentro do
mesmo Addon — `feature_mash_control` e `feature_brew_father` são do
mesmo Addon `brewstation`, então isso é permitido, mas a Feature de
sync não precisa duplicar a tabela). Se um futuro importador
(`feature_beersmith`, BeerXML) precisar do mesmo de-para, ele chama o
mesmo `ingredient_resolution_service` — não recria a lógica.

---

## Autocreate: como um Material nasce sem intervenção manual

`ingredient_autocreate_service.py` resolve os 4 campos obrigatórios de
`Material` (`sku`/`origem_id`/`tipo_produto_id`/`categoria_id`, ver
BACKLOG.md — ampliação de Material) que a API do BrewFather não
fornece:

| Campo | Resolução |
|---|---|
| `tipo_produto_id` | Sempre o seed `TipoProduto("Insumo")` — `estoque_seed.get_or_create_tipo_produto_insumo()` |
| `origem_id` | Sempre o seed `Origem("A definir")` — `estoque_seed.get_or_create_origem_a_definir()` |
| `categoria_id` | `get_or_create` por nome (`_get_ou_criar_categoria`), reaproveitando o mapeamento `tipo_ingrediente → categoria` |
| `sku` | `_gerar_sku(nome, tipo_ingrediente)` — `{TIPO}-{10 primeiros caracteres do nome}`, maiúsculo sem acento, sufixo numérico em colisão. `{TIPO}` vem de `_TIPO_PARA_SKU_PREFIXO` (`MALTE`/`LUPULO`/`LEVEDURA`), fallback `INSUMO` pra tipo não mapeado (ex.: `adjunto`/`agua_agente` — ver item (c) do BACKLOG, ainda não implementado) |
| `pendente_revisao` | Sempre `True` nesse fluxo — sinaliza na tela de-para, nunca bloqueia `Movimentacao`/`Saldo` |

**Se um tipo de ingrediente novo for adicionado** (ex.: quando o item
(c) do BACKLOG — adjuntos/água — for implementado), `_TIPO_PARA_SKU_PREFIXO`
ganha uma entrada nova só se um prefixo de SKU específico for
desejado; sem entrada, cai no fallback `INSUMO` automaticamente — não
quebra, só fica menos específico.

Ver também `docs/skills/11-referencia-fraca-e-display-field.md` para
como `material_id` (referência fraca) é exibido nas telas geradas de
`RecipeIngredient`/`IngredientMapping` uma vez resolvido.

---

## Como adicionar um campo novo importado do BrewFather

Checklist prático, na ordem em que os dados fluem (mesmo caminho que
o item (c) do BACKLOG — adjuntos/água — vai seguir quando for
implementado):

1. **`services/brewfather_client.py`** — o parser do payload bruto da
   API. Cada categoria de dado (`fermentables`, `hops`, `yeasts` hoje;
   `miscs`, `water` no item (c)) tem sua própria função
   `_normalizar_X(recipe_raw)`, chamada dentro de `get_recipes()`, que
   devolve uma lista de dicts num formato interno comum (não o
   formato bruto da API — já traduzido pros nomes de campo que
   `sync_service`/`ingredient_resolution_service` esperam).
2. **Novo campo em `RecipeIngredient`** (só se o dado não couber nos
   campos já existentes — `descricao_origem`/`quantidade`/
   `unidade_medida`/`tempo_adicao_min`/`etapa`/`uso_detalhado`/
   `tipo_ingrediente`/`cor_ebc`/`rendimento`/`alpha_acidos`/
   `atenuacao`): seguir o checklist genérico de
   `docs/technical/06-manutencao-e-expansao.md` (sistema) — "Como
   adicionar um campo a um model existente". `RecipeIngredient` já usa
   o padrão de controller genérico (introspecção de `__table__`), não
   precisa regenerar via CrudGen pra aparecer nas telas.
3. **`services/ingredient_resolution_service.py::resolver_ingrediente`**
   — se o campo novo for um parâmetro novo (não uma tabela nova),
   ganha um parâmetro `nome_do_campo: tipo | None = None` a mais na
   assinatura, passado direto pro construtor de `RecipeIngredient`.
   Padrão já usado por todos os campos de spec existentes (`cor_ebc`,
   `alpha_acidos`, etc.).
4. **`services/sync_service.py::_importar_receita`** — passa o valor
   novo do dict normalizado (passo 1) pra chamada de
   `resolver_ingrediente(...)` (passo 3).
5. **Tabela nova** (caso do item (c) — `WaterProfile`, que não é por
   ingrediente, é por receita): não passa por
   `ingredient_resolution_service` — é gravada direto em
   `_importar_receita`, mesmo padrão já usado por `MashStep`/
   `FermentationStep` (loop simples sobre a lista normalizada, um
   `db.session.add()` por item, sem de-para nenhum envolvido — de-para
   só existe pra ingrediente, que referencia `Material`).
6. **Docs**: atualizar `features/feature_mash_control/docs/technical/03-fluxos.md`
   (o diagrama de sequência é a fonte única sobre o fluxo de
   importação — evitar duplicar aqui) e
   `features/feature_mash_control/docs/technical/04-modelo-de-dados.md`
   se for tabela/coluna nova.

---

## Erros conhecidos e pegadinhas

- **`sincronizar()` engole qualquer exceção** (`except Exception` genérico,
  vira flash de erro) — bom pra não quebrar a tela em produção, mas
  dificulta debug local. Rodar `sync_service.sync_recipes()` direto
  num shell (`flask shell`) pra ver o traceback completo, se o flash
  de erro não for específico o bastante.
- **`confirmar_mapeamento` assume que toda `RecipeIngredient` pendente
  com a mesma `descricao_origem` tem a mesma `origem_receita`** da
  chamada — não resolve pendências de uma receita com origem diferente
  mesmo que a descrição bata (ver docstring da função). Isso é
  intencional (de-para é por fonte, "Malte Pilsen" do BrewFather e
  "Malte Pilsen" de um BeerXML futuro podem apontar pra Materiais
  diferentes), não um bug.
- **`_gerar_sku` e `_get_ou_criar_categoria`** são funções "privadas"
  (prefixo `_`) de `ingredient_autocreate_service.py`, mas são
  importadas diretamente por `brewfather_syncs_hooks.py` (cadastro
  rápido na tela de-para) — reaproveitamento intencional dentro do
  mesmo Addon, não vazamento acidental.
