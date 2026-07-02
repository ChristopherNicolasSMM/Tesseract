# 09 — Auto-Descoberta de Módulos (rotas, models, menu)

> **Status: SKILL FORMALIZADA (fase de decisão, 2026-07-01).** Nasceu
> de uma investigação direta no código real do PyTeca
> (`ChristopherNicolasSMM/PyTeca`, pastas `main.py` e
> `utils/generate_model/menu_builder.py`) — o PyTeca já resolvia
> "wiring automático" via `pkgutil.walk_packages` + introspecção de
> `db.Model.__subclasses__()`. Esta skill adapta o mesmo mecanismo
> para a arquitetura tri-nível do Tesseract (Core/Addon/Feature,
> isolamento e prefixo de tabela — skill 02), que o PyTeca (monolítico)
> não precisava resolver.
>
> Mesmo peso normativo das demais skills. Convenção de status (igual
> skill 05/06/07): **[DECIDIDO]** / **[ABERTO]** / **[PENDENTE-SKILL]**.

---

## 0. Decisão raiz

**[DECIDIDO]** `register_models()`, `register_routes()` e
`get_transactions()` deixam de ser puramente manuais. `AddonBase`/
`FeatureBase` ganham uma implementação **default** que descobre
automaticamente, via `pkgutil.walk_packages`, o que existe na pasta
daquele módulo específico — **escopada**, ao contrário do PyTeca, que
faz uma varredura global (`db.Model.__subclasses__()` sem filtro,
válido só porque lá não existe isolamento entre módulos).

**[DECIDIDO]** É **aditivo, nunca quebra o que já existe**: qualquer
Addon/Feature que já sobrescreve esses três métodos manualmente (os 8
`addon.py`/`feature.py` reais do repositório hoje) continua
funcionando exatamente igual — override explícito sempre vence sobre
o comportamento default. Migrar os módulos já existentes para o
caminho automático é trabalho futuro **opcional**, não faz parte desta
skill.

---

## 1. Origem: o mecanismo real do PyTeca

**Rotas** (`main.py`, `discover_and_register_blueprints`):
```python
for importer, modname, ispkg in pkgutil.walk_packages(package.__path__, prefix=package_name + '.'):
    module = importlib.import_module(modname)
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, Blueprint):
            app.register_blueprint(attr)
```
Varre `controller/` e `api/routes/` inteiros, importa cada módulo,
registra qualquer `Blueprint` encontrado.

**Menu** (`utils/generate_model/menu_builder.py`, `get_items_from_models`):
```python
for model_class in db.Model.__subclasses__():
    meta = get_model_metadata(model_class)  # @label/@plural já gravados pelo CrudGen
    endpoint = f"{meta['plural']}.list"
    try:
        url_for(endpoint)   # só inclui se a rota existir de fato
    except Exception:
        continue
    items.append({...})
```
Introspecciona toda subclasse de `db.Model` já carregada, usa as
anotações que o CrudGen já grava, e só inclui no menu se a rota
correspondente realmente existir.

Nenhum passo manual — o model.py gerado (CLI ou Model Builder web,
skill 06) já aparece sozinho no próximo boot, rota e menu inclusos.

---

## 2. Adaptação para o Tesseract — descoberta ESCOPADA por módulo

### 2.1 [DECIDIDO] Rotas

Escopo do walk: `addons.addon_X.root.controller` +
`addons.addon_X.root.api.routes` (núcleo do Addon), ou
`addons.addon_X.features.feature_Y.controller` +
`...feature_Y.api.routes` (Feature). Mesmo mecanismo do PyTeca, só que
apontando para a pasta do módulo específico em vez do pacote inteiro
do projeto — preserva o isolamento Addon/Feature (skill 00).

### 2.2 [DECIDIDO] Models

Mesmo escopo, trocando `controller`/`api.routes` por `model`. A lista
de classes coletadas nesse walk é exatamente o que hoje
`register_models()` retorna manualmente — **nenhuma mudança** em como
o `ModuleManager` aplica `apply_table_prefix` depois (skill 02
preservada 100%, esta skill não mexe nisso).

### 2.3 [DECIDIDO] Menu (Transação)

`get_transactions()` default aplica o mesmo truque do PyTeca sobre os
models descobertos no passo 2.2: lê `get_model_metadata()`, monta
`{plural}.list`, confirma que a rota existe, gera a entrada. Convenção
de `group`/`code`/`@menu_icon` — ver skill 00, adendo correspondente
(evita duplicar a mesma regra em duas skills).

### 2.4 [ABERTO — detalhe de implementação, não de arquitetura]

`url_for()` fora de uma request precisa rodar dentro de
`app.app_context()` (o boot do `ModuleManager` não está numa request).
Resolvido na hora do código — não bloqueia esta decisão.

---

## 3. Impacto na skill 06 (Model Builder)

**[DECIDIDO]** Com esta skill em vigor, o Patch B do Model Builder
(scaffold de Addon/Feature novo do zero — skill 06, ainda não
implementado) fica mais simples: o `addon.py`/`feature.py` gerado não
precisa mais escrever `register_models()`/`register_routes()`/
`get_transactions()` nenhum — só a declaração `__module__` e a classe
vazia herdando de `AddonBase`/`FeatureBase`. Isso também fecha, de vez
(para módulo novo **e** para módulo já existente), o "achado 1" da
sessão anterior: o Model gerado pelo Model Builder para um Addon/
Feature já existente também passa a aparecer sozinho no próximo boot,
sem precisar do trecho manual que a skill 06 previa colar em
`addon.py`/`feature.py`.

---

## 4. Compatibilidade com os módulos já existentes

**[DECIDIDO]** Nenhuma migração obrigatória agora. Os 8 `addon.py`/
`feature.py` reais (`addon_brewstation`, `addon_device_manager`,
features de `yeast_bank`/`mash_control`/`brew_father`, etc.) continuam
com override manual — herança Python garante que isso funciona sem
qualquer ajuste neles. Migrá-los para remover o boilerplate manual
fica registrado como trabalho futuro opcional.

---

## 5. Pendências desta skill

- [ABERTO] Nenhuma pendência de arquitetura. Detalhe de `url_for` fora
  de request (seção 2.4) e biblioteca/abordagem exata de walk ficam
  para a fase de código, quando autorizada.
