"""
annotations/

Decorators de metadado usados pelo CrudGen (Fase 4) para anotar models
e gerar Service/Controller/Routes/Templates a partir deles. Portado da
arquitetura de anotações do PyTeca, preservada como estava — é a parte
que o Christopher pediu para manter intacta ("gostei da arquitetura
limpa com os anotations").
"""
from typing import List, Optional, Callable, Any, Dict


# ---- Decorators de entidade ----
def label(value: str):
    def decorator(cls):
        cls._entity_label = value
        return cls
    return decorator


def plural(value: str):
    def decorator(cls):
        cls._entity_plural = value
        return cls
    return decorator


def menu_icon(value: str):
    """
    Ícone (classe Bootstrap Icons, ex.: "bi-flask") usado quando a
    Transação deste model é AUTO-gerada pela descoberta de módulos
    (skill 09 + adenda skill 00). Opcional — sem ela, a Transação
    auto-gerada usa "bi-app" genérico. Não afeta Transação escrita à
    mão (essa já declara "icon" direto no dict).
    """
    def decorator(cls):
        cls._menu_icon = value
        return cls
    return decorator


def display_field(value: str):
    """Campo usado como nome de exibição do model (ex: 'username', 'titulo')."""
    def decorator(cls):
        cls._display_field = value
        return cls
    return decorator


def weak_ref(field: str, resolver: str, options: str | None = None, value_field: str | None = None):
    """
    Marca `field` como referência fraca (skill 02 — sem FK real,
    cross-Addon) resolvida em runtime por `resolver`. Também usada
    (skill 11, extensão) pra FK real DENTRO da mesma Feature/Addon
    quando só se quer o combo de busca da UI — a constraint de banco
    continua real nesse caso, isto é puramente cosmético/formulário.

    `resolver` é um caminho pontuado até uma função `(valor) -> dict | None`
    que devolve, no mínimo, a chave "display" (calculada no lado de
    quem possui o model alvo, a partir do @display_field dele — nunca
    hardcoded aqui). `valor` é o que estiver em `field` — normalmente
    um id inteiro, mas pode ser uma string (ex.: `device_function_name`,
    que guarda o `name` de outro Addon, skill 02 — resolver por nome é
    a convenção nesse caso, nunca id interno). Ver
    docs/skills/11-referencia-fraca-e-display-field.md.

    `options` (opcional): o @plural do model alvo — habilita o combo
    de busca assíncrono (`/api/options/<options>`) no formulário de
    detalhe gerado, no lugar do `<input>` de id cru. Sem isso, o campo
    mostra só o nome resolvido como texto de apoio ao lado do input.

    `value_field` (opcional, extensão desta rodada): por padrão o
    combo guarda o `id` (PK) do registro escolhido no campo do
    formulário — é o caso comum (`material_id` guardando
    `Material.id`). Quando `field` guarda outra coluna do alvo em vez
    do id (ex.: `device_function_name` guardando `DeviceFunction.name`,
    não `DeviceFunction.id`), `value_field` diz qual coluna do alvo
    usar como valor armazenado — o `/api/options` valida que é uma
    coluna real do model alvo antes de aceitar (skill 11 §6).
    Diferentes `@weak_ref` podem apontar pro MESMO `options` com
    `value_field` diferente (ex.: `DeviceActor.function_id` usa o
    padrão "id"; `DashboardWidget.device_function_name` usa "name" —
    os dois miram `DeviceFunction`, cada consumidor guarda o que
    precisa, sem conflito).

    Uso no model:
        @weak_ref("material_id",
                   resolver="addons.addon_estoque.root.services.material_lookup.get_material",
                   options="materials")
        class Malte(db.Model):
            material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK

    Múltiplas @weak_ref podem ser empilhadas se o model tiver mais de
    um campo de referência fraca.
    """
    def decorator(cls):
        if not hasattr(cls, '_weak_refs'):
            cls._weak_refs = []
        cls._weak_refs.append({
            "field": field, "resolver": resolver, "options": options, "value_field": value_field,
        })
        return cls
    return decorator


def get_weak_refs(cls) -> list[dict]:
    """Retorna a lista de {"field", "resolver"} de @weak_ref declaradas no model."""
    return getattr(cls, '_weak_refs', [])


