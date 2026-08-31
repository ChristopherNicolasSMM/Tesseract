# 25 — Proposta: Ações em Massa como Padrão do CrudGen (Apagar/Inativar) + Aplicação em Ingredientes e MashRecipe

> **Status: [DECIDIDO] — planejamento fechado, implementação não
> iniciada.** Nasceu de "ações em massa" ter sido construída sob
> medida na lista de Materiais (`addon_estoque`, ver BACKLOG.md) e do
> Christopher ter pedido o mesmo padrão em Malte/Lúpulo/Levedura
> (`feature_ingredientes`) e MashRecipe (`feature_mash_control`).
> Investigação real mostrou que a implementação de Materiais foi feita
> à mão dentro de um arquivo **gerado** (`materials/manage.html`, não
> um hook) — arriscando ser perdida no próximo `--overwrite`. Esta
> skill generaliza o padrão pro próprio CrudGen em vez de repetir a
> construção manual em cada tela nova.
>
> Convenção de status igual às skills 05/19/24: **[DECIDIDO]** fechado,
> pronto pra executar quando autorizado. **[EXECUTADO]** já no código.
> **[ABERTO]** ainda sem decisão.

---

## 0. Motivação

A lista de Materiais ganhou checkbox por linha + barra de ações em
massa (Movimentar Estoque / Criar Cotação / Criar Pedido / Modificação
em Massa) construída diretamente em `materials/manage.html` — um
arquivo **gerado** pelo CrudGen, não um `_hooks.py`. Isso significa que
um `tesseract generate --model Material --overwrite` futuro apagaria
essa camada inteira, sem aviso.

Ao planejar o mesmo padrão pra Malte/Lúpulo/Levedura/MashRecipe, ficou
claro que só duas ações (**apagar** e **inativar**) são realmente
genéricas — o resto (Movimentar Estoque, Cotação, Pedido) é específico
de Material. Em vez de reescrever checkbox+barra à mão em cada tela
nova (repetindo o mesmo risco de perda no overwrite), esta skill
propõe: **apagar/inativar em massa viram parte do que o CrudGen gera
por padrão**, e um novo mecanismo de **hook de template** absorve as
ações extras específicas de cada entidade (hoje só Material tem).

---

## 1. Escopo genérico — apagar/inativar em massa via CrudGen [DECIDIDO]

### 1.1 O que passa a ser gerado por padrão em todo `manage.html`

- Coluna de checkbox por linha (`.checkbox-selecionar-<entidade>`,
  `data-<entidade>-id`) + checkbox "selecionar todos" no cabeçalho —
  mesmo HTML/CSS já usado em Materiais, generalizado.
- Barra de ações em massa (`d-none` → `d-flex` conforme seleção),
  com dois botões padrão: **Apagar** (lixeira/`trash` em massa) e
  **Inativar** (só aparece se a entidade tiver campo `ativo` — ver
  seção 1.2).
- Contador "`N` registro(s) selecionado(s)" com o nome da entidade no
  singular/plural corretos, resolvido a partir de `@label`/`@plural`
  (annotations já existentes) — não hardcoded, pra já nascer com o
  texto certo em qualquer entidade nova.

### 1.2 Bifurcação: entidade com `ativo` próprio vs. entidade sem [DECIDIDO]

O CrudGen detecta se o model gerado tem uma coluna `ativo` (Boolean)
própria:

| Caso | Comportamento do botão "Inativar" gerado |
|---|---|
| Model tem `ativo` (ex.: `Material`) | Bulk inativar seta `ativo=False` nos IDs selecionados, direto na própria tabela — reaproveita a função de modificação em massa já existente (`modificar_materiais_em_massa`, ver seção 2). |
| Model **não** tem `ativo` (ex.: `Malte`/`Lupulo`/`Levedura`) **mas** tem um `@weak_ref` **obrigatório** pra uma entidade que tem `ativo` | Bulk inativar delega — chama a função pública de modificação em massa do módulo dono do `ativo`, passando o(s) id(s) resolvidos via weak_ref. **Decisão de sessão**: Malte/Lúpulo/Levedura usam esse caminho, delegando pra `Material.ativo` via `estoque_service.modificar_materiais_em_massa(material_ids, {"ativo": False})` — função **já existente**, sem necessidade de criar update novo em `material_lookup` (que continua só leitura). |
| Model não tem `ativo` nem weak_ref pra algo que tenha | Botão "Inativar" **não é gerado** — só "Apagar" aparece. |

Essa bifurcação evita duas armadilhas: (a) criar uma segunda noção de
"ativo" desalinhada da fonte de verdade (`Material.ativo`), e (b) gerar
um botão sem função nenhuma por trás em entidades que não têm nem o
campo nem pra onde delegar.

### 1.3 Labels contextuais por entidade [DECIDIDO]

Texto dos botões/confirmações é montado a partir de `@label`/`@plural`
já existentes em cada model (`Malte`/`Maltes`, `Lúpulo`/`Lúpulos`,
`Levedura`/`Leveduras`), nunca um texto genérico único tipo "Inativar
itens". Mesma regra vale pro diálogo de confirmação
(`data-confirm-key`, já usado em `trash` individual — reaproveitado
aqui, só trocando a chave de i18n pro plural).

### 1.4 Novo mecanismo — "hook de template" [DECIDIDO]

Hoje só existe hook em Python (`controller_hooks.py.j2`,
`service_hooks.py.j2`, `routes_hooks.py.j2`, skill 01/03) — não existe
ponto de extensão em template. `manage.html.j2` passa a gerar um ponto
de inclusão:

