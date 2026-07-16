# 06 — Manutenção e Expansão (Feature Mash Control)

## Sobre o motor de controle em tempo real (parcialmente portado)

O BrewStation original tinha PID controller, motor de automação
(avalia sensor continuamente) e scheduler de processo. Do que já foi
portado para o Tesseract:

- **Motor de automação: portado e ativo.** `AutomationRule` avalia de
  fato via EventBus do Core (`device_manager.actor.value_changed`) —
  é 100% orientado a evento, sem polling/scheduler, então não precisou
  esperar o sistema de Tasks. Ver `03-fluxos.md` e
  `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`, Fase E.
- **Loop de controle PID contínuo: ainda não portado.** As tabelas já
  têm os parâmetros necessários (`pid_kp`/`ki`/`kd` em
  `BrewSessionStep`), mas não existe nenhum processo consumindo esses
  parâmetros continuamente ainda — diferente do motor de automação
  (evento pontual), um PID de verdade precisa rodar em intervalos
  regulares. Candidato natural: `services/core/task_service.py`
  (sistema de Tasks/`APScheduler`, já existe e já é usado por outras
  áreas do Core — `/admin/tasks/`), não vale mais a justificativa
  antiga de "não temos scheduler ainda". Quando isso entrar, o motor
  consumiria as tabelas já existentes como configuração, sem precisar
  de migration nova.

## Dependência de `addon_device_manager`

Sempre ativar `device_manager` antes — `mash_control` declara isso em
`feature.json` (`"requires": ["device_manager", "estoque"]` — nome
correto do Addon promovido, skill 05; a Feature também depende de
`estoque` pra resolução de ingrediente de receita).

## Como adicionar um tipo de widget novo ao Dashboard

1. Adiciona o nome do tipo em `_VALID_WIDGET_TYPES`
   (`dashboard_runtime_service.py`) — sem isso, `create_widget_from_editor()`
   rejeita a criação.
2. Se o tipo precisa de dado em tempo real (como `step_card`), adiciona
   um branch em `get_layout_snapshot()` que popula
   `widgets_out[widget.id]`. Se é conteúdo estático (como `text`/`image`),
   não precisa — o dado vem direto de `config_json`, lido no template.
3. Bloco HTML novo no loop de widgets em `dashboards/view.html`
   (`{% elif w.widget_type == '...' %}`), e branch em JS
   `renderWidget()` se o tipo tiver dado dinâmico.
4. Ícone na paleta (`#dbPalette`, lista de tuplas
   `(widget_type, icone_bootstrap, label)` no topo do template).
5. Se o tipo precisa de vínculo (`vessel_id`/`device_function_name`),
   adiciona um `.db-panel-field` no painel lateral e inclui o tipo em
   `panelFieldsByType` (JS) — senão o painel não mostra os campos de
   configuração certos pra ele.

Nenhum desses passos precisa de migration — `DashboardWidget.widget_type`
é `String` livre e `config_json` é `JSON` livre; o "schema" de um tipo
de widget novo é inteiramente convenção de código, não de banco.

## Workspace consolidado por Planta (`plant_workspace.py`) — fragmento AJAX

Padrão novo (conversa — "juntar Dashboard + Etapas + Sessões + Planta
numa tela só"), fase 1: casca (`/brewstation/plant-workspace/` →
escolhe/cria Planta → `/plant-workspace/<id>` → barra de abas) + aba
Dashboard funcionando. As telas individuais de sempre continuam
existindo em paralelo — a remoção do menu é decisão pra depois de
validar o workspace na prática.

**Mecanismo de fragmento** (decisão da conversa: AJAX de verdade, não
iframe): `dashboards/view.html` foi dividido em `_content.html` (HTML)
+ `_scripts.html` (JS) — a tela cheia (`view.html`) inclui os dois
dentro de `{% block content %}`/`{% block extra_js %}`, sem mudar
nada de comportamento; um fragmento novo (`_fragment.html`) inclui os
mesmos dois partials sem `{% extends %}`, pra ser devolvido bruto por
`plant_workspace.tab_dashboard()` e injetado via `fetch()` na casca.

**Duas armadilhas resolvidas, valem pra qualquer aba nova**:
1. `<script>` injetado via `innerHTML =` não executa sozinho (o
   browser bloqueia por padrão) — a casca (`shell.html`) recria cada
   tag de `<script>` do fragmento recebido antes de confiar que ele
   rodou.
2. Se o fragmento tem algum polling (`setInterval`, como o Dashboard
   tem — snapshot a cada 3s), ele precisa de um jeito de "desligar" ao
   trocar de aba, senão fica rodando escondido pra sempre a cada
   reabertura. Convenção: o fragmento expõe `window.__tabCleanup =
   function () {...}` antes de terminar seu próprio `<script>`; a
   casca chama isso (se existir) antes de carregar a próxima aba.

**Como adicionar uma aba nova** (Sessões/Planta/Receita
Mash/Automação, próximas rodadas):
1. Nova rota `GET /plant-workspace/<plant_id>/tab/<chave>` no
   `plant_workspace.py`, devolvendo um template SEM `{% extends %}`
   (bruto).
2. Marca `"enabled": True` na entrada correspondente de `_TABS`
   (`plant_workspace.py`) e adiciona a URL no dicionário `tabUrls` do
   JS de `shell.html`.
3. Se a tela de origem já existe como página cheia (ex.: telas de
   Sessão hoje), o caminho de menor esforço é o mesmo desta fase —
   extrair o conteúdo dela pra um partial reaproveitado pelos dois
   lados (tela cheia + fragmento), não duplicar a lógica.
4. Se a tela nova tiver `setInterval`/listener global, seguir a
   convenção do item 2 das armadilhas acima.
