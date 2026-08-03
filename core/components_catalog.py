"""
core/components_catalog.py

Fase 11, Patch 1 — catálogo de TIPOS de componente do Designer, com
schema de propriedades declarado por tipo. Terceiro catálogo do
projeto no mesmo padrão de `core/rules_catalog.py` (Fase 7b) e
`core/actions_catalog.py` (Fase 10): só metadado em código, sem
tabela.

## Por que este arquivo existe

Até a Fase 10, o painel de propriedades do editor fazia
`Object.keys(component.properties)` — ou seja, listava as chaves **já
salvas naquela instância**, não as que aquele tipo deveria ter. Três
defeitos que isso causava, todos corrigidos aqui:

1. Todo campo virava `<input type="text">` — `variant` deveria ser
   select, `bold` checkbox, `font_size` number, `text_color` color.
2. Todo valor salvo virava string (`input.value`), então `font_size:
   26` virava `"26"` e `bold: True` virava `"true"` — é por isso que
   os templates da Fase 10 comparam `p.checked_default == 'true'`
   contra string. Com o schema, o tipo é preservado no save
   (`coerce_properties()`).
3. Propriedade prevista no default mas ausente na instância não
   aparecia no painel, e não havia como adicionar nenhuma outra.

É o mesmo conceito que o GrapesJS chama de **trait** e o Puck chama
de **field**: o campo editável é declarado na definição do TIPO, não
descoberto na instância.

## Schema de uma propriedade

| Chave | Obrigatória | Regra |
|---|---|---|
| `name` | Sim | Chave dentro de `DesignerComponent.properties` |
| `label` | Sim | Texto PT-BR mostrado no painel (nunca a chave crua) |
| `type` | Sim | Widget — ver `PROP_TYPES` abaixo |
| `default` | Sim | Valor inicial, **no tipo certo** (int/bool/str) |
| `options` | Só em `select` | Lista de `str` ou de `{"value","label"}` |
| `help` | Não | Texto auxiliar curto abaixo do campo |
| `group` | Não | Agrupa no painel (`"conteudo"`/`"dados"`/`"estilo"`) |

`PROP_TYPES` e a coerção de tipo correspondente:

| `type` | Widget no editor | Tipo Python salvo |
|---|---|---|
| `text` | `<input type="text">` | `str` |
| `textarea` | `<textarea>` | `str` |
| `number` | `<input type="number">` | `int` |
| `bool` | `<input type="checkbox">` | `bool` |
| `select` | `<select>` | `str` |
| `color` | `<input type="color">` | `str` |
| `data_action` | `<select>` populado com DesignerDataAction | `int \\| None` |
| `icon` | `<input type="text">` (classe Bootstrap Icons) | `str` |

`accepts_children` marca os tipos que podem conter outros componentes
— usado só como declaração nesta fase; a árvore real (`parent_id`/
`order_index`) e o layout em fluxo são o Patch 2.
"""

PROP_TYPES = ("text", "textarea", "number", "bool", "select", "color", "data_action", "icon")

