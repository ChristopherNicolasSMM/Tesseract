"""Composição HTML declarativa de impressão; sem código fornecido pelo cliente."""
import json
from html import escape
from jsonschema import Draft202012Validator
from .report_page_service import page_config, page_css, validate_pagination, pagination_css
from .report_image_service import validate_image, image_css, MAX_TOTAL_IMAGE_BYTES, MAX_IMAGE_COUNT
from .report_format_service import validate_format, format_value
from .report_calculation_service import AGGREGATES, validate_condition, condition_matches, aggregate
from .report_style_service import validate_style, style_css
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
    """Composição com aparência tipada, sem assets externos ou CSS livre."""
    TYPES = {'text', 'table', 'section', 'divider', 'page_break', 'image'}

    @classmethod
    def validate(cls, layout):
        if type(layout) is not dict or not {'schema_version', 'body'} <= set(layout) or set(layout) - {'schema_version', 'body', 'page'} or (type(layout['schema_version']) is not int or layout['schema_version'] != 1):
            raise ReportError('reports.error.layout')
        try:
            if 'page' in layout and layout['page'] is None:
                raise ValueError('Invalid page')
            page_config(layout.get('page'))
        except ValueError as exc:
            raise ReportError('reports.error.page', 'page') from exc
        ids = set()
        image_bytes = image_count = 0
        def walk(nodes, depth=0, in_columns=False):
            nonlocal image_bytes, image_count
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
                if 'condition' in props:
                    if not validate_condition(props['condition']):
                        raise ReportError('reports.error.condition', ident)
                    cls._binding(props['condition']['binding'], ident, allow_item=False)
                allowed = {'text', 'binding', 'level', 'format'} if node['type'] == 'text' else {'collection', 'columns', 'empty_text'} if node['type'] == 'table' else {'columns', 'gap'} if node['type'] == 'section' else {'source', 'alt', 'width', 'height'} if node['type'] == 'image' else set()
                allowed.add('condition')
                if node['type'] != 'page_break':
                    allowed.update(('style', 'pagination'))
                pagination = props.get('pagination', {})
                if not validate_pagination(pagination) or (in_columns and (node['type']=='page_break' or pagination.get('break_before') or pagination.get('break_after'))):
                    raise ReportError('reports.error.pagination', ident)
                if 'style' in props and not validate_style(props['style'], table=node['type']=='table'):
                    raise ReportError('reports.error.layout', ident)
                if set(props) - allowed:
                    raise ReportError('reports.error.layout', ident)
                if node['type'] == 'image':
                    try:
                        image_bytes += validate_image(props)
                    except ValueError as exc:
                        raise ReportError('reports.error.image', ident) from exc
                    image_count += 1
                    if image_bytes > MAX_TOTAL_IMAGE_BYTES or image_count > MAX_IMAGE_COUNT:
                        raise ReportError('reports.error.image', ident)
                if node['type'] == 'text':
                    if 'format' in props and not validate_format(props['format']):
                        raise ReportError('reports.error.format', ident)
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
                        if type(column) is not dict or not {'label', 'binding'} <= set(column) or set(column) - {'label', 'binding', 'align', 'width', 'format', 'aggregate'} or type(column['label']) is not str or len(column['label']) > 120:
                            raise ReportError('reports.error.layout', ident)
                        if 'aggregate' in column and (type(column['aggregate']) is not str or column['aggregate'] not in AGGREGATES):
                            raise ReportError('reports.error.aggregate', ident)
                        if 'format' in column and not validate_format(column['format']):
                            raise ReportError('reports.error.format', ident)
                        if 'align' in column and not validate_style({'align':column['align']}):
                            raise ReportError('reports.error.layout', ident)
                        if 'width' in column and (type(column['width']) is not int or not 1 <= column['width'] <= 100):
                            raise ReportError('reports.error.layout', ident)
                        cls._binding(column['binding'], ident, allow_item=True)
                    if sum(c.get('width', 0) for c in columns) > 100:
                        raise ReportError('reports.error.layout', ident)
                    if type(props.get('empty_text', '')) is not str:
                        raise ReportError('reports.error.layout', ident)
                if node['type'] == 'section':
                    if ('columns' in props and (type(props['columns']) is not int or not 1 <= props['columns'] <= 4)) or ('gap' in props and (type(props['gap']) is not int or not 0 <= props['gap'] <= 24)):
                        raise ReportError('reports.error.layout', ident)
                    walk(node.get('children', []), depth + 1, in_columns or props.get('columns',1)>1)
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
        def value_html(value, spec=None, path=''):
            if type(value) in (dict, list):
                raise ReportError('reports.error.binding')
            try:
                return escape(format_value(value, spec or {}))
            except (ValueError, OverflowError) as exc:
                raise ReportError('reports.error.format', path) from exc
        def render_nodes(nodes):
            parts = []
            for node in nodes:
                props = node['props']
                if 'condition' in props:
                    condition_value = resolve(props['condition']['binding'])
                    try:
                        visible = condition_matches(condition_value, props['condition'])
                    except ValueError as exc:
                        raise ReportError('reports.error.condition', node['id']) from exc
                    if not visible:
                        continue
                css = ';'.join(value for value in (style_css(props.get('style', {})), pagination_css(props.get('pagination', {}))) if value)
                attr = (' style="' + css + '"') if css else ''
                if node['type'] == 'text':
                    value = props['text'] if 'text' in props else resolve(props['binding'])
                    tag = {'title': 'h1', 'subtitle': 'h2', 'body': 'p'}[props.get('level', 'body')]
                    parts.append(f'<{tag}{attr}>{value_html(value, props.get("format"), node["id"])}</{tag}>')
                elif node['type'] == 'image':
                    parts.append('<figure class="report-image"'+attr+'><img src="'+escape(props['source'], quote=True)+'" alt="'+escape(props.get('alt', ''), quote=True)+'" style="'+image_css(props)+'"></figure>')
                elif node['type'] == 'page_break':
                    parts.append('<div class="page-break"></div>')
                elif node['type'] == 'divider':
                    parts.append('<hr'+attr+'>')
                elif node['type'] == 'section':
                    columns = props.get('columns', 1)
                    if columns > 1:
                        grid_css = f'display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:{props.get("gap", 8)}pt;'
                        section_attr = ' class="report-columns" style="' + grid_css + css + '"'
                    else:
                        section_attr = attr
                    parts.append('<section'+section_attr+'>' + render_nodes(node.get('children', [])) + '</section>')
                else:
                    items = resolve(props['collection'])
                    if type(items) is not list or len(items) > 2000:
                        raise ReportError('reports.error.collection', node['id'])
                    columns = props['columns']
                    def column_attr(column):
                        values = []
                        if 'width' in column: values.append('width:'+str(column['width'])+'%')
                        if 'align' in column: values.append('text-align:'+column['align'])
                        return (' style="'+';'.join(values)+'"') if values else ''
                    header = ''.join('<th'+column_attr(c)+'>' + escape(c['label']) + '</th>' for c in columns)
                    rows = ''.join('<tr>' + ''.join('<td'+column_attr(c)+'>' + value_html(resolve(c['binding'], item, True), c.get('format'), node['id']) + '</td>' for c in columns) + '</tr>' for item in items)
                    if not items:
                        rows = f'<tr><td colspan="{len(columns)}">{escape(props.get("empty_text", ""))}</td></tr>'
                    footer = ''
                    if any('aggregate' in c for c in columns):
                        cells = []
                        for c in columns:
                            value = ''
                            if 'aggregate' in c:
                                values = [resolve(c['binding'], item, True) for item in items]
                                try:
                                    result = aggregate(values, c['aggregate'])
                                except ValueError as exc:
                                    raise ReportError('reports.error.aggregate', node['id']) from exc
                                # Contagem é sempre inteiro, independente do formato das células.
                                spec = {'kind':'number','decimals':0} if c['aggregate']=='count' else c.get('format', {'kind':'number'})
                                value = value_html(result, spec, node['id'])
                            cells.append('<td'+column_attr(c)+'>'+value+'</td>')
                        footer = '<tfoot><tr>'+''.join(cells)+'</tr></tfoot>'
                    parts.append('<table'+attr+'><thead><tr>' + header + '</tr></thead><tbody>' + rows + '</tbody>'+footer+'</table>')
            return ''.join(parts)
        body = render_nodes(layout['body'])
        page_rule, screen_page = page_css(page_config(layout.get('page')))
        style = page_rule + """
* { box-sizing: border-box; }
body { margin:0; background:white; color:#182230; font:10pt sans-serif; }
.report-document { width:100%; }
.report-image { margin:0; break-inside:avoid; }
.report-image img { vertical-align:middle; }
.report-columns > * { min-width:0; overflow-wrap:anywhere; }
table { width:100%; border-collapse:collapse; table-layout:fixed; }
th,td { padding:var(--report-cell-padding,6pt); border:1px solid #cbd5e1; overflow-wrap:anywhere; }
th { background:#eef2f6; }
thead { display:table-header-group; }
tfoot { display:table-row-group; font-weight:bold; }
tr { break-inside:avoid; }
p { white-space:pre-wrap; overflow-wrap:anywhere; orphans:3; widows:3; }
h1,h2 { break-after:avoid; overflow-wrap:anywhere; }
.page-break { break-before:page; }
@media screen {
  body { padding:16px; background:#eef2f6; }
  .report-document { SCREEN_PAGE_SETTINGS margin:auto; background:white; }
  html[data-theme="dark"] body { background:#192435; color:#e8eef7; }
  html[data-theme="dark"] .report-document { background:#273549; }
  html[data-theme="dark"] th { background:#34445a; }
  html[data-theme="dark"] th, html[data-theme="dark"] td { border-color:#64748b; }
  .page-break { border-top:1px dashed #64748b; margin:20px 0; }
  @media (max-width:600px) { .report-document { padding:16px; } .report-columns { display:block !important; } }
}
@media print {
  body, .report-document { background:white !important; color:#182230 !important; }
  .report-document { padding:0; margin:0; max-width:none; min-height:0; }
  th { background:#eef2f6 !important; }
  th,td { border-color:#cbd5e1 !important; }
  .page-break { border:0; margin:0; }
}
"""
        style = style.replace('SCREEN_PAGE_SETTINGS', screen_page)
        document = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; img-src data:">'
                '<title>Relatório</title><style>' + style + '</style></head><body>'
                '<main class="report-document">' + body + '</main></body></html>')
        if len(document.encode('utf-8')) > 2 * 1024 * 1024:
            raise ReportError('reports.error.size', status=413)
        return document


def default_document():
    return {'schema_version': 1, 'body': [{'id': 'title', 'type': 'text', 'props': {'text': 'Relatório', 'level': 'title'}}]}
