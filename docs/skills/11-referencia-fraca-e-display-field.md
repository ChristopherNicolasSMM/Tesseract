# 11 — Referência Fraca: `@display_field` + `@weak_ref` + `/api/options`

> **Status: [DECIDIDO], pendente de implementação.** Nasceu da
> retomada do item de backlog "tela de insumos não mostra o nome do
> Material" — investigação inicial (sem olhar o PyTeca) desenhou uma
> solução por hook manual em 6 arquivos; a pedido, essa solução foi
> descartada em favor de investigar diretamente o código real do
> `ChristopherNicolasSMM/PyTeca`, que já resolvia um problema
> parecido (lá, sempre com FK real). O resultado é este documento.
>
> Convenção de status (igual skill 05, 09, 10): **[DECIDIDO]** /
> **[ABERTO]** / **[PENDENTE-SKILL]**.

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

## 6. `/api/options/<table_name>` — combo de busca genérico

**[DECIDIDO]** Novo endpoint em Core, mesmo formato de resposta do
PyTeca (compatível com Select2 sem JS novo de parsing):

```
GET /api/options/<table_name>?search=xxx&page=1
→ { "results": [{"id": ..., "text": ...}], "pagination": {"more": bool} }
```

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

**[ABERTO] Dependência não resolvida**: Select2 (JS/CSS) **não está**
nos assets estáticos do projeto hoje (`static/`, herdados do Nice
Admin — Bootstrap/ApexCharts/Boxicons/Quill/TinyMCE/ECharts, sem
Select2). Duas saídas, nenhuma decidida:
1. Vendorizar Select2 (baixar e versionar os arquivos, mesmo padrão
   dos demais assets do Nice Admin).
2. Usar uma alternativa mais leve (ex.: `<datalist>` nativo do HTML5,
   sem paginação/busca assíncrona real — mais simples, mas sem busca
   server-side pra tabelas grandes).
Decidir antes de implementar a seção 6 — a seção 2-5 (exibição
read-only) não depende dessa decisão e pode ser implementada primeiro.

---

## 7. Onde isso muda a UI de fato

`templates/.../detail.html`, campo com `@weak_ref`: deixa de ser
`<input type="text">` puro digitando id cru — vira um combo de busca
assíncrona (uma vez resolvida a pendência da seção 6), mostrando o
nome ao digitar, persistindo o id no submit. Resolve exibição e edição
ao mesmo tempo — hoje o usuário digita o id na mão pra trocar o
material vinculado a um `Malte`, por exemplo.

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

- [ABERTO] Seção 6 — vendorizar Select2 vs. alternativa mais leve
  (`<datalist>`), decidir antes de implementar o combo de busca.
- Nenhuma outra pendência de arquitetura — seções 1–5 e 7–8 estão
  fechadas, aguardando autorização explícita pra implementar (fase de
  documentação apenas até aqui).
