# 20 — Proposta: CrudGen reconhece tipo SQLAlchemy e gera HTML + validação correspondente

> **Status: [PROPOSTA] — documento de análise, nenhuma linha de
> implementação nesta skill.** Registrado como backlog em 2026-08-20,
> expandido em 2026-08-21 (achados reais ao usar `YeastContainer`/
> `YeastBankItem` — skills 14/15/16). Esta skill é só a Etapa 1
> (diagnóstico + proposta); a implementação é uma fase própria,
> aguardando autorização explícita depois de revisar este documento —
> mesma regra de ouro do projeto (skill 00: ajustar/registrar a
> decisão antes de codar).

---

## A. Diagnóstico do estado atual

O CrudGen já tem uma camada de validação HTML5 real — não é greenfield.
`core/crudgen/templates/controller.py.j2` (linhas ~69–84, no
controller gerado) constrói `_FIELD_HTML_VALIDATIONS` iterando
`get_model_metadata(Model)["validations"]`, que só existe pra campos
com pelo menos uma anotação `@required`/`@max_length`/`@min_length`/
`@min_value` explícita. O template (`detail.html.j2`/`manage.html.j2`)
consome esse dict via `fv = field_html_validations.get(field, {})` e
hoje só tem UMA regra de tipo:

```jinja
<input type="{{ 'number' if fv.get('min_value') is not none else 'text' }}" ...>
```

Ou seja: **o tipo HTML do campo nunca olha pra coluna do banco** — só
olha se `@min_value` foi declarado. Um `db.Float` sem `@min_value`
(caso real: `YeastBankItem.estimated_viability_pct`) sempre vira
`type="text"`, então o navegador não valida nada e a pessoa pode
digitar "0,5" (vírgula) sem aviso algum até o servidor tentar
`float("0,5")` no commit e falhar (essa parte já foi corrigida na
skill 16 pra não perder o formulário — mas o campo continua sem
`type="number"`, então o erro só aparece depois de tentar salvar, não
antes).

`db.Date`/`db.DateTime`/`db.Boolean`/`db.Text`/`db.Enum` não têm
tratamento nenhum — todos caem no mesmo `<input type="text">` (Boolean
é uma exceção parcial: `_BOOLEAN_FIELDS` já existe e a listagem em
`manage.html` já renderiza checkbox lá, mas o formulário de detalhe/
criação não usa esse dado pra decidir o tipo do campo — outra
inconsistência real encontrada nesta análise).

## B. Arquivos envolvidos

| Arquivo | Papel hoje |
|---|---|
| `annotations/__init__.py` | Anotações (`@required`, `@max_length`, `@enum_field`, `@weak_ref`, `@field_labels`...) + `get_model_metadata()` |
| `core/crudgen/generator.py` | Orquestra a geração; `context` passado aos templates **não** carrega metadado por campo — isso é feito dentro do controller gerado (ver linha abaixo) |
| `core/crudgen/templates/controller.py.j2` | **Onde `_FIELD_HTML_VALIDATIONS` é montado de verdade**, a cada boot do app (não na geração) — `for _field, _rules in get_model_metadata(...).get("validations", {}).items(): ...` |
| `core/crudgen/templates/detail.html.j2` | Formulário de edição — 1 bloco `if/elif` decide `enum_field` → `weak_ref` (com options) → `weak_ref` (sem options) → fallback |
| `core/crudgen/templates/manage.html.j2` | Formulário de criação (quick-add) — mesmo bloco duplicado |

## C. Fluxo atual (Model → annotations → generator → template → HTML)

```
Model (@required, @max_length, @min_value, @enum_field, @weak_ref, @field_labels)
  → get_model_metadata(Model)["validations"]  (só os 4 tipos de anotação acima)
  → controller.py gerado: _FIELD_HTML_VALIDATIONS[campo] = {required, maxlength, minlength, min_value}
                          (montado toda vez que o controller é importado — NÃO na geração)
  → render_template(..., field_html_validations=_FIELD_HTML_VALIDATIONS, ...)
  → Jinja: fv = field_html_validations.get(field, {})
  → <input type="{{ 'number' if fv.get('min_value') is not none else 'text' }}">
```

