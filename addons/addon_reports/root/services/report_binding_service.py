"""Resolução declarativa de campos, sem eval, atributos ou objetos ORM."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BindingError(ValueError):
    """Erro estruturado; texto visível será traduzido pelo adaptador da IDE."""
    code: str
    path: tuple

    def __str__(self):
        return self.code


class ReportBindingService:
    SOURCES = frozenset({'data', 'parameters', 'item'})

    @classmethod
    def resolve(cls, binding, *, data, parameters, item=None, in_item_scope=False):
        """Preserva null/false/zero; fallback só resolve campo realmente ausente."""
        if type(binding) is not dict:
            raise BindingError('reports.binding.invalid', ())
        if set(binding) - {'source', 'path', 'fallback', 'format'}:
            raise BindingError('reports.binding.invalid', ())
        source = binding.get('source')
        path = binding.get('path')
        if (type(source) is not str or source not in cls.SOURCES or
                type(path) is not list or len(path) > 32 or
                any(type(segment) is not str or not segment for segment in path)):
            raise BindingError('reports.binding.invalid', ())
        if source == 'item' and not in_item_scope:
            raise BindingError('reports.binding.scope_invalid', tuple(path))
        value = {'data': data, 'parameters': parameters, 'item': item}[source]
        for index, segment in enumerate(path):
            if type(value) is not dict:
                raise BindingError('reports.binding.type_invalid', tuple(path[:index]))
            if segment not in value:
                if 'fallback' in binding:
                    return binding['fallback']
                raise BindingError('reports.binding.missing', tuple(path[:index + 1]))
            value = value[segment]
        return value
