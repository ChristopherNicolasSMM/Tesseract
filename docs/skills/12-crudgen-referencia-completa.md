# 12 — CrudGen: Referência Completa + Guia de Uso das Anotações

> **Status: REFERÊNCIA DESCRITIVA + guia prático.** Nasceu como
> levantamento do estado real do CrudGen (pipeline, anotações,
> hooks/`--overwrite`) — na sequência, virou também o lugar onde as
> decisões de fechamento do CrudGen desta sessão foram implementadas:
> HTML5 nativo + badge a partir de `@required`/`@max_length`/
> `@min_length`/`@min_value`, seed de `FieldRule` a partir das mesmas
> anotações, `--only templates`, e migração de 3 módulos reais pro
> caminho de auto-descoberta (skill 09). Tudo já **[EXECUTADO]** —
> não é mais "achado, decisão pendente" como numa primeira versão
> deste documento.

---

## 1. Pipeline de ponta a ponta

```
1. Developer escreve model.py anotado (@label, @plural, @choices, etc.)
       ↓
2. python run.py generate --model <path> --addon <nome> [--feature <nome>] [--overwrite] [--only templates]
       ↓ (core/cli.py::generate_cmd)
3. Resolve a classe do model no arquivo (reimport pelo dotted path real — seção 6)
       ↓ (core/crudgen/generator.py::generate)
4. resolve_table_prefix() lê addon.json/feature.json → prefixo tri-nível (skill 02)
5. apply_table_prefix() renomeia __tablename__ do model em runtime
6. get_model_metadata() extrai as anotações (seção 2)
7. Loop nos artefatos (todos, ou só templates se --only): renderiza, escreve
   (hooks só na primeira vez — seção 3)
8. sync_model_permissions() grava as permissões CRUD automáticas + @permission
9. sync_field_rules_from_validations() semeia FieldRule a partir de
   @required/@max_length/@min_length/@min_value (só na criação — seção 5)
       ↓
10. Resultado: service/controller/routes (+ hooks) + manage.html + detail.html
    prontos. Falta só registrar em register_models()/register_routes()
    do addon.py/feature.py (manual, OU automático se o módulo usar o
    default de auto-descoberta — seção 7) e o próximo boot criar a tabela.
```

**Nada disso cria tabela no banco.** `generate()` só escreve arquivo. A
tabela nasce no próximo boot (`db.create_all()`) ou via migration.

---

## 2. Catálogo de anotações — guia de uso completo

Todas as anotações abaixo, **exceto as da seção 2.4**, são
**ativas** — afetam geração real ou runtime real. Isso mudou nesta
sessão: `@required`/`@max_length`/`@min_length`/`@min_value` eram
decorativas (nenhum consumidor) até esta rodada — ver seção 5 pro
antes/depois.

### 2.1 Identidade e apresentação

**`@label(valor)`**
```python
@label("Malte")
class Malte(db.Model): ...
```
Nome de exibição da entidade — título de página, mensagens, etc.
Sem ela, cai no `__name__` da classe (`get_model_metadata()`).

**`@plural(valor)`**
```python
@plural("maltes")
class Malte(db.Model): ...
```
Nome plural — vira o nome do Blueprint, prefixo de URL
(`/brewstation/maltes`, `/api/brewstation/maltes`), nome da pasta de
template (`templates/maltes/`), nome de permissão (`maltes.list`,
`maltes.create`, ...) e a chave usada por `@weak_ref(options=...)`
(seção 4) pra achar `/api/options/maltes`. **Quase todo nome gerado
deriva daqui** — é a anotação mais "pesada" em efeito.

**`@menu_icon(valor)`**
```python
@menu_icon("bi-flask")
class Malte(db.Model): ...
```
Ícone Bootstrap Icons — **só tem efeito se `get_transactions()` do
módulo for o default auto-gerado** (skill 09, seção 7 abaixo). Se o
módulo escreve `get_transactions()` à mão (caso mais comum nos
módulos reais deste projeto), essa anotação é ignorada — o ícone vem
direto do dict escrito à mão.

### 2.2 Validação — HTML5 nativo + `FieldRule` (EXECUTADO nesta sessão)