Achado importante pra decisão de arquitetura (seção E): esse fluxo
mostra que a metadata de campo **já é resolvida em runtime** (dentro
do controller gerado, a cada boot), não "congelada" no momento da
geração. Isso significa que estender esse mesmo padrão pra incluir
tipo de coluna não exige mexer no pipeline de geração em si — só no
que o controller gerado calcula.

## D. Problema encontrado

1. Campo `Float`/`Integer`/`Numeric` sem `@min_value` → `type="text"`,
   zero validação nativa, aceita vírgula (achado real, skill 15/16).
2. Campo `Date`/`DateTime`/`Time` → sempre `type="text"`, sem
   date-picker nativo, formato de data livre (risco de erro de
   digitação, sem padronização).
3. Campo `Boolean` no formulário de detalhe/criação → `type="text"`
   (a listagem já resolve isso via `_BOOLEAN_FIELDS`, o formulário
   não usa a mesma informação).
4. Campo `Text` (multi-linha) → `<input>` de uma linha, não
   `<textarea>`.
5. Nenhum separador decimal PT-BR é tratado — mesmo com
   `type="number"`, o HTML5 nativo só aceita ponto; "0,5" continua
   inválido pro navegador (browsers PT-BR mostram teclado numérico com
   vírgula em mobile, piorando ainda mais — o usuário digita o que o
   teclado sugere e é rejeitado).

## E. Solução arquitetural recomendada

Estender o **mesmo mecanismo que já existe** (`_FIELD_HTML_VALIDATIONS`,
resolvido em runtime no controller gerado) com uma segunda fonte de
metadata — introspecção real da coluna SQLAlchemy — em vez de criar um
sistema paralelo. Cada campo passa a carregar um `html_type` calculado
a partir de `model_class.__table__.columns[field].type`, com a mesma
prioridade que `min_value`/`required`/etc. já têm hoje: só entra em
jogo no **fallback** (depois de `@enum_field` e `@weak_ref` — seção J).

## F. Alternativas consideradas

1. **`@calendar`/`@date_field`/`@datetime_field`** (annotation nova
   só pra marcar campo de data).
2. **Introspecção automática do tipo SQLAlchemy** (a recomendada).
3. **Lógica só no Jinja** (o template decide o `type` inspecionando o
   objeto Python column diretamente, sem passar por metadata Python
   antes).
4. **Camada de Field Metadata separada** (`core/crudgen/field_metadata.py`,
   um dict estruturado por campo — `{name, html_type, required,
   step, ...}` — construído uma vez e consumido por tudo).

## G. Prós e contras de cada alternativa

| Alternativa | Prós | Contras |
|---|---|---|
| `@calendar` nova | Explícito, zero ambiguidade | Redundante — `db.Date` já diz que é data; obriga o dev a lembrar de anotar toda coluna de data, ao contrário do resto do projeto (skill 00: informação já expressa no tipo não devia precisar de anotação extra) |
| Introspecção automática | Zero anotação nova pro dev; corrige TODOS os campos existentes automaticamente (inclusive os das 40+ entidades já geradas, não só as novas); usa informação que já existe no model | Precisa mapear tipos customizados/derivados com cuidado (seção sobre riscos) |
| Lógica só no Jinja | Sem mudança em `generator.py`/`annotations` | Jinja não tem acesso limpo a `column.type.python_type` sem passar um objeto Python complexo pro template (hoje os templates só recebem dicts/strings simples — mudar isso quebra o padrão "template burro, lógica no Python" que o resto do projeto segue) |
| Field Metadata separada | Mais "arquiteturalmente pura", um único dict por campo | Overengineering pro tamanho do problema real — os templates já consomem 4 dicts paralelos (`field_html_validations`, `field_labels`, `enum_field_options`, `weak_ref_*`) sem problema; introduzir uma 5ª estrutura que sobrepõe as outras 4 obriga a decidir uma nova precedência do zero, sem necessidade |

