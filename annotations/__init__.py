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


def display_field(value: str):
    """Campo usado como nome de exibição do model (ex: 'username', 'titulo')."""
    def decorator(cls):
        cls._display_field = value
        return cls
    return decorator


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