**`@required(campo, message=None)`**
```python
@required("nome", message="Nome do material é obrigatório")
class Material(db.Model): ...
```
Efeito real, dois lugares:
1. **HTML5 nativo**: `<input required>` + badge `<span class="text-danger">*</span>`
   no label, em `manage.html`/`detail.html` gerados.
2. **`FieldRule` semeada** (`entity_key=<plural>`, `field_name=<campo>`,
   `rule_id="obrigatorio"`) — liga ao motor real de validação
   client-side (`static/js/rule_engine.js`, skill 07b), a mesma tela
   admin de Field Rules que já existia. **Só na criação** — depois
   disso o admin é dono do registro (mesmo espírito de hook, seção 3).

**`@max_length(campo, max, message=None)`**
```python
@max_length("sku", 60, message="SKU deve ter no máximo 60 caracteres")
```
HTML5 `maxlength="60"` + `FieldRule(rule_id="max_length")`.

**`@min_length(campo, min, message=None)`**
```python
@min_length("nome", 3, message="Nome deve ter no mínimo 3 caracteres")
```
HTML5 `minlength="3"` + `FieldRule(rule_id="min_length")`.

**`@min_value(campo, min, message=None)`**
```python
@min_value("cor_ebc", 0, message="Cor EBC não pode ser negativa")
```
Campo vira `<input type="number" min="0">` (só quando tem
`@min_value` — outros campos numéricos sem essa anotação continuam
`type="text"`, decisão desta sessão pra não mexer em campo que
ninguém pediu) + `FieldRule(rule_id="min_valor")`.

**Não existe `@max_value`** — só `min_value` foi portado do PyTeca.
O catálogo de regras (`core/rules_catalog.py`) já tem `max_valor`/
`maxValue` pronto, só falta a anotação — não implementado nesta
rodada (fora do que foi pedido), fica registrado pra simetria futura.

**`@field_labels({campo: rótulo, ...})`** — adicionado nesta sessão
(achado real: `manage.html`/`detail.html` gerados sempre mostravam
`field.replace('_', ' ').title()` como rótulo — nunca passava pelo
i18n da skill 00, produzindo texto tipo "Container Type" em vez de
"Tipo"). Sem essa anotação, o campo continua caindo no fallback de
sempre — comportamento anterior preservado, nenhum model existente
quebra.
```python
@field_labels({
    "container_type": "Tipo",
    "device_id": "Dispositivo",
    "description": "Descrição",
})
```
Mesma convenção de "conveniência de autoria" do `@label`/
`Column(label=...)` (skill 00) — texto direto aqui, ainda não
resolvido via `i18n/pt_BR.json`. Resolver isso definitivamente (gerar
a chave de tradução a partir do texto, em vez de hardcode por model) é
decisão em aberto da análise de field metadata registrada no backlog
(tipos SQLAlchemy → HTML + validação), não desta sessão — essa
anotação é o mínimo pra parar de mostrar rótulo em inglês nas telas
que já existem, sem esperar a análise maior.

**`@readonly_fields([campo, ...])`** — adicionado na skill 21. Soma
campos ao conjunto padrão que já é somente-leitura no formulário
(`id`/`created_at`/`updated_at`/`is_deleted`/`deleted_at`). Uso real:
`YeastBankEvent.starter_id`/`cell_count_id` são preenchidos só pelo
hook `post_create_redirect` (abaixo), nunca escolhidos na tela — sem
essa anotação, apareceriam como campo numérico editável comum (são
FK reais).
```python
@readonly_fields(["starter_id", "cell_count_id"])
```

**Hooks de controller — achado real (skill 21): nunca eram chamados de
verdade.** `controller.py.j2`/`routes.py.j2` sempre tiveram o
docstring "Customizações via `X_hooks.py`" — mas nenhum dos dois
importava ou chamava esse arquivo. `X_hooks.py` existia, era criado
pelo CrudGen, só nunca foi conectado a nada (diferente de
`X_service_hooks.py`, que sempre teve `pbo_apply_fields`/
`pai_apply_fields` reais). Corrigido com o mesmo padrão seguro já
usado no service (`try/except ImportError` + `_hook(name)` com
fallback no-op — hook ausente nunca quebra nada). Dois hooks reais
adicionados nesta sessão, ambos opcionais:

- **`block_create(data) -> str | None`** — chamado no início de
  `create()` (web **e** API). Retornar uma string bloqueia a criação
  (mostra a string como erro); retornar `None` (ou não definir a
  função) deixa criar normalmente. Uso real: `YeastStarterLog` só
  pode ser criado a partir de um `YeastBankEvent` tipo "Starter"
  (skill 21) — a tela própria do Starter bloqueia `create()` direto.
- **`post_create_redirect(item) -> Response | None`** — chamado depois
  que `create()` salva com sucesso, **tanto na rota web quanto na
  API** (achado real: a primeira versão só chamava na web, e a API
  virava um jeito de criar o evento sem disparar a criação
  automática do registro especializado — bug de contorno silencioso).
  Na web, um `Response` retornado (via `redirect(url_for(...))`) troca
  o destino padrão (`{{ plural }}.manage`); na API o valor de retorno
  é descartado de propósito (JSON não redireciona) — só os efeitos
  colaterais do hook importam ali. Uso real: criar um `YeastBankEvent`
  tipo "Starter"/"Contagem de Células" cria automaticamente o
  registro especializado (`YeastStarterLog`/`YeastCellCountHistory`)
  e, na web, redireciona pra edição dele.

### 2.3 Referência fraca e busca cross-módulo

**`@display_field(valor)`**
```python
@display_field("nome")
class Material(db.Model): ...
```
Campo que representa o "nome" do registro pra qualquer consumidor
externo — usado por `/api/options/<plural>` (busca) e por qualquer
função-resolver de `@weak_ref` (convenção: a função deve usar isso
pra montar a chave `"display"` do retorno, nunca hardcoded).

**`@weak_ref(campo, resolver, options=None)`**
```python
@weak_ref("material_id",
           resolver="addons.addon_estoque.root.services.material_lookup.get_material",
           options="materials")
class Malte(db.Model):
    material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK
```
Ver seção 4 — resolve id cru em nome legível na lista; vira combo de
busca (`options=`) ou texto de apoio (sem `options=`) no formulário de
detalhe.

**`@choices(campo, label=None, order="asc")`**
```python
@choices("tipo", label="Tipo")
class Malte(db.Model): ...
```
Vira filtro `<select>` em `manage.html`, com valores `DISTINCT` reais
do banco (não uma lista fixa) — atualiza sozinho conforme dado novo
entra.

### 2.4 Permissão de negócio

**`@permission(action, role_required=None, description=None)`**
```python
@permission("trash", role_required="brewmaster", description="Mover lote para a lixeira")
class MashRecipe(db.Model): ...
```
Cria permissão extra (`<plural>.<action>`) além das 7 automáticas
(`list`/`detail`/`create`/`update`/`trash`/`restore`/`delete_permanent`)
— Camada 2. Se `role_required` for passado, a Role é criada (se não
existir) e a permissão anexada a ela automaticamente.

### 2.5 [ABERTO, não resolvido nesta sessão] Vestigiais

`@listview`, `@form`, e as classes `Column`/`Filter`/`Group` **continuam
sem nenhum consumidor** — não fizeram parte do pedido desta rodada
(que era especificamente sobre `@required`/`@max_length`/
`@min_length`/`@min_value`). Mesma recomendação de antes: decidir se
ligam a algo real, se somem do módulo, ou se ficam documentadas como
estão. Ver `BACKLOG.md` pra retomar quando quiser.

---

## 3. Os 8 artefatos gerados + hooks + `--overwrite` + `--only`

```python
_FILES_TO_GENERATE = [
    ("service.py.j2",         "services/{snake_singular}_service.py",         False),
    ("service_hooks.py.j2",   "services/{snake_singular}_service_hooks.py",   True),
    ("controller.py.j2",      "controller/{plural}.py",                       False),
    ("controller_hooks.py.j2","controller/{plural}_hooks.py",                 True),
    ("routes.py.j2",          "api/routes/{plural}_routes.py",                False),
    ("routes_hooks.py.j2",    "api/routes/{plural}_routes_hooks.py",          True),
    ("manage.html.j2",        "templates/{plural}/manage.html",               False),
    ("detail.html.j2",        "templates/{plural}/detail.html",               False),
]
```