## H. Solução escolhida e justificativa

**Introspecção automática (alternativa 2)**, implementada **dentro do
mesmo dict que já existe** (`_FIELD_HTML_VALIDATIONS` ganha uma chave
nova, `html_type`, além de `required`/`maxlength`/`minlength`/
`min_value` que já tem) — não a alternativa 4. Justificativa:

- Menor mudança possível (skill 00, regra de ouro): estende um
  mecanismo real e testado, não cria um novo.
- Backward compatible por construção: campo sem tipo mapeado
  continua caindo em `text`, igual hoje.
- Corrige os outros 40+ CRUDs já gerados no projeto **assim que forem
  regenerados** (`--overwrite`), sem precisar tocar em nenhum model —
  a introspecção lê `__table__.columns` diretamente, não depende de
  anotação nova.
- `@calendar` fica descartada: informação redundante com o que
  `db.Date` já expressa, na contramão da convenção do projeto.

## I. Mapeamento SQLAlchemy → HTML recomendado

| Tipo SQLAlchemy | `html_type` | Atributos extra |
|---|---|---|
| `db.Date` | `date` | — |
| `db.DateTime` | `datetime-local` | — |
| `db.Time` | `time` | — |
| `db.Integer` | `number` | `step="1"` |
| `db.Float` / `db.Numeric` | `number` | `step="any"` + normalização de vírgula→ponto via JS antes do submit (ver riscos) |
| `db.Boolean` | `checkbox` | — |
| `db.Text` | `textarea` | — |
| `db.String` | `text` | (já é o comportamento atual — sem mudança) |
| `db.Enum` (SQLAlchemy nativo, não `@enum_field`) | `select` | Só se o projeto passar a usar `db.Enum` de verdade — hoje todo enum do projeto é via `@enum_field` (string + annotation), não `db.Enum` nativo (nenhum model do projeto usa `db.Enum` hoje — confirmado nesta análise) |

Tipo não mapeado (ex.: `db.JSON`, `db.LargeBinary`) → fallback `text`,
igual comportamento de hoje — nunca quebra por tipo desconhecido.

## J. Precedência entre `@weak_ref`, `@enum_field`, tipo SQLAlchemy e fallback

Confirmada **lendo o bloco `if/elif` real** de `detail.html.j2`/
`manage.html.j2` (não presumida):

```
1. @enum_field         (já é o `if` mais externo hoje)
2. @weak_ref + options (combo assíncrono)
3. @weak_ref sem options (texto + display de apoio)
4. tipo SQLAlchemy → html_type   ← ENTRA AQUI, dentro do `else` que hoje só decide number/text
5. fallback text
```

Justificativa: `@enum_field`/`@weak_ref` são decisões **de negócio**
sobre como aquele campo deve ser editado (lista fechada, referência a
outra entidade) — sempre mais específicas que o tipo bruto da coluna.
Um `device_id` é `Integer` na coluna, mas ninguém quer `<input
type="number">` pra escolher um dispositivo — o `@weak_ref` já resolve
isso hoje, corretamente, antes de qualquer introspecção de tipo. A
introspecção só precisa decidir o que fazer no `else` final, que hoje
já é exatamente "nem enum, nem weak_ref" — não muda a ordem existente,
só enriquece o que já é o último `elif`.

## K. Arquivos que precisarão ser alterados

- `core/crudgen/templates/controller.py.j2` — a mesma função/bloco que
  já monta `_FIELD_HTML_VALIDATIONS` ganha uma segunda fonte
  (introspecção de `{{ class_name }}.__table__.columns`), mesclando
  `html_type` no dict existente por campo.