```
{% include "<addon>/<entidade>/_acoes_em_massa_extra.html" ignore missing %}
```

Regras (mesma lógica de qualquer arquivo `_hooks.py`, skill 00/01):

- `_acoes_em_massa_extra.html` é criado **uma única vez** pelo CrudGen
  (vazio/comentado, como esqueleto) e **nunca sobrescrito**, mesmo com
  `--overwrite`.
- Se ausente ou vazio, `ignore missing` faz o Jinja simplesmente não
  renderizar nada extra — a tela mostra só Apagar/Inativar genéricos.
- Botões específicos (os 4 de Materiais: Movimentar Estoque, Criar
  Cotação, Criar Pedido, Modificação em Massa) migram pra dentro desse
  arquivo — o genérico (checkbox, barra, Apagar/Inativar) continua
  vindo do `manage.html.j2` mesmo depois da migração.

### 1.5 JS — genérico único, não repetido por entidade [DECIDIDO]

Um único arquivo `core/static/js/crudgen-bulk-actions.js` cuida de:
seleção de linha/"selecionar todos", contagem, mostrar/esconder barra,
e as duas ações genéricas (apagar/inativar via fetch JSON). Cada tela
gerada só referencia esse arquivo (sem duplicar a lógica de seleção em
JS próprio). `materials-acoes-em-massa.js` é refatorado pra manter só
os 4 fluxos específicos, delegando seleção/contagem pro script
genérico (evita duas fontes de verdade sobre "quem está selecionado").

### 1.6 Risco assumido — não quebrar a grid de Materiais [DECIDIDO]

Antes de rodar `--overwrite` em `materials/manage.html` de verdade:
gerar num clone limpo, comparar que os 4 modais/botões extras (agora
vindo de `_acoes_em_massa_extra.html`) continuam presentes e
funcionais, rodar a suíte completa, só então aplicar. Mesma disciplina
de sempre (ver README.md/fluxo de trabalho) — nenhum passo novo além
do já praticado.

---

## 2. Aplicação em Malte/Lúpulo/Levedura (`feature_ingredientes`) [DECIDIDO]

Nenhuma migration nova — os 3 já têm `is_deleted`/`deleted_at`
(apagar em massa é direto) e nenhum tem `ativo` próprio (inativar em
massa delega pro `Material` via `material_id`, seção 1.2).

| Entidade | Apagar em massa | Inativar em massa |
|---|---|---|
| `Malte` | `is_deleted=True` local | Delega — `Material.ativo=False` via `estoque_service.modificar_materiais_em_massa` |
| `Lupulo` | idem | idem |
| `Levedura` | idem | idem |

### 2.1 Painel unificado com abas — [ABERTO]

Investigação do projeto legado (`BrewStation`,
`plugin_integ_bFather/templates/estoque.html`) mostrou uma tela única
de "Estoque de Ingredientes" com filtro por tipo (`malte`/`lupulo`/
`levedura`/`adjunto`) em vez de 3 telas CrudGen separadas. O Tesseract
já tem precedente estrutural equivalente —
`feature_yeast_bank/templates/feature_yeast_bank/painel.html` +
`yeast_bank_painel.py` (tela própria fora do padrão CrudGen, agregando
entidades em abas).

**Decisão em aberto**: unificar Malte/Lúpulo/Levedura num
`ingredientes_painel.html` no mesmo molde (reaproveitando os bulk
actions genéricos da seção 1) é uma extensão desejável, mas **não
bloqueia** a entrega do bulk actions simples nas 3 telas atuais — fica
como item independente, a ser autorizado separadamente.

---

## 3. Aplicação em MashRecipe (`feature_mash_control`) [DECIDIDO]

`MashRecipe` já tem `is_active` (Boolean) — apagar/inativar em massa
são locais, sem delegação nem migration nova.

| Ação | Efeito |
|---|---|
| Apagar em massa | `is_deleted=True` nos IDs selecionados |
| Inativar em massa | `is_active=False` nos IDs selecionados |

### 3.1 Correção necessária pra "apagar pra re-sincronizar" funcionar [DECIDIDO]

Achado real: `sync_service._importar_receita()` faz
`MashRecipe.query.filter_by(origem_receita="BrewFather", origem_receita_id=origem_id).first()`
**sem** filtrar `is_deleted=False`. Isso significa que, hoje, apagar
(ou inativar) uma receita BrewFather **não força reimportação** — a
próxima sync encontra o registro (deletado ou não) e simplesmente
retorna ele, sem recriar nada.

**Correção**: adicionar `is_deleted=False` ao filtro de
`_importar_receita()`. Com isso, uma receita apagada em massa passa a
ser tratada como "não existe" na próxima sincronização, e uma nova
versão é criada do zero. Sem esse ajuste, o bulk apagar/inativar de
MashRecipe é só limpeza visual — não entrega o resultado que motivou o
pedido ("apagar para re-sincronizar").

> Nota: esta correção também é pré-requisito direto da skill 27
> (sincronização seletiva do BrewFather) — a tela de seleção proposta
> lá depende de conseguir distinguir "nunca importada" de "apagada,
> pendente de reimportar".

---

## 4. Fora de escopo desta skill

- Os 4 botões específicos de Materiais continuam existindo — só mudam
  de arquivo (`_acoes_em_massa_extra.html`), sem mudança de
  comportamento.
- Nenhuma alteração em `Composicao`, `Envase`, custo de industrialização
  ou sincronização do BrewFather — ver skills 26 e 27.