**Hooks nunca são sobrescritos — comprovado empiricamente** (marcador
manual inserido num hook existente sobreviveu a `generate --overwrite`
real; log confirma `"N hook(s) preservado(s)"`). A checagem de hook
roda **antes** de qualquer checagem de `overwrite` no código.

**`--overwrite`**: reescreve os 5 artefatos não-hook. Tudo-ou-nada,
a menos que `--only` seja usado.

**`--only templates`** (EXECUTADO nesta sessão): restringe a
regeneração só a `manage.html`/`detail.html`. **Exige `--overwrite`
junto** — sem isso, `generate()` levanta `ValueError` explícito (não
faz sentido pedir "só templates" sem também pedir pra sobrescrever o
que já existe). Uso:
```
python run.py generate --model <path> --addon <nome> --overwrite --only templates
```
Não roda o seed de `FieldRule` (seção 2.2) — esse é só de geração
completa.

**Risco real testado (skill 20)**: `--only templates` sozinho **quebra**
(`jinja2.exceptions.UndefinedError`) numa entidade cujo `controller.py`
nunca foi regenerado desde que uma variável nova passou a ser exigida
pelo template (`field_labels` — skill 15; `html_type` dentro de
`field_html_validations` — skill 20). O HTML novo referencia uma
variável que o controller antigo nunca calculou nem passou pro
`render_template()`. Reproduzido de propósito rodando `--only
templates` em `DeviceFunction` (fora do `feature_yeast_bank`, controller
gerado antes da skill 15) — `manage()` quebrou com 500 na hora.
**Regra prática**: depois de uma mudança que adiciona uma variável nova
consumida pelos templates (não só ajusta HTML), a primeira regeneração
de cada entidade precisa ser **sem** `--only` (os 5 artefatos, controller
incluído) — só depois disso `--only templates` volta a ser seguro pra
essa entidade.

**Dois modos de template**: `.py.j2` usa Jinja2 real na hora de
gerar; `.html.j2` usa substituição de string simples
(`@@label@@`/`@@plural@@`/`@@class_name_lower@@`) porque o HTML
gerado **também é** um template Jinja, processado depois pelo Flask
em runtime — qualquer lógica nova em HTML gerado é Jinja **literal**
no `.j2`, nunca avaliada na hora de gerar.

---

## 4. Referência fraca → combobox

1. Model **alvo** ganha `@display_field("nome")`.
2. Model **que TEM** a referência fraca ganha `@weak_ref(campo,
   resolver=, options=)`.
3. Controller gerado lê `get_weak_refs(Classe)`, monta `_WEAK_REFS`.
4. `manage()`/`detail()` chamam o `resolver` via `importlib` (nunca
   importa o model alvo direto) — pega a chave `"display"`.
5. `manage.html`: célula da lista substitui valor cru pelo resolvido.
6. `detail.html`: **nunca** sobrescreve `value=` do input (quebraria o
   submit). Com `options=` → combo de busca
   (`static/js/weak_ref_combo.js`, vanilla JS, chama
   `/api/options/<options>`). Sem `options=` → texto de apoio ao lado.
7. `/api/options/<plural>` (`api/routes/core/options_routes.py`) — só
   elegível pra model com `@display_field` (whitelist implícita).

**Gap conhecido, não resolvido**: o formulário inline de "Novo
registro" em `manage.html` não ganha o combo — só `detail.html` tem
isso hoje.

---

## 5. Validação — antes e depois desta sessão

**Antes**: `@required`/`@max_length`/`@min_length`/`@min_value`
populavam `cls._validations`, mas nada lia esse valor — decorativas.
A única validação real vinha de `FieldRule` (tabela, configurada à
mão pela tela admin de Field Rules), sem nenhuma ligação com anotação
de model.

