# 15 — Pop-ups Padrão: Diálogo de Confirmação e Toast/Alert

> **Status: DECIDIDO, execução pendente.** Nasceu de uma revisão real do
> estado de confirmação/alerta do projeto (`window.confirm()` nativo sem
> estilo, `flash()` duplicado por template). Escopo desta skill: só
> **confirmação** e **toast/alert** — formulário em modal (`_modals/
> form_modal.html`) foi removido do projeto e está fora deste documento
> (ver skill 01, nota de arquivo `form_modal.html.j2`/`_modals/`
> confirmadamente morto).

## 0. Por que Core, e não Addon/Plugin

Diálogo de confirmação e toast não pertencem a nenhum domínio (cervejaria,
dispositivo, estoque) — são infraestrutura de UI genérica, igual ao
`ModuleManager` ou ao `EventBus`. Não criam tabela, não têm manifesto
próprio. Vivem em `static/` (global, ver adendo skill 01),
`templates/core/base.html` (integração única) e `services/core/`
(quando envolvem lógica além de JS, como o motor de i18n da skill 00).

## 1. Diálogo de confirmação

### 1.1 Problema real encontrado

Todo `manage.html`/`detail.html` gerado pelo CrudGen usa
`onsubmit="return confirm('Mover para a lixeira?')"` — nativo do
navegador, sem estilo, sem i18n (texto hardcoded no `.j2`). Dois usos
manuais fora do CrudGen seguem o mesmo padrão problemático
(`feature_mash_control/dashboards/_scripts.html`,
`feature_brew_father/brewfather_syncs/depara.html`).

### 1.2 Convenção de marcação (declarativa, não inline JS)

Qualquer elemento que hoje dispararia `confirm()` nativo passa a
declarar a intenção via atributo `data-confirm-key`, nunca
`onsubmit`/`onclick` com JS de confirmação embutido:

```
<form method="post" action="..." data-confirm-key="core.confirm.trash_generic">
```

Para mensagem com valor dinâmico (interpolação — ver skill 00, adendo de
i18n), os parâmetros vêm de atributos `data-confirm-param-[nome]`:

```
<button data-confirm-key="brewstation_mashctrl.dashboard.confirm_actuate"
        data-confirm-param-label="Bomba 1">
```

### 1.3 Mecanismo de interceptação — regra obrigatória de delegação

**Regra de ouro desta seção** (motivo real: Plant Workspace e Dashboard
carregam tela via fragmento AJAX, e `<script>` injetado via `innerHTML`
não auto-executa — mesma classe de bug já catalogada nos aprendizados
recorrentes do projeto). O listener **nunca** é registrado por
`querySelectorAll(...).forEach(el => el.addEventListener(...))` sobre
elementos específicos — isso fica surdo a qualquer form/botão injetado
depois do carregamento inicial da página.

- Um único listener, registrado **uma vez**, em `templates/core/base.html`,
  via delegação no `document`:
  `document.addEventListener("submit", handler, true)` (fase de captura,
  para poder interceptar antes do submit real) usando
  `event.target.closest("[data-confirm-key]")` para resolver o elemento.
- Mesmo mecanismo para `click` em elementos não-form
  (`data-confirm-key` num `<button>` fora de um `<form>`).
- Isso cobre automaticamente qualquer fragmento AJAX novo, sem exigir
  reinit por aba — mesmo espírito do `window.__tabCleanup` já convencionado.

### 1.4 API JS pública

`window.__tesseractConfirm({ key, params }) → Promise<boolean>`

- Mostra modal Bootstrap estilizado (reaproveita `bootstrap.bundle.min.js`
  já carregado — sem lib nova) em vez do `confirm()` nativo.
- O texto do modal vem de `t(key, params)` (skill 00, motor de i18n) —
  nunca texto direto.
- Resolve `true`/`false` conforme o botão clicado; o handler de submit
  intercepta o evento original (`event.preventDefault()`), aguarda a
  Promise, e só então dispara o submit/click real programaticamente se
  `true` — nunca duas confirmações em sequência.

### 1.5 Chaves i18n desta primeira leva

| Chave | Módulo dono | Texto pt_BR |
|---|---|---|
| `core.confirm.trash_generic` | Core | "Mover para a lixeira?" |
| `core.confirm.delete_permanent_generic` | Core | "Excluir PERMANENTEMENTE? Esta ação não pode ser desfeita." |
| `brewstation_mashctrl.dashboard.confirm_actuate` | `feature_mash_control` | "Confirma acionar \"{label}\"?" |
| `brewstation_bf.depara.confirm_create_materials` | `feature_brew_father` | "Criar um Material no estoque para cada ingrediente pendente? Os dados de spec (EBC, alpha, etc.) do BrewFather serão usados." |

As duas primeiras (genéricas, sem domínio) vivem em `core/i18n/pt_BR.json`.
As duas últimas vivem no `i18n/pt_BR.json` da própria Feature dona da
tela — nenhuma delas ainda tem pasta `i18n/` própria hoje; nasce com
esta skill.

## 2. Toast / Alert

### 2.1 Problema real encontrado

