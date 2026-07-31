"""
core/actions_catalog.py

Fase 10, Patch 3 — catálogo de tipos de Ação disparáveis por evento de
um DesignerComponent (`DesignerComponent.events`, coluna que existia
desde a Fase 7c mas estava morta — nenhum controller/template lia ou
escrevia nela até este patch).

Mesmo padrão de core/rules_catalog.py: só metadado (id, label, ícone,
parâmetros, descrição) — a implementação real de cada tipo vive em
`static/js/actions_engine.js` (ações client-side) ou no endpoint
`POST /admin/designer/data-action/<id>/execute` (a única server-side,
call_data_action — decisão registrada em BACKLOG.md, Fase 10: toda
Ação que toca dado/API roda sempre no servidor, nunca no navegador,
porque a conexão pode envolver credencial).

`runs_on`:
  - "client": executado direto no navegador por actions_engine.js,
    sem round-trip nenhum — nunca tem acesso a segredo.
  - "server": o navegador só dispara uma chamada ao endpoint dedicado;
    quem decide o que fazer (inclusive qual credencial usar, via
    ODataConnection) é sempre o servidor.

Diferente de RULE_CATALOG (que tem grupos "Validação"/"Visibilidade"/
"Cálculo" com only-Validação conectado), aqui as 5 ações já entram
todas "connected" — decisão do usuário registrada em BACKLOG.md, Fase
10: escopo completo nesta primeira leva (básico + manipulação de
componente + chamar Ação de Dado), não incremental por grupo.
"""

EVENT_TYPES = ("onClick", "onChange", "onLoad")

ACTION_CATALOG = [
    {
        "id": "navigate", "label": "Navegar para URL", "icon": "bi-box-arrow-up-right",
        "runs_on": "client",
        "params": [
            {"name": "url", "label": "URL", "type": "text", "default": "/"},
            {"name": "target", "label": "Abrir em", "type": "select", "options": ["_self", "_blank"], "default": "_self"},
        ],
        "description": "Navega o navegador para a URL informada.",
    },
    {
        "id": "show_message", "label": "Mostrar Mensagem", "icon": "bi-chat-square-text",
        "runs_on": "client",
        "params": [
            {"name": "message", "label": "Mensagem", "type": "text", "default": "Concluído."},
            {"name": "variant", "label": "Tipo", "type": "select", "options": ["success", "error", "warning", "info"], "default": "info"},
        ],
        "description": "Mostra um toast (mesmo sistema padronizado da skill 15) com a mensagem.",
    },
    {
        "id": "set_component_value", "label": "Definir Valor de Componente", "icon": "bi-input-cursor-text",
        "runs_on": "client",
        "params": [
            {"name": "target_component_id", "label": "ID do Componente Alvo", "type": "number", "default": ""},
            {"name": "value", "label": "Valor", "type": "text", "default": ""},
        ],
        "description": "Define o valor de outro componente da mesma página (ex.: um textbox).",
    },
    {
        "id": "toggle_component", "label": "Mostrar/Ocultar Componente", "icon": "bi-eye",
        "runs_on": "client",
        "params": [
            {"name": "target_component_id", "label": "ID do Componente Alvo", "type": "number", "default": ""},
            {"name": "mode", "label": "Modo", "type": "select", "options": ["show", "hide", "toggle"], "default": "toggle"},
        ],
        "description": "Mostra, oculta ou alterna a visibilidade de outro componente.",
    },
    {
        "id": "call_data_action", "label": "Chamar Ação de Dado", "icon": "bi-cloud-arrow-up-fill",
        "runs_on": "server",
        "params": [
            {"name": "data_action_id", "label": "Ação de Dado", "type": "data_action_select", "default": ""},
            {"name": "key", "label": "Chave do registro (update)", "type": "text", "default": ""},
            {"name": "payload", "label": "Payload JSON (update)", "type": "textarea", "default": "{}"},
        ],
        "description": (
            "Executa uma Ação de Dado cadastrada (tesseract_designer_data_action) "
            "sempre via servidor — nunca expõe credencial de conexão ao navegador."
        ),
    },
]


def get_action_def(action_id: str) -> dict | None:
    for action in ACTION_CATALOG:
        if action["id"] == action_id:
            return action
    return None


def get_server_action_ids() -> list[str]:
    return [a["id"] for a in ACTION_CATALOG if a["runs_on"] == "server"]