**Depois (esta sessão)**: as 4 anotações agora **alimentam os dois
mecanismos que já existiam, sem inventar um terceiro**:
- HTML5 nativo direto no `<input>` gerado (seção 2.2).
- Seed de `FieldRule`, create-only (`generator.py::_seed_field_rules_from_validations`),
  usando o catálogo de `rule_id` que **já existia**
  (`core/rules_catalog.py`, grupo "Validação") — não foi inventado
  `rule_id` novo, só ligado o que já estava lá:

| Tipo da anotação | `rule_id` | `js_function` |
|---|---|---|
| `required` | `obrigatorio` | `required` |
| `max_length` | `max_length` | `maxLength` |
| `min_length` | `min_length` | `minLength` |
| `min_value` | `min_valor` | `minValue` |

**Create-only é proposital**: regenerar (`--overwrite`) não pode
reverter uma customização que o admin fez na `FieldRule` depois —
mesmo espírito de hook (`*_hooks.py`), aplicado a dado em banco em vez
de arquivo. Testado explicitamente: editar `params_json` de uma
`FieldRule` já semeada, regenerar de novo, a edição sobrevive.

---

## 6. CLI — referência completa

```
python run.py generate --model <caminho/model.py> --addon <nome> [--feature <nome>] [--class-name <Nome>] [--overwrite] [--only templates]
```

| Argumento | Obrigatório | Regra |
|---|---|---|
| `--model` | Sim | Caminho do arquivo `.py` com o model anotado |
| `--addon` | Sim | Nome do Addon (sem o prefixo `addon_` da pasta) |
| `--feature` | Não | Nome da Feature (sem o prefixo `feature_`) — omitido = núcleo do Addon (`root/`) |
| `--class-name` | Não | Só necessário se o arquivo tiver mais de uma classe com `__tablename__` |
| `--overwrite` | Não (flag) | Reescreve os 5 arquivos não-hook se já existirem — hooks nunca, mesmo assim |
| `--only templates` | Não | Restringe a regeneração só aos 2 artefatos HTML. **Exige `--overwrite` junto** — erro claro se faltar |

**Carregamento do model**: reimporta pelo **caminho de pacote real**
(`importlib.import_module`, dotted path), não isolado. Reaproveita a
classe já mapeada pelo boot normal — evita `NoForeignKeysError` em
model com `relationship()` real pra outra tabela já prefixada (bug
real corrigido em sessão anterior). **Para model novo**, registrar em
`register_models()` **antes** de rodar `generate` — o registro prévio
é o que faz o boot importar a classe (e resolver FK) na ordem certa.

---

## 7. Migração pro caminho de auto-descoberta (skill 09) — EXECUTADO

Migrados nesta sessão: `feature_yeast_bank`, `feature_mash_control`,
`addon_device_manager` — só `register_models()`/`register_routes()`
(mecânicos, sem decisão de produto embutida). **`get_transactions()`
continua manual em todo módulo real** — decisão explícita, não
esquecimento:

- O default auto-gerado (`auto_transactions_from_models`) usa código
  `TX_AUTO_<PLURAL>`/`TX_GROUP_AUTO_<MODULO>`, sem descrição, ícone
  genérico se `@menu_icon` não estiver presente, e **um grupo só por
  módulo** — perderia a hierarquia Addon>Feature (`TX_GROUP_BREWSTATION`,
  skill 10) e mudaria os códigos `TX_` que 3 arquivos de teste
  referenciam diretamente.
- `addon_brewstation` (núcleo) não foi migrado — não tem model/rota
  própria pra economizar boilerplate nenhum, e seu `get_transactions()`
  é exatamente o wrapper `TX_GROUP_BREWSTATION` construído a dedo.

**Cuidado ao migrar `register_routes()` de um módulo com efeito
colateral além de registrar Blueprint** (achado real, 2 dos 3 módulos
migrados tinham isso): `feature_mash_control` inscreve o motor de
automação no EventBus (`automation_engine.register()`);
`addon_device_manager` registra o alvo de reconexão MQTT no
`TASK_REGISTRY` em memória (`register_task(...)`). Nos dois casos, a
migração trocou só o loop mecânico de `import`+`register_blueprint`
por `discover_blueprints()` — o efeito colateral customizado continua
explícito, escrito à mão, depois da chamada de auto-descoberta.