`flash()` categorizado (`success`/`error`) é renderizado como
`<div class="alert alert-danger/alert-success">` **duplicado
individualmente em cada `manage.html`/`detail.html`** (não centralizado
em `base.html`). Sem dismiss, sem timeout, sem posição fixa, e invisível
em qualquer fluxo que não seja POST→redirect→GET tradicional (não
alcança fragmento AJAX).

### 2.2 Container único

`templates/core/base.html` ganha um container fixo
(`#core-toast-container`, posição fixa, empilhável) e passa a ser o
**único lugar do projeto** que processa `get_flashed_messages()` — os
loops duplicados em `manage.html.j2`/`detail.html.j2` (e nos arquivos já
gerados a partir deles) são removidos.

### 2.3 Dois caminhos de disparo

| Caminho | Quando se aplica | Mecanismo |
|---|---|---|
| **Flash tradicional** | Fluxo POST → redirect → GET (a maioria dos controllers CrudGen hoje) | `base.html` renderiza `get_flashed_messages()` **uma única vez**, injeta como JSON inline no HTML; JS lê no load da página e empurra pro toast com auto-dismiss. |
| **Resposta AJAX** | Fragmentos (Plant Workspace, Dashboard, qualquer `fetch()` que não recarrega a página) | Controller retorna `{"message": "...", "category": "success"}` no JSON de resposta; o JS que já faz o `fetch()` chama `window.__tesseractToast.show(message, category)` diretamente — **nunca** depende de `flash()`/sessão para esse caminho. |

Controllers existentes que hoje só fazem `flash()` **não precisam mudar**
se continuam no fluxo tradicional (trash/delete via form POST normal). Só
endpoints que já respondem com fragmento/JSON (ex.: dashboard, dentro do
Plant Workspace) precisam adotar o campo `message`/`category` na resposta
para o toast aparecer.

### 2.4 API JS pública

`window.__tesseractToast.show(message, category)` — `category` em
`success | error | warning | info` (as duas primeiras já em uso hoje via
`flash()`; as outras duas nascem suportadas desde já, mesmo sem chamador
ainda, para não exigir retrabalho de CSS/JS quando surgir o primeiro uso).

## 3. Arquivos afetados (schema da mudança, sem código nesta etapa)

| Arquivo | Mudança |
|---|---|
| `services/core/i18n_service.py` | Novo (skill 00, adendo de i18n) |
| `core/i18n/pt_BR.json` | Novo — chaves `core.confirm.*` |
| `core/app_factory.py` | Registra global Jinja `t()` |
| `static/js/core_confirm_dialog.js` | Novo — delegação de evento + `window.__tesseractConfirm` |
| `static/js/core_toast.js` | Novo — `window.__tesseractToast` + leitura do flash inline |
| `static/css/core_popups.css` | Novo — estilo compartilhado dos dois componentes |
| `templates/core/base.html` | Container de toast, include dos 2 JS/1 CSS novos, render único de `get_flashed_messages()` |
| `core/crudgen/templates/manage.html.j2` | Remove loop de flash; troca `onsubmit=confirm(...)` por `data-confirm-key` |
| `core/crudgen/templates/detail.html.j2` | Idem |
| `addons/addon_brewstation/features/feature_mash_control/i18n/pt_BR.json` | Novo — chave `confirm_actuate` |
| `addons/addon_brewstation/features/feature_mash_control/templates/dashboards/_scripts.html` | Troca `confirm()` manual por `data-confirm-key`/`window.__tesseractConfirm` |
| `addons/addon_brewstation/features/feature_brew_father/i18n/pt_BR.json` | Novo — chave `confirm_create_materials` |
| `addons/addon_brewstation/features/feature_brew_father/templates/brewfather_syncs/depara.html` | Idem |
| Todo `manage.html`/`detail.html` já gerado (dezenas) | Regenerado via `crudgen generate --overwrite` após o `.j2` mudar |

## 4. Ponto de atenção obrigatório na execução (não é regra de skill, é aviso operacional)

A regeneração via `--overwrite` cobre a maioria das telas sem risco, mas
**as telas de `feature_mash_control` que alimentam o Plant Workspace**
(`/brewstation/plant-workspace/`, abas via fragmento AJAX — ver memória
de sessões anteriores) exigem validação manual extra pós-regeneração:
confirmar que o container de toast/confirm em `base.html` realmente
alcança conteúdo injetado por `window.__workspaceLoadUrl`/
`__workspaceReloadCurrent`, e que nenhuma tab quebrou por causa da
remoção do loop de flash antigo dentro do próprio fragmento. Rodar a
suíte de testes completa não cobre isso (é comportamento de DOM/JS, não
Python) — validação manual na tela é obrigatória antes de considerar
esta skill "executada" no Plant Workspace especificamente.

## 5. Regra de ouro desta skill

> Nenhum novo pop-up de confirmação ou alerta nasce usando `confirm()`
> nativo, `alert()` nativo, ou `<div class="alert">` solto fora do
> container central de `base.html`. Se aparecer, foi colocado no lugar
> errado — usar `data-confirm-key` ou `window.__tesseractToast`.