def field_labels(labels: dict):
    """
    Rótulos de campo (PT-BR) para os formulários gerados
    (`manage.html`/`detail.html`) — sem essa anotação, o campo cai no
    fallback atual (`field.replace('_', ' ').title()`), que produz
    texto em inglês titlecase a partir do nome Python da coluna.

    Mesma convenção de conveniência de autoria da skill 00 (texto
    direto na anotação, como `@label`/`Column(label=...)`) — ainda não
    passa pelo pipeline de tradução (`i18n/pt_BR.json`); isso é decisão
    em aberto da análise de field metadata do CrudGen (skill 12/19).

    ```python
    @field_labels({
        "container_type": "Tipo",
        "device_id": "Dispositivo",
    })
    ```
    """
    def decorator(cls):
        cls._field_labels = {**getattr(cls, '_field_labels', {}), **labels}
        return cls
    return decorator


def get_field_labels(cls) -> dict:
    """Retorna o dict {field: label} declarado via @field_labels no model."""
    return getattr(cls, '_field_labels', {})


# ---- Decorators de UI (SmartList) ----
class Column:
    def __init__(self, name: str, label: Optional[str] = None, width: Optional[str] = None,
                 sortable: bool = False, filterable: bool = False, align: str = "start"):
        self.name = name
        self.label = label or name.replace('_', ' ').title()
        self.width = width
        self.sortable = sortable
        self.filterable = filterable
        self.align = align


class Filter:
    def __init__(self, name: str, type: str = "text", placeholder: Optional[str] = None,
                 options: Optional[List[tuple]] = None, options_callable: Optional[Callable] = None):
        self.name = name
        self.type = type
        self.placeholder = placeholder
        self.options = options
        self.options_callable = options_callable


def listview(columns: List[Column], default_sort: Optional[str] = None,
             filters: Optional[List[Filter]] = None):
    def decorator(cls):
        cls._ui_listview = {
            "columns": [c.__dict__ for c in columns],
            "default_sort": default_sort,
            "filters": [f.__dict__ for f in (filters or [])],
        }
        return cls
    return decorator


# ---- Decorators de formulário ----
class Group:
    def __init__(self, name: str, label: str, fields: List[str], collapsible: bool = False):
        self.name = name
        self.label = label
        self.fields = fields
        self.collapsible = collapsible


def form(fields: List[str], groups: Optional[List[Group]] = None):
    def decorator(cls):
        cls._ui_form = {
            "fields": fields,
            "groups": [g.__dict__ for g in (groups or [])],
        }
        return cls
    return decorator


# ---- Decorators de validação ----
def required(field: str, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "required",
            "message": message or f"{field} é obrigatório",
        })
        return cls
    return decorator


def max_length(field: str, max: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "max_length",
            "max": max,
            "message": message or f"{field} deve ter no máximo {max} caracteres",
        })
        return cls
    return decorator


def min_length(field: str, min: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "min_length",
            "min": min,
            "message": message or f"{field} deve ter no mínimo {min} caracteres",
        })
        return cls
    return decorator


def min_value(field: str, min: int, message: Optional[str] = None):
    def decorator(cls):
        cls._validations = getattr(cls, '_validations', {})
        cls._validations.setdefault(field, []).append({
            "type": "min_value",
            "min": min,
            "message": message or f"{field} deve ser no mínimo {min}",
        })
        return cls
    return decorator


def choices(field: str, label: str | None = None, order: str = "asc"):
    """SELECT DISTINCT automático para filtros (ex.: @choices("genre"))."""
    def decorator(cls):
        if not hasattr(cls, '_choices_fields'):
            cls._choices_fields = []
        cls._choices_fields.append({
            "field": field,
            "label": label or field.replace("_", " ").title(),
            "order": order,
        })
        return cls
    return decorator


def get_choices_fields(cls) -> list[dict]:
    return getattr(cls, '_choices_fields', [])


