# 11 — Referência Fraca: `@display_field` + `@weak_ref` + `/api/options`

> **Status: EXECUTADA (2026-07-07).** Nasceu da retomada do item de
> backlog "tela de insumos não mostra o nome do Material" —
> investigação inicial (sem olhar o PyTeca) desenhou uma solução por
> hook manual em 6 arquivos; a pedido, essa solução foi descartada em
> favor de investigar diretamente o código real do
> `ChristopherNicolasSMM/PyTeca`, que já resolvia um problema
> parecido (lá, sempre com FK real). O desenho abaixo foi
> implementado como estava documentado, sem desvios de arquitetura —
> ver seção 10 para o único achado real durante a execução (bug de
> regeneração do CrudGen, não relacionado à decisão em si).
>
> Convenção de status (igual skill 05, 09, 10): **[DECIDIDO]** /
> **[EXECUTADO]** / **[ABERTO]** / **[PENDENTE-SKILL]**.

---

## 0. Contexto — por que não dá pra portar o mecanismo do PyTeca 1:1

Investigação direta no repositório real (`ChristopherNicolasSMM/PyTeca`,
`src/annotations/__init__.py`, `src/api/routes/core/options_routes.py`,
`src/model/bookstore/loan.py`) encontrou dois mecanismos:

1. **`@display_field(value)`** — decorator de classe, já existe **no
   Tesseract também** (`annotations/__init__.py`, portado na Fase 4),
   mas nunca foi aplicado a nenhum model nem consumido por nenhum
   código. Capacidade morta até esta skill.
2. **`Column("book.title", ...)`** no `@listview` — a listagem gerada
   atravessa um `relationship()` real do SQLAlchemy (`loan.book.title`)
   pra exibir o campo do objeto relacionado direto na coluna.