_VARIANTS = ["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]

COMPONENT_CATALOG = [
    # ── Texto e visual ────────────────────────────────────────────
    {
        "id": "heading", "label": "Título", "icon": "bi-type-h1",
        "category": "texto", "accepts_children": False, "default_size": (600, 50),
        "props": [
            {"name": "text", "label": "Texto", "type": "text", "default": "Título", "group": "conteudo"},
            {"name": "font_size", "label": "Tamanho da fonte (px)", "type": "number", "default": 26, "group": "estilo"},
            {"name": "text_color", "label": "Cor do texto", "type": "color", "default": "#012970", "group": "estilo"},
            {"name": "bold", "label": "Negrito", "type": "bool", "default": True, "group": "estilo"},
        ],
    },
    {
        "id": "label", "label": "Texto", "icon": "bi-fonts",
        "category": "texto", "accepts_children": False, "default_size": (200, 30),
        "props": [
            {"name": "text", "label": "Texto", "type": "textarea", "default": "Texto", "group": "conteudo"},
            {"name": "font_size", "label": "Tamanho da fonte (px)", "type": "number", "default": 14, "group": "estilo"},
            {"name": "text_color", "label": "Cor do texto", "type": "color", "default": "#444444", "group": "estilo"},
            {"name": "bold", "label": "Negrito", "type": "bool", "default": False, "group": "estilo"},
        ],
    },
    {
        "id": "image", "label": "Imagem", "icon": "bi-image",
        "category": "texto", "accepts_children": False, "default_size": (200, 150),
        "props": [
            {"name": "src", "label": "URL da imagem", "type": "text", "default": "", "group": "conteudo"},
            {"name": "alt", "label": "Texto alternativo", "type": "text", "default": "", "group": "conteudo",
             "help": "Descrição para leitores de tela."},
        ],
    },
    {
        "id": "divider", "label": "Linha divisória", "icon": "bi-dash-lg",
        "category": "texto", "accepts_children": False, "default_size": (600, 4),
        "props": [
            {"name": "color", "label": "Cor", "type": "color", "default": "#ced4da", "group": "estilo"},
        ],
    },

    # ── Campos de formulário ──────────────────────────────────────
    {
        "id": "textbox", "label": "Campo de texto", "icon": "bi-input-cursor-text",
        "category": "formulario", "accepts_children": False, "default_size": (280, 60),
        "props": [
            {"name": "label", "label": "Rótulo", "type": "text", "default": "Campo", "group": "conteudo"},
            {"name": "placeholder", "label": "Texto de exemplo", "type": "text", "default": "", "group": "conteudo"},
            {"name": "field_name", "label": "Nome do campo", "type": "text", "default": "", "group": "dados",
             "help": "Casa com a coluna do registro numa Caixa de formulário."},
            {"name": "input_type", "label": "Tipo de entrada", "type": "select",
             "options": ["text", "email", "password", "number", "date", "time", "textarea"],
             "default": "text", "group": "conteudo"},
        ],
    },
    {
        "id": "select", "label": "Menu suspenso", "icon": "bi-menu-button-wide",
        "category": "formulario", "accepts_children": False, "default_size": (280, 60),
        "props": [
            {"name": "label", "label": "Rótulo", "type": "text", "default": "Selecione", "group": "conteudo"},
            {"name": "field_name", "label": "Nome do campo", "type": "text", "default": "", "group": "dados"},
            {"name": "options_source", "label": "Origem das opções", "type": "select",
             "options": [{"value": "static", "label": "Lista fixa"},
                         {"value": "data_action", "label": "Ação de Dado"}],
             "default": "static", "group": "dados"},
            {"name": "static_options", "label": "Opções fixas", "type": "text",
             "default": "Opção 1,Opção 2", "group": "dados", "help": "Separadas por vírgula."},
            {"name": "data_action_id", "label": "Ação de Dado", "type": "data_action", "default": None, "group": "dados"},
            {"name": "value_field", "label": "Coluna do valor", "type": "text", "default": "id", "group": "dados"},
            {"name": "label_field", "label": "Coluna do rótulo", "type": "text", "default": "name", "group": "dados"},
        ],
    },
    {
        "id": "checkbox", "label": "Caixa de marcar", "icon": "bi-check-square",
        "category": "formulario", "accepts_children": False, "default_size": (220, 30),
        "props": [
            {"name": "label", "label": "Rótulo", "type": "text", "default": "Marcar", "group": "conteudo"},
            {"name": "field_name", "label": "Nome do campo", "type": "text", "default": "", "group": "dados"},
            {"name": "checked_default", "label": "Marcado por padrão", "type": "bool", "default": False, "group": "conteudo"},
            {"name": "style", "label": "Estilo", "type": "select",
             "options": [{"value": "checkbox", "label": "Caixa"}, {"value": "switch", "label": "Interruptor"}],
             "default": "checkbox", "group": "estilo"},
        ],
    },
    {
        "id": "radio", "label": "Múltipla escolha", "icon": "bi-ui-radios",
        "category": "formulario", "accepts_children": False, "default_size": (280, 100),
        "props": [
            {"name": "label", "label": "Rótulo", "type": "text", "default": "Escolha", "group": "conteudo"},
            {"name": "field_name", "label": "Nome do campo", "type": "text", "default": "", "group": "dados"},
            {"name": "options", "label": "Opções", "type": "text", "default": "Opção 1,Opção 2",
             "group": "dados", "help": "Separadas por vírgula."},
            {"name": "default_value", "label": "Opção marcada por padrão", "type": "text", "default": "", "group": "conteudo"},
        ],
    },
    {
        "id": "button", "label": "Botão", "icon": "bi-hand-index",
        "category": "formulario", "accepts_children": False, "default_size": (140, 40),
        "props": [
            {"name": "text", "label": "Texto", "type": "text", "default": "Botão", "group": "conteudo"},
            {"name": "variant", "label": "Cor", "type": "select", "options": _VARIANTS,
             "default": "primary", "group": "estilo"},
            {"name": "icon", "label": "Ícone", "type": "icon", "default": "", "group": "estilo",
             "help": "Classe do Bootstrap Icons, ex.: bi-save."},
            {"name": "outline", "label": "Só contorno", "type": "bool", "default": False, "group": "estilo"},
        ],
    },

    # ── Contêineres e dados ───────────────────────────────────────
    {
        "id": "form_container", "label": "Caixa de formulário", "icon": "bi-bounding-box",
        "category": "container", "accepts_children": True, "default_size": (420, 320),
        "props": [
            {"name": "title", "label": "Título", "type": "text", "default": "Formulário", "group": "conteudo"},
            {"name": "data_action_id", "label": "Ação de Dado", "type": "data_action", "default": None, "group": "dados"},
            {"name": "key_param", "label": "Parâmetro da URL", "type": "text", "default": "id", "group": "dados",
             "help": "Qual parâmetro da URL indica o registro a carregar (ex.: ?id=42)."},
            {"name": "layout", "label": "Empilhar filhos", "type": "select",
             "options": [{"value": "vertical", "label": "Verticalmente"},
                         {"value": "horizontal", "label": "Horizontalmente"}],
             "default": "vertical", "group": "estilo"},
            {"name": "gap", "label": "Espaço entre filhos (px)", "type": "number", "default": 8, "group": "estilo"},
            {"name": "padding", "label": "Espaço interno (px)", "type": "number", "default": 12, "group": "estilo"},
            {"name": "align", "label": "Alinhamento dos filhos", "type": "select",
             "options": [{"value": "stretch", "label": "Esticar"},
                         {"value": "flex-start", "label": "Início"},
                         {"value": "center", "label": "Centro"},
                         {"value": "flex-end", "label": "Fim"}],
             "default": "stretch", "group": "estilo"},
        ],
    },
    {
        "id": "card", "label": "Cartão", "icon": "bi-card-heading",
        "category": "container", "accepts_children": True, "default_size": (320, 220),
        "props": [
            {"name": "title", "label": "Título", "type": "text", "default": "Título do Card", "group": "conteudo"},
            {"name": "body_text", "label": "Texto do corpo", "type": "textarea", "default": "", "group": "conteudo"},
            {"name": "image_src", "label": "URL da imagem", "type": "text", "default": "", "group": "conteudo"},
            {"name": "footer_text", "label": "Texto do rodapé", "type": "text", "default": "", "group": "conteudo"},
            {"name": "layout", "label": "Empilhar filhos", "type": "select",
             "options": [{"value": "vertical", "label": "Verticalmente"},
                         {"value": "horizontal", "label": "Horizontalmente"}],
             "default": "vertical", "group": "estilo"},
            {"name": "gap", "label": "Espaço entre filhos (px)", "type": "number", "default": 8, "group": "estilo"},
            {"name": "padding", "label": "Espaço interno (px)", "type": "number", "default": 12, "group": "estilo"},
            {"name": "align", "label": "Alinhamento dos filhos", "type": "select",
             "options": [{"value": "stretch", "label": "Esticar"},
                         {"value": "flex-start", "label": "Início"},
                         {"value": "center", "label": "Centro"},
                         {"value": "flex-end", "label": "Fim"}],
             "default": "stretch", "group": "estilo"},
        ],
    },
    {
        "id": "datagrid", "label": "Tabela de dados", "icon": "bi-table",
        "category": "dados", "accepts_children": False, "default_size": (600, 320),
        "props": [
            {"name": "title", "label": "Título", "type": "text", "default": "Lista", "group": "conteudo"},
            {"name": "data_action_id", "label": "Ação de Dado", "type": "data_action", "default": None, "group": "dados"},
            {"name": "columns", "label": "Colunas", "type": "text", "default": "", "group": "dados",
             "help": "Separadas por vírgula. Vazio = todas as colunas do registro."},
            {"name": "table_style", "label": "Estilo da tabela", "type": "select",
             "options": [{"value": "bordered", "label": "Com bordas"},
                         {"value": "striped", "label": "Listrada"},
                         {"value": "hover", "label": "Destaque ao passar o mouse"}],
             "default": "bordered", "group": "estilo"},
        ],
    },
    {
        "id": "list", "label": "Lista simples", "icon": "bi-list-ul",
        "category": "dados", "accepts_children": False, "default_size": (320, 260),
        "props": [
            {"name": "title", "label": "Título", "type": "text", "default": "Lista", "group": "conteudo"},
            {"name": "data_action_id", "label": "Ação de Dado", "type": "data_action", "default": None, "group": "dados"},
            {"name": "display_field", "label": "Coluna exibida", "type": "text", "default": "name", "group": "dados"},
        ],
    },

    # ── Indicadores ───────────────────────────────────────────────
    {
        "id": "alert", "label": "Aviso", "icon": "bi-exclamation-triangle",
        "category": "indicador", "accepts_children": False, "default_size": (400, 60),
        "props": [
            {"name": "message", "label": "Mensagem", "type": "textarea",
             "default": "Mensagem de alerta.", "group": "conteudo"},
            {"name": "variant", "label": "Cor", "type": "select", "options": _VARIANTS,
             "default": "info", "group": "estilo"},
            {"name": "dismissible", "label": "Pode ser fechado", "type": "bool", "default": False, "group": "conteudo"},
        ],
    },
    {
        "id": "badge", "label": "Selo", "icon": "bi-tag",
        "category": "indicador", "accepts_children": False, "default_size": (100, 30),
        "props": [
            {"name": "text", "label": "Texto", "type": "text", "default": "Novo", "group": "conteudo"},
            {"name": "variant", "label": "Cor", "type": "select", "options": _VARIANTS,
             "default": "primary", "group": "estilo"},
        ],
    },
    {
        "id": "progress_bar", "label": "Barra de progresso", "icon": "bi-bar-chart-steps",
        "category": "indicador", "accepts_children": False, "default_size": (300, 30),
        "props": [
            {"name": "value", "label": "Valor atual", "type": "number", "default": 50, "group": "conteudo"},
            {"name": "min", "label": "Valor mínimo", "type": "number", "default": 0, "group": "conteudo"},
            {"name": "max", "label": "Valor máximo", "type": "number", "default": 100, "group": "conteudo"},
            {"name": "variant", "label": "Cor", "type": "select", "options": _VARIANTS,
             "default": "primary", "group": "estilo"},
            {"name": "label_visible", "label": "Mostrar o valor", "type": "bool", "default": True, "group": "estilo"},
        ],
    },
]

CATEGORIES = [
    ("texto", "Texto e visual"),
    ("formulario", "Formulário"),
    ("container", "Contêineres"),
    ("dados", "Dados"),
    ("indicador", "Indicadores"),
]

PROP_GROUPS = [
    ("conteudo", "Conteúdo"),
    ("dados", "Dados"),
    ("estilo", "Estilo"),
]


def get_component_def(type_id: str) -> dict | None:
    for comp in COMPONENT_CATALOG:
        if comp["id"] == type_id:
            return comp
    return None


def get_component_types() -> tuple:
    """Ids de tipo válidos — fonte única, consumida por
    model/core/designer_component.py (COMPONENT_TYPES)."""
    return tuple(c["id"] for c in COMPONENT_CATALOG)


def get_default_size(type_id: str) -> tuple:
    comp = get_component_def(type_id)
    return tuple(comp["default_size"]) if comp else (150, 40)


def get_default_properties(type_id: str) -> dict:
    """Defaults **no tipo certo** (int/bool/str/None), direto do
    schema — não é mais um dict paralelo mantido à mão no controller."""
    comp = get_component_def(type_id)
    if not comp:
        return {}
    return {p["name"]: p["default"] for p in comp["props"]}


def accepts_children(type_id: str) -> bool:
    comp = get_component_def(type_id)
    return bool(comp and comp.get("accepts_children"))


def _coerce_one(prop_def: dict, raw):
    """Converte o valor cru vindo do formulário para o tipo declarado
    no schema. Sem isso, tudo chega como string do `<input>` e o
    template acaba comparando `== 'true'` (defeito real da Fase 10)."""
    prop_type = prop_def["type"]

    if prop_type == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "on", "1", "yes")

    if prop_type == "number":
        if isinstance(raw, bool):
            return prop_def["default"]
        try:
            return int(raw)
        except (TypeError, ValueError):
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                return prop_def["default"]

    if prop_type == "data_action":
        if raw in (None, "", "None"):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    return "" if raw is None else str(raw)


def coerce_properties(type_id: str, raw_properties: dict) -> dict:
    """Aplica o schema sobre o que veio do editor: descarta chave que
    não existe no tipo (evita lixo acumulado em `properties`),
    completa a que faltou com o default, e converte cada valor para o
    tipo declarado."""
    comp = get_component_def(type_id)
    if not comp:
        return dict(raw_properties or {})

    raw_properties = raw_properties or {}
    result = {}
    for prop_def in comp["props"]:
        name = prop_def["name"]
        if name in raw_properties:
            result[name] = _coerce_one(prop_def, raw_properties[name])
        else:
            result[name] = prop_def["default"]
    return result