- `core/crudgen/templates/detail.html.j2` / `manage.html.j2` — o
  `else` final troca `'number' if fv.get('min_value') is not none
  else 'text'` por `fv.get('html_type', 'text')`; `checkbox`/
  `textarea` precisam de HTML diferente de `<input>` (branches novos
  dentro do mesmo `else`).
- `docs/skills/12-crudgen-referencia-completa.md` — documentar o
  `html_type` novo, igual foi feito pra `@field_labels` na skill 15.
- JS pequeno (arquivo a definir — provavelmente
  `static/core/js/...`, não criado ainda) — normalização de vírgula→
  ponto em campos `number` antes do submit, `blur`/`submit` listener,
  sem framework novo (skill 00/13: nada de jQuery/Select2).

## L. Arquivos que NÃO devem ser alterados

- `annotations/__init__.py` — nenhuma annotation nova precisa ser
  criada (decisão da seção H: sem `@calendar`).
- `core/crudgen/generator.py` — o `context` passado aos templates
  continua igual; a introspecção acontece dentro do controller
  gerado, no mesmo padrão que `_FIELD_HTML_VALIDATIONS` já usa hoje
  (achado da seção C).
- `static/js/weak_ref_combo.js` — mecanismo de `@weak_ref` não é
  tocado, precedência (seção J) garante que ele nem chega a competir
  com a introspecção de tipo.
- `core/rules_catalog.py`/`static/js/rule_engine.js` (skill 07b) —
  validação client-side de regra de negócio é camada separada da
  validação HTML5 nativa; este documento não mexe nela.

## M. Estratégia de testes

Reaproveitar a infraestrutura já usada nas skills 14/15/16
(`tests/test_phase14_yeast_container.py`, fixtures `app`/`client`
com login real). Casos mínimos, um por linha do mapeamento (seção I):

1. `db.Date` → `type="date"` no HTML gerado.
2. `db.DateTime` → `type="datetime-local"`.
3. `db.Time` → `type="time"`.
4. `db.Integer` → `type="number"` `step="1"`.
5. `db.Float` → `type="number"` `step="any"`.
6. `db.Boolean` → `<input type="checkbox">` no formulário de detalhe
   (hoje só a listagem acerta isso).
7. `db.Text` → `<textarea>`.
8. `@enum_field` continua `<select>` mesmo em coluna `String` (garante
   que a introspecção não disputa com o enum — seção J).
9. `@weak_ref` com `options` continua combo assíncrono (mesma garantia
   pro weak_ref).
10. `@weak_ref` sem `options` continua texto + display.
11. Campo `nullable=True` sem valor → HTML válido, sem `required`.
12. Valor existente é preservado no campo ao editar (`data.get(field)`
    já funciona pra qualquer `type` novo, sem mudança adicional).
13. `--overwrite` regenerando uma entidade antiga aplica os `html_type`
    novos automaticamente.
14. `--only templates` também aplica (só toca os 2 arquivos HTML,
    mas eles dependem do controller.py já ter `html_type` no dict —
    testar a combinação explicitamente, é o caso mais fácil de
    esquecer).
15. Regressão: toda a suíte de `feature_yeast_bank` (skills 14/15/16)
    continua verde depois da mudança no `else` final dos templates.

## N. Riscos de regressão

- **Tipo customizado/derivado** (`TypeDecorator`, tipo próprio) —
  `column.type.python_type` pode levantar `NotImplementedError`
  (mesmo padrão de exceção que `_coerce_value` já trata hoje, seção
  4.2 da skill 16) — precisa do mesmo `try/except`, cair em `text`
  sem quebrar a geração.
- **Normalização de vírgula→ponto** é o único item desta proposta que
  precisa de JS novo — risco de escopo crescer pra "motor de máscara
  de input" genérico. Escopo travado: só `blur`/`submit`, sem
  biblioteca externa (skill 00/13).
