"""
core/rules_catalog.py

Catálogo de regras de negócio aplicáveis a campos de formulário —
adaptado de rules/rule_types.py (DEVStationFlask). Mantida a mesma
estrutura (id, label, ícone, parâmetros, descrição) por grupo.

Escopo da Fase 7b (decisão registrada em BACKLOG.md): só o grupo
**Validação** está conectado a algo real nesta fase — os formulários
genéricos do CrudGen (`manage.html`/`detail.html`, todas as 24
entidades). **Visibilidade** e **Cálculo** referenciam IDs de
componente arbitrários (`comp_1`, `comp_2`...) que só fazem sentido
dentro de um canvas — ficam catalogados aqui (prontos pra quando o
Designer, Fase 7c, existir) mas sem nenhuma UI/engine consumindo eles
ainda.

`js_check` aqui é só METADADO (documentação de qual função do
`rule_engine.js` a regra corresponde) — o motor real
(`static/js/rule_engine.js`) implementa as funções de Validação
diretamente; o `js_check` armazenado não é `eval`ado em lugar nenhum
(evita o problema de segurança de rodar string-como-código vinda do
banco).
"""

RULE_CATALOG = [
    {
        "group": "Validação",
        "connected": True,  # tem motor real (rule_engine.js) consumindo
        "rules": [
            {
                "id": "obrigatorio", "label": "Campo Obrigatório", "icon": "bi-asterisk",
                "params": [{"name": "message", "label": "Mensagem de Erro", "type": "text", "default": "Campo obrigatório."}],
                "js_function": "required",
                "description": "Impede que o campo fique vazio.",
            },
            {
                "id": "min_length", "label": "Tamanho Mínimo", "icon": "bi-text-left",
                "params": [
                    {"name": "min", "label": "Mínimo de Caracteres", "type": "number", "default": "3"},
                    {"name": "message", "label": "Mensagem", "type": "text", "default": "Mínimo de {min} caracteres."},
                ],
                "js_function": "minLength",
                "description": "Valida tamanho mínimo do texto.",
            },
            {
                "id": "max_length", "label": "Tamanho Máximo", "icon": "bi-text-right",
                "params": [
                    {"name": "max", "label": "Máximo de Caracteres", "type": "number", "default": "100"},
                    {"name": "message", "label": "Mensagem", "type": "text", "default": "Máximo de {max} caracteres."},
                ],
                "js_function": "maxLength",
                "description": "Valida tamanho máximo do texto.",
            },
            {
                "id": "email", "label": "Formato E-mail", "icon": "bi-envelope",
                "params": [{"name": "message", "label": "Mensagem", "type": "text", "default": "E-mail inválido."}],
                "js_function": "email",
                "description": "Valida formato de e-mail.",
            },
            {
                "id": "cpf", "label": "CPF Válido", "icon": "bi-person-vcard",
                "params": [{"name": "message", "label": "Mensagem", "type": "text", "default": "CPF inválido."}],
                "js_function": "cpf",
                "description": "Valida CPF com dígito verificador.",
            },
            {
                "id": "cnpj", "label": "CNPJ Válido", "icon": "bi-building",
                "params": [{"name": "message", "label": "Mensagem", "type": "text", "default": "CNPJ inválido."}],
                "js_function": "cnpj",
                "description": "Valida CNPJ com dígito verificador.",
            },
            {
                "id": "numero", "label": "Apenas Números", "icon": "bi-123",
                "params": [{"name": "message", "label": "Mensagem", "type": "text", "default": "Apenas números são permitidos."}],
                "js_function": "onlyNumbers",
                "description": "Aceita somente dígitos.",
            },
            {
                "id": "min_valor", "label": "Valor Mínimo", "icon": "bi-arrow-down-circle",
                "params": [
                    {"name": "min", "label": "Valor Mínimo", "type": "number", "default": "0"},
                    {"name": "message", "label": "Mensagem", "type": "text", "default": "Valor deve ser ≥ {min}."},
                ],
                "js_function": "minValue",
                "description": "Valor numérico mínimo.",
            },
            {
                "id": "max_valor", "label": "Valor Máximo", "icon": "bi-arrow-up-circle",
                "params": [
                    {"name": "max", "label": "Valor Máximo", "type": "number", "default": "9999"},
                    {"name": "message", "label": "Mensagem", "type": "text", "default": "Valor deve ser ≤ {max}."},
                ],
                "js_function": "maxValue",
                "description": "Valor numérico máximo.",
            },
            {
                "id": "data_valida", "label": "Data Válida", "icon": "bi-calendar-check",
                "params": [{"name": "message", "label": "Mensagem", "type": "text", "default": "Data inválida."}],
                "js_function": "validDate",
                "description": "Verifica se a data é válida.",
            },
        ],
    },
    {
        "group": "Visibilidade",
        "connected": False,  # catalogado, sem engine — depende do Designer (Fase 7c)
        "rules": [
            {
                "id": "visivel_se", "label": "Visível Se", "icon": "bi-eye",
                "params": [
                    {"name": "source_id", "label": "Campo Origem (ID)", "type": "text", "default": "comp_1"},
                    {"name": "operator", "label": "Operador", "type": "select", "options": ["==", "!=", ">", "<", ">=", "<=", "contains"], "default": "=="},
                    {"name": "value", "label": "Valor Comparado", "type": "text", "default": "sim"},
                ],
                "js_function": "visibleIf",
                "description": "Mostra este componente quando a condição for verdadeira.",
            },
            {
                "id": "oculto_se", "label": "Oculto Se", "icon": "bi-eye-slash",
                "params": [
                    {"name": "source_id", "label": "Campo Origem (ID)", "type": "text", "default": "comp_1"},
                    {"name": "operator", "label": "Operador", "type": "select", "options": ["==", "!=", ">", "<", ">=", "<="], "default": "=="},
                    {"name": "value", "label": "Valor", "type": "text", "default": "nao"},
                ],
                "js_function": "hiddenIf",
                "description": "Oculta este componente quando a condição for verdadeira.",
            },
            {
                "id": "habilitado_se", "label": "Habilitado Se", "icon": "bi-toggle-on",
                "params": [
                    {"name": "source_id", "label": "Campo Origem (ID)", "type": "text", "default": "comp_1"},
                    {"name": "operator", "label": "Operador", "type": "select", "options": ["==", "!=", "filled", "empty"], "default": "filled"},
                    {"name": "value", "label": "Valor (se ==)", "type": "text", "default": ""},
                ],
                "js_function": "enabledIf",
                "description": "Habilita o componente quando a condição for verdadeira.",
            },
        ],
    },
    {
        "group": "Cálculo",
        "connected": False,
        "rules": [
            {
                "id": "calcular", "label": "Calcular Expressão", "icon": "bi-calculator",
                "params": [
                    {"name": "expression", "label": "Expressão JS (use DSB.val('id'))", "type": "text", "default": "DSB.val('comp_1') * 1.1"},
                    {"name": "target_id", "label": "ID do Campo Destino", "type": "text", "default": "comp_2"},
                ],
                "js_function": "calculate",
                "description": "Calcula e atribui resultado ao campo destino.",
            },
            {
                "id": "somar", "label": "Somar Campos", "icon": "bi-plus-circle",
                "params": [
                    {"name": "ids", "label": "IDs separados por vírgula", "type": "text", "default": "comp_1,comp_2"},
                    {"name": "target_id", "label": "ID Destino", "type": "text", "default": "comp_3"},
                ],
                "js_function": "sum",
                "description": "Soma os valores dos campos e coloca no destino.",
            },
            {
                "id": "progresso", "label": "Controlar ProgressBar", "icon": "bi-bar-chart-steps",
                "params": [
                    {"name": "source_id", "label": "Campo Valor (ID)", "type": "text", "default": "comp_1"},
                    {"name": "min", "label": "Valor Mínimo", "type": "number", "default": "0"},
                    {"name": "max", "label": "Valor Máximo", "type": "number", "default": "100"},
                    {"name": "target_id", "label": "ID da ProgressBar", "type": "text", "default": "comp_2"},
                ],
                "js_function": "linkProgress",
                "description": "Vincula um campo numérico a uma barra de progresso.",
            },
            {
                "id": "status_map", "label": "Mapear Status", "icon": "bi-signpost-2",
                "params": [
                    {"name": "source_id", "label": "Campo Origem (ID)", "type": "text", "default": "comp_1"},
                    {"name": "mapping", "label": "JSON {valor: texto}", "type": "textarea", "default": '{"1":"Ativo","0":"Inativo"}'},
                    {"name": "target_id", "label": "ID StatusBar/Label", "type": "text", "default": "comp_2"},
                ],
                "js_function": "statusMap",
                "description": "Mapeia valor para texto e atualiza StatusBar/Label.",
            },
            {
                "id": "formatar", "label": "Formatar Valor", "icon": "bi-textarea-t",
                "params": [
                    {"name": "source_id", "label": "Campo Origem (ID)", "type": "text", "default": "comp_1"},
                    {"name": "format", "label": "Formato (R$ {v})", "type": "text", "default": "R$ {v}"},
                    {"name": "target_id", "label": "ID Destino", "type": "text", "default": "comp_2"},
                ],
                "js_function": "format",
                "description": "Formata o valor e exibe no campo destino.",
            },
        ],
    },
]


def get_rule_def(rule_id: str) -> dict | None:
    for group in RULE_CATALOG:
        for rule in group["rules"]:
            if rule["id"] == rule_id:
                return rule
    return None


def get_connected_rule_ids() -> list[str]:
    """IDs de regra com motor real (hoje: só o grupo Validação)."""
    return [
        rule["id"]
        for group in RULE_CATALOG if group.get("connected")
        for rule in group["rules"]
    ]