def enum_field(field: str, options: list, label: str | None = None):
    """
    Campo de OPÇÃO FIXA (enum) — o CrudGen gera `<select>` com essas
    opções no formulário de detalhe (criação/edição), em vez de
    `<input type="text">` livre.

    Diferente de @choices (acima): @choices é dinâmico — computa
    `SELECT DISTINCT` do que já existe no banco, só serve pra montar
    filtro de lista, nunca aparece no formulário. @enum_field é
    estático — as opções são a fonte de verdade declarada no código
    (ex.: os `status` válidos de uma máquina de estados), valem tanto
    pra criar quanto editar, e funcionam mesmo com o banco vazio.

    `options`: lista de string (valor == label) ou lista de tupla
    `(valor, label)` quando o texto exibido precisa ser diferente do
    valor gravado.

    Uso no model:
        @enum_field("status", options=["draft", "active", "paused", "completed", "aborted"])
        class BrewSession(db.Model):
            status = db.Column(db.String(20), default="draft")  # SEM CHECK constraint — validação é aqui
    """
    def decorator(cls):
        if not hasattr(cls, '_enum_fields'):
            cls._enum_fields = []
        normalized = []
        for opt in options:
            if isinstance(opt, tuple):
                normalized.append({"value": opt[0], "label": opt[1]})
            else:
                normalized.append({"value": opt, "label": opt})
        cls._enum_fields.append({
            "field": field,
            "label": label or field.replace("_", " ").title(),
            "options": normalized,
        })
        return cls
    return decorator


def get_enum_fields(cls) -> list[dict]:
    """Retorna a lista de {"field", "label", "options"} de @enum_field declaradas no model."""
    return getattr(cls, '_enum_fields', [])


# ---- Extração de metadados ----
def get_model_metadata(cls) -> Dict[str, Any]:
    """Extrai todos os metadados anotados de uma classe, para o CrudGen."""
    return {
        "name": cls.__name__,
        "label": getattr(cls, '_entity_label', cls.__name__),
        "plural": getattr(cls, '_entity_plural', cls.__name__.lower() + 's'),
        "ui_listview": getattr(cls, '_ui_listview', None),
        "ui_form": getattr(cls, '_ui_form', None),
        "validations": getattr(cls, '_validations', {}),
        "display_field": getattr(cls, '_display_field', 'id'),
        "menu_icon": getattr(cls, '_menu_icon', None),
        "weak_refs": getattr(cls, '_weak_refs', []),
        "enum_fields": getattr(cls, '_enum_fields', []),
    }


# ---- @permission: Camada 2 (granularidade de negócio) ----
# Camada 1 (permissão automática de rota gerada pelo CrudGen) passa a
# ser real a partir desta fase — ver core/permissions_sync.py.
# @permission cobre ações de negócio que não mapeiam 1:1 para uma rota,
# ou quando se quer atribuir a permissão a um Role já na sincronização.
def permission(action: str, role_required: str | None = None, description: str | None = None):
    """
    Uso no model:
        @permission("trash", role_required="brewmaster",
                     description="Mover lote para a lixeira")
        class Recipe(db.Model):
            ...

    Nome de permissão sincronizado: "<plural>.<action>" — mesmo padrão
    da Camada 1, para nunca haver dois formatos de nome coexistindo.
    """
    def decorator(cls):
        if not hasattr(cls, '_permissions'):
            cls._permissions = []
        cls._permissions.append({
            "action": action,
            "role_required": role_required,
            "description": description or f"Permite '{action}' em {cls.__name__}",
        })
        return cls
    return decorator


def get_permissions_meta(cls) -> list[dict]:
    """Retorna as permissões de negócio (@permission) declaradas no model."""
    return getattr(cls, '_permissions', [])


# ---- @odata_expose: Fase 10 (Patch 1) ----
# Marca uma entidade do CrudGen como exposta pelo provedor OData local
# (core/odata_local_seed.py + endpoint do Patch 2). Opt-in por entidade
# (decisão registrada em BACKLOG.md, Fase 10) — sem esta anotação, a
# entidade não aparece no provedor local, mesmo que o Addon esteja
# ativo. Mesmo padrão de @permission: metadado em atributo de classe,
# lido por get_odata_expose_meta(cls); nenhum comportamento de runtime
# nasce aqui neste patch, só a marcação.
def odata_expose(entity_name: str, permission_required: str | None = None):
    """
    Uso no model:
        @odata_expose("yeast_strain", permission_required="yeast_strains.list")
        class YeastStrain(db.Model):
            ...

    `entity_name` é o nome usado no EntitySet do provedor local — não
    precisa ser igual ao `__tablename__` (mesmo espírito de
    DesignerDataAction.entity_name, que referencia esse nome, não a
    tabela física).
    """
    def decorator(cls):
        cls._odata_expose = {
            "entity_name": entity_name,
            "permission_required": permission_required,
        }
        return cls
    return decorator


def get_odata_expose_meta(cls) -> dict | None:
    """Retorna o metadado de @odata_expose declarado no model, ou None se ausente."""
    return getattr(cls, '_odata_expose', None)