- **`datetime-local` e timezone** — o browser não manda timezone
  nenhuma no valor; `estimated_viability_updated_at`/`discarded_at`
  (`YeastBankItem`) são gravados como UTC ingênuo hoje
  (`datetime.now(timezone.utc)` sem tzinfo persistida) — o HTML5
  `datetime-local` não piora nem resolve esse problema existente, só
  não deve fingir que resolve. Documentar como limitação conhecida,
  não tentar resolver timezone nesta fase.
- **Boolean no formulário de criação/edição** — `_coerce_value` (skill
  16) já sabe converter string de checkbox (`"true"`/`"on"`) pro
  Python bool; o `<input type="checkbox">` não manda nada no POST
  quando desmarcado (comportamento padrão de HTML forms) — o
  `_coerce_value` atual precisa ser conferido pra esse caso
  específico (campo ausente no form data ≠ campo `False` hoje,
  mesma pegadinha clássica de checkbox HTML) — vale um teste
  dedicado (item 6 da seção M) antes de fechar a implementação.

## O. Exemplo concreto: `YeastBankItem` depois da solução

| Campo | Tipo real da coluna | `html_type` resultante |
|---|---|---|
| `prepared_date` | `db.Date` | `date` |
| `expiry_date` | `db.Date` | `date` |
| `last_checked` | `db.Date` | `date` |
| `last_viability_reference_date` | `db.Date` | `date` |
| `estimated_viability_updated_at` | `db.DateTime` | `datetime-local` |
| `discarded_at` | `db.DateTime` | `datetime-local` |
| `estimated_viability_pct` | `db.Float` | `number`, `step="any"` |
| `last_viability_reference_value` | `db.Float` | `number`, `step="any"` |
| `viability_notes` | `db.Text` | `textarea` |
| `discard_reason` | `db.Text` | `textarea` |
| `container_id` | `Integer` + `@weak_ref` | **inalterado** — combo (precedência, seção J) |
| `status` | `String` + `@enum_field` | **inalterado** — select (precedência, seção J) |

## P. Exemplo concreto: `YeastStorageReading` depois da solução

| Campo | Tipo real da coluna | `html_type` resultante |
|---|---|---|
| `recorded_at` | `db.DateTime` | `datetime-local` |
| `temperature_c` | `db.Float` | `number`, `step="any"` |
| `humidity_percent` | `db.Float` | `number`, `step="any"` |
| `device_id` | `Integer` + `@weak_ref` | **inalterado** — combo (precedência, seção J) |

## Q. Plano de implementação em etapas pequenas (quando autorizado)

1. Função de mapeamento tipo→`html_type` (seção I), com
   `try/except` pra tipo não reconhecido (seção N) — sem tocar
   template ainda, só a função isolada + teste unitário direto nela.
2. Mesclar `html_type` dentro de `_FIELD_HTML_VALIDATIONS` no
   `controller.py.j2` (mesma variável, chave nova) — regenerar
   `YeastContainer`/`YeastBankItem` com `--overwrite` como primeiro
   caso real, conferir os testes 1–7 (seção M) nelas.
2b. Testar especificamente o caso Boolean (`_coerce_value` +
    checkbox ausente no POST, risco N) antes de seguir — é o único
    item desta lista com risco de comportamento incorreto silencioso.
3. `else` final de `detail.html.j2`/`manage.html.j2` passa a usar
   `fv.get('html_type', 'text')`, com branches novos pra
   `checkbox`/`textarea` (não são `<input>` simples).
4. JS de normalização de vírgula→ponto (escopo travado, seção N) —
   só depois do HTML5 `type="number"` já estar no ar, pra confirmar
   que o navegador já bloqueia a maior parte do problema sozinho
   antes de decidir se o JS extra é realmente necessário.
5. Documentar em `docs/skills/12-crudgen-referencia-completa.md`.
6. Rodar suíte completa (skill 15/16 como baseline) + `--only
   templates` numa entidade já existente fora do `feature_yeast_bank`,
   pra confirmar que o mecanismo generaliza (não é um efeito colateral
   específico do Container/Item).