O mecanismo 2 **não pode ser portado como está**: ele depende de FK
real entre as duas tabelas, no mesmo processo Python, com
`relationship()` de verdade. O PyTeca é monolítico — nunca teve
motivo pra evitar isso. O Tesseract **proíbe FK real entre Addons**
(skill 02, regra de ouro — "FK entre Addons diferentes... proibido em
nível de banco") — `Malte.material_id`, `ItemEnvase.material_id`,
`RecipeIngredient.material_id`, `IngredientMapping.material_id` são
referência fraca de propósito, sem `relationship()` nenhum. A skill
02 continua valendo sem exceção — esta skill não cria FK nova, só
resolve o problema de exibição de outro jeito.

---

## 1. Decisão raiz

**[DECIDIDO]** Duas anotações novas (uma delas já existente, só
recebendo primeiro uso real) resolvem exibição de referência fraca de
forma genérica, e o `core/crudgen/generator.py` passa a gerar a
resolução automaticamente pra qualquer entidade que as declare — não
é mais trabalho manual repetido por entidade.

**[DECIDIDO]** Escopo inclui também portar `/api/options/<table>`
(combo de busca assíncrono) — não fica só na exibição read-only, o
campo de referência fraca no formulário de edição também deixa de
ser um `<input>` de id cru.

---

## 2. `@display_field(value)` — no model ALVO da referência

Já existe em `annotations/__init__.py` (Fase 4, nunca usado). Declara
qual campo representa o "nome" daquele model pra qualquer consumidor
externo — mesma assinatura do PyTeca, sem mudança:

```python
@display_field("nome")
class Material(db.Model):
    ...
    nome = db.Column(db.String(200), unique=True, nullable=False)
```

Primeiro uso real desta anotação: `Material` (`addon_estoque`). Outros
alvos comuns de referência fraca ganham a mesma anotação conforme
forem identificados — não é exclusivo de `Material`.

---

## 3. `@weak_ref(field, resolver)` — NOVA, no model QUE TEM a referência fraca

Sem equivalente no PyTeca (lá não existe o conceito — toda relação é
FK real). Declara, pro `field` indicado, qual função resolve o valor:

```python
@weak_ref("material_id", resolver="addons.addon_estoque.root.services.material_lookup.get_material")
class Malte(db.Model):
    __tablename__ = "malte"
    material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK — skill 02
```

| Parâmetro | Tipo | Regra |
|---|---|---|
| `field` | `str` | Nome da coluna que é referência fraca (mesma tabela) |
| `resolver` | `str` | Caminho pontuado (dotted path) até uma função `(id: int \| None) -> dict \| None` |

Múltiplas `@weak_ref` empilhadas se o model tiver mais de um campo de
referência fraca (ex.: um model futuro que referencie `Material` e
`Fabricante` ao mesmo tempo).

**Metadado exposto**: `get_model_metadata(cls)` (já existente) ganha a
chave `"weak_refs"` — lista de `{"field": ..., "resolver": ...}` — o
gerador lê daqui, mesma mecânica de `_choices_fields`/`_permissions`
já usada por `@choices`/`@permission`.

---

## 4. Contrato do resolver — chave `"display"` obrigatória

Toda função apontada por `resolver=` devolve um dict (ou `None`) com,
no mínimo, a chave `"display"` — calculada a partir do
`@display_field` do model alvo, nunca hardcoded no lado de quem
consome (é exatamente esse desacoplamento que faz a anotação valer a
pena — se `Material` trocar o campo de exibição de `nome` pra outro
campo um dia, nenhum consumidor externo precisa mudar).

```python
# addons/addon_estoque/root/services/material_lookup.py — AJUSTE, função já existe
def get_material(material_id: int | None) -> dict | None:
    if not material_id:
        return None
    obj = Material.query.filter_by(id=material_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(Material, "_display_field", "id")
    data["display"] = getattr(obj, display_field, None) or f"Material #{obj.id}"
    return data
```

Toda função de lookup pública já existente que sirva de alvo de
`@weak_ref` precisa dessa chave — é enriquecimento do que já existe
(`material_lookup.get_material`, e futuramente qualquer outro lookup
público de outro Addon), não é função nova.

Se o resolver devolver `None` (referência fraca sem garantia de
integridade — ex.: Material apagado), quem consome cai pro valor cru
sem erro, nunca quebra a tela.

---

## 5. Geração (`core/crudgen/generator.py`) — comportamento por tela

Ao gerar controller pra uma entidade com `@weak_ref` declarado:

- **`manage()` (lista)**: pra cada `item`, resolve os campos com
  `@weak_ref` chamando o `resolver` e monta um dict auxiliar (ex.:
  `resolved_refs[item.id][field] = resolved["display"]`), passado ao
  template.
- **`detail()`**: mesma resolução, só que pro registro único.

Template gerado (`manage.html`/`detail.html`) decide o que fazer com
isso — **comportamento diferente por tela, não é substituição
uniforme**:

| Tela | Comportamento |
|---|---|
| `manage.html` (lista, célula não-editável) | Substitui o valor cru pelo `display` resolvido diretamente na célula |
| `detail.html` (formulário, `<input>` editável ligado ao POST) | **Nunca** altera `value=` do input (quebraria o save — submeteria string em vez de id). O nome resolvido aparece como texto de apoio (`<small class="text-muted">`) ao lado/abaixo do campo — substituído pelo combo de busca da seção 6, quando essa parte entrar |

**Escopo desta rodada**: qualquer entidade nova com `@weak_ref`
declarado já nasce coberta — não é mais preciso repetir isso à mão
por entidade. As 6 entidades já identificadas (`Malte`, `Lupulo`,
`Levedura`, `ItemEnvase`, `RecipeIngredient`, `IngredientMapping`)
ganham a anotação e regeneram via `python run.py generate --overwrite`.

---

## 6. `/api/options/<plural>` — combo de busca genérico

**[EXECUTADO]** Novo endpoint em Core, mesmo formato de resposta do
PyTeca (compatível com Select2 sem JS novo de parsing):

```
GET /api/options/<plural>?search=xxx&page=1
→ { "results": [{"id": ..., "text": ...}], "pagination": {"more": bool} }
```

**Ajuste em relação à proposta inicial**: a URL usa `<plural>` (o
mesmo valor de `@plural` do model alvo — `"materials"` pra `Material`),
não o nome real da tabela (`tesseract_estoque_material`). Motivo:
`plural` já é a chave estável usada em toda rota gerada pelo CrudGen —
reaproveitar evita introduzir uma segunda convenção de identificador
só pra isto. `@weak_ref` ganhou o parâmetro `options` (o `plural` do
alvo) pra fazer essa ligação — sem ele, o campo não ganha combo, só
o texto de apoio (seção 5).

**Diferenças em relação ao PyTeca** (Tesseract tem RBAC, o PyTeca não
tinha essa preocupação no endpoint):

- Exige `@login_required` no mínimo.
- **Escopo restrito, não é `db.Model.__subclasses__()` livre**: só
  tabelas cujo model declara `@display_field` são elegíveis — evita
  expor `tesseract_user`/`tesseract_role`/etc. sem querer. Tabela fora
  da whitelist devolve 400, mesma convenção de erro que o PyTeca já
  usava pra tabela desconhecida.
- Campo de busca: usa o próprio `_display_field` como campo textual
  (`ilike`), mesmo default do PyTeca — sem lista separada de
  `search_fields` por enquanto (o PyTeca tinha isso mais elaborado,
  mas não há caso de uso real ainda que justifique a complexidade
  extra aqui).

**[EXECUTADO] Dependência resolvida**: decisão tomada na implementação
— **vanilla JS**, sem Select2/jQuery (`static/js/weak_ref_combo.js`).
O projeto não tinha nenhum dos dois nos assets estáticos (herdados do
Nice Admin), e vendorizar uma lib nova só pra isto não se justificava.
O endpoint devolve o formato de resposta nativo do Select2 de
propósito — se o projeto adotar a lib por outro motivo no futuro, só
trocar o JS consumidor, o backend não muda.

---

## 7. Onde isso muda a UI de fato

`templates/.../detail.html`, campo com `@weak_ref(..., options=...)`:
deixa de ser `<input type="text">` puro digitando id cru — vira um
combo de busca assíncrona (`.weakref-combo`, `static/js/weak_ref_combo.js`),
mostrando o nome ao digitar, persistindo o id (`<input type="hidden">`)
no submit. Campo com `@weak_ref` mas sem `options` mostra só o nome
resolvido como texto de apoio ao lado do `<input>` de id cru — sem
combo. Resolve exibição e edição ao mesmo tempo — antes o usuário
digitava o id na mão pra trocar o material vinculado a um `Malte`,
por exemplo.

---

## 8. Escopo desta rodada (retomando o pedido original)

Entidades identificadas com o problema (revisão anterior a esta
skill, ver `BACKLOG.md`):

| Entidade | Feature | Campo |
|---|---|---|
| `Malte` | `feature_ingredientes` | `material_id` |
| `Lupulo` | `feature_ingredientes` | `material_id` |
| `Levedura` | `feature_ingredientes` | `material_id` |
| `ItemEnvase` | `feature_envase` | `material_id` |
| `RecipeIngredient` | `feature_mash_control` | `material_id` |
| `IngredientMapping` | `feature_mash_control` | `material_id` |

Todas resolvem pro mesmo alvo (`addon_estoque.Material`) e pelo mesmo
resolver (`material_lookup.get_material`) — `@weak_ref` repetido 6x
com os mesmos parâmetros, `@display_field("nome")` uma vez só em
`Material`.

---

## 9. Pendências desta skill

Nenhuma — todas as seções (1–8) foram executadas sem desvio da
decisão original. Ver seção 10 para o único achado real durante a
execução (bug pré-existente do CrudGen, não relacionado a esta
decisão de arquitetura).

---

## 10. [CORRIGIDO em 2026-07-07] Bug encontrado na execução — regeneração de entidade com `relationship()` real

Não é uma decisão desta skill, é um achado colateral, corrigido numa
sessão seguinte (registrado aqui e em `BACKLOG.md` pra manter o
histórico): `python run.py generate --model ... --overwrite` falhava
com `NoForeignKeysError` ao regenerar `ItemEnvase` e `RecipeIngredient`
(ambas têm `relationship()` real pra outra tabela do mesmo
Addon/Feature — `Envase`, `MashRecipe`).

**Causa raiz**: `core/cli.py` (`generate_cmd`) recarregava o arquivo
do model isoladamente via `importlib.util.spec_from_file_location`, à
parte do processo normal de boot. Nessa mesma sessão de CLI, o boot
completo (`create_app()`, disparado pelo `@with_appcontext`) já tinha
importado e **renomeado** a tabela real de `Envase` pra
`tesseract_brewstation_envase` (aplicação do prefixo tri-nível, skill
02). Quando o `generate_cmd` reimportava `item_envase.py` do zero, a
`ForeignKey("envase.id")` do código-fonte (nome curto, sem prefixo —
correto, é assim que todo model é escrito) não encontrava mais
nenhuma tabela chamada literalmente `envase` na metadata
compartilhada, porque ela já tinha sido renomeada minutos antes na
mesma sessão.

**Correção aplicada**: `generate_cmd` passa a reimportar o model pelo
caminho de pacote real (dotted path via `importlib.import_module`) em
vez de recarregar o arquivo isolado — reaproveita a mesma classe já
mapeada corretamente pelo boot normal, sem duplicar a definição de
tabela. Fallback pro carregamento isolado antigo mantido só pro caso
raro de o arquivo ainda não ser membro de pacote importável.

**Cobertura de teste**: `test_phase4_crudgen.py` só testava a função
`generate()` chamada direto com a classe já em memória — nunca o
carregamento via CLI, que é onde o bug vivia. 3 testes novos em
`tests/test_crudgen_cli_generate_relationship_bug.py` fecham essa
lacuna, invocando o comando real via `app.test_cli_runner()`.
