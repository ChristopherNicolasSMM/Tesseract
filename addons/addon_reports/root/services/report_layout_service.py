"""Composição HTML declarativa de impressão; sem código fornecido pelo cliente."""
import json
from html import escape
from jsonschema import Draft202012Validator
from .report_binding_service import ReportBindingService, BindingError


class ReportError(ValueError):
    def __init__(self, code, path='', status=422):
        self.code, self.path, self.status = code, path, status
        super().__init__(code)


def validate_schema(schema):
    if type(schema) is not dict:
        raise ReportError('reports.error.schema')
    # Primeiro corte sem referências: nunca buscar schemas pela rede.
    def walk(value):
        if isinstance(value, dict):
            if any(key in value for key in ('$ref', '$dynamicRef')):
                raise ReportError('reports.error.schema')
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ReportError('reports.error.schema') from exc


def validate_data(schema, data):
    validate_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(list(e.path)))
    if errors:
        raise ReportError('reports.error.data', '.'.join(map(str, errors[0].path)))


class ReportLayoutService:
    """MVP com fontes/estilos fixados, sem assets externos ou CSS livre."""
    TYPES = {'text', 'table', 'section', 'divider'}

    @classmethod
    def validate(cls, layout):
        if type(layout) is not dict or set(layout) != {'schema_version', 'body'} or (type(layout['schema_version']) is not int or layout['schema_version'] != 1):
            raise ReportError('reports.error.layout')
        ids = set()
        def walk(nodes, depth=0):
            if type(nodes) is not list or depth > 8:
                raise ReportError('reports.error.layout')
            for node in nodes:
                if type(node) is not dict or set(node) - {'id', 'type', 'props', 'children'}:
                    raise ReportError('reports.error.layout')
                ident = node.get('id')
                if type(ident) is not str or not ident or len(ident) > 80 or ident in ids:
                    raise ReportError('reports.error.layout')
                ids.add(ident)
                if len(ids) > 200 or (type(node.get('type')) is not str or node.get('type') not in cls.TYPES) or type(node.get('props')) is not dict:
                    raise ReportError('reports.error.layout', ident)
                props = node['props']
                allowed = {'text', 'binding', 'level'} if node['type'] == 'text' else {'collection', 'columns', 'empty_text'} if node['type'] == 'table' else set()
                if set(props) - allowed:
                    raise ReportError('reports.error.layout', ident)
                if node['type'] == 'text':
                    if ('text' in props) == ('binding' in props) or props.get('level', 'body') not in ('body', 'title', 'subtitle'):
                        raise ReportError('reports.error.layout', ident)
                    if 'text' in props and (type(props['text']) is not str or len(props['text']) > 10000):
                        raise ReportError('reports.error.layout', ident)
                    if 'binding' in props:
                        cls._binding(props['binding'], ident, allow_item=False)
                if node['type'] == 'table':
                    cls._binding(props.get('collection'), ident, allow_item=False)
                    columns = props.get('columns')
                    if type(columns) is not list or not 1 <= len(columns) <= 12:
                        raise ReportError('reports.error.layout', ident)
                    for column in columns:
                        if type(column) is not dict or set(column) != {'label', 'binding'} or type(column['label']) is not str or len(column['label']) > 120:
                            raise ReportError('reports.error.layout', ident)
                        cls._binding(column['binding'], ident, allow_item=True)
                    if type(props.get('empty_text', '')) is not str:
                        raise ReportError('reports.error.layout', ident)
                if node['type'] == 'section':
                    walk(node.get('children', []), depth + 1)
                elif 'children' in node:
                    raise ReportError('reports.error.layout', ident)
        walk(layout['body'])

    @staticmethod
    def _binding(binding, ident, allow_item):
        if type(binding) is not dict or set(binding) != {'source', 'path'}:
            raise ReportError('reports.error.binding', ident)
        sources = ('data', 'parameters', 'item') if allow_item else ('data', 'parameters')
        source, path = binding.get('source'), binding.get('path')
        if source not in sources or type(path) is not list or len(path) > 32 or any(type(p) is not str or not p for p in path):
            raise ReportError('reports.error.binding', ident)

    @classmethod
    def render(cls, layout, data, parameters):
        cls.validate(layout)
        def resolve(binding, item=None, scoped=False):
            try:
                return ReportBindingService.resolve(binding, data=data, parameters=parameters, item=item, in_item_scope=scoped)
            except BindingError as exc:
                raise ReportError('reports.error.binding', '.'.join(exc.path)) from exc
        def value_html(value):
            if type(value) in (dict, list):
                raise ReportError('reports.error.binding')
            return escape('' if value is None else str(value))
        def render_nodes(nodes):
            parts = []
            for node in nodes:
                props = node['props']
                if node['type'] == 'text':
                    value = props['text'] if 'text' in props else resolve(props['binding'])
                    tag = {'title': 'h1', 'subtitle': 'h2', 'body': 'p'}[props.get('level', 'body')]
                    parts.append(f'<{tag}>{value_html(value)}</{tag}>')
                elif node['type'] == 'divider':
                    parts.append('<hr>')
                elif node['type'] == 'section':
                    parts.append('<section>' + render_nodes(node.get('children', [])) + '</section>')
                else:
                    items = resolve(props['collection'])
                    if type(items) is not list or len(items) > 2000:
                        raise ReportError('reports.error.collection', node['id'])
                    columns = props['columns']
                    header = ''.join('<th>' + escape(c['label']) + '</th>' for c in columns)
                    rows = ''.join('<tr>' + ''.join('<td>' + value_html(resolve(c['binding'], item, True)) + '</td>' for c in columns) + '</tr>' for item in items)
                    if not items:
                        rows = f'<tr><td colspan="{len(columns)}">{escape(props.get("empty_text", ""))}</td></tr>'
                    parts.append('<table><thead><tr>' + header + '</tr></thead><tbody>' + rows + '</tbody></table>')
            return ''.join(parts)
        body = render_nodes(layout['body'])
        style = '@page { size: A4; margin: 15mm; @bottom-right { content: counter(page); } } body { background: white; color: #182230; font: 10pt sans-serif; } table { width:100%; border-collapse:collapse; } th,td { padding:6pt; border:1px solid #cbd5e1; overflow-wrap:anywhere; } th { background:#eef2f6; } thead { display:table-header-group; } p { white-space:pre-wrap; overflow-wrap:anywhere; } h1,h2 { break-after:avoid; }'
        return '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><style>' + style + '</style><body>' + body + '</body></html>'


def default_document():
    return {'schema_version': 1, 'body': [{'id': 'title', 'type': 'text', 'props': {'text': 'Relatório', 'level': 'title'}}]}
