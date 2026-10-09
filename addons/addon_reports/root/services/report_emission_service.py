"""Telas de emissão compartilham contratos, filtros e geração publicados."""
from datetime import date
from flask import current_app
from . import report_library_service as library
from . import report_template_service as reports
from .report_layout_service import ReportError

SCREENS = {
    'receitas': ('receita-completa', 'Receitas', 'bi-journal-text', 'brewstation', 'feature_mash_control'),
    'sessoes': ('sessao-detalhada', 'Sessões', 'bi-cup-straw', 'brewstation', 'feature_mash_control'),
    'banco-leveduras': ('banco-leveduras', 'Banco de leveduras', 'bi-archive', 'brewstation', 'feature_yeast_bank'),
    'disponibilidade-validade': ('disponibilidade-validade', 'Disponibilidade e validade', 'bi-calendar-event', 'brewstation', 'feature_yeast_bank'),
    'starters': ('planejamento-starters', 'Starters', 'bi-droplet', 'brewstation', 'feature_yeast_bank'),
    'dashboard': ('dashboard-geral', 'Dashboard', 'bi-bar-chart', 'brewstation', 'feature_mash_control'),
    'estoque': ('estoque-organizacional', 'Estoque atual', 'bi-box-seam', 'estoque', None),
}
FILTERS = {
    'receitas': (), 'sessoes': (),
    'banco-leveduras': ('status', 'strain_id', 'location'),
    'disponibilidade-validade': ('strain_id', 'location'),
    'starters': ('starter_status', 'strain_name', 'date_from', 'date_to'),
    'dashboard': ('search',), 'estoque': ('positive_only',),
}


def authorize(screen):
    if screen not in SCREENS:
        raise ReportError('reports.error.not_found', status=404)
    reports.authorize('render')
    library.authorize(SCREENS[screen][0],action='render')
    return SCREENS[screen]


def catalog_transactions():
    """Contribuição opcional nos grupos dos addons; IDE mantém descoberta padrão."""
    result = []
    for addon, parent in (('brewstation','TX_GROUP_BREWSTATION'),('estoque','TX_GROUP_ESTOQUE')):
        if addon not in current_app.module_manager.active_modules:
            continue
        group = 'TX_GROUP_REPORTS_' + addon.upper()
        result.append({'code':group,'label':'Relatórios','route':None,'parent_code':parent,'icon':'bi-file-earmark-text'})
        for name, (_,label,icon,owner,feature) in SCREENS.items():
            if owner != addon or (feature and owner+'/'+feature not in current_app.module_manager.active_features):
                continue
            if name=='dashboard' and ('estoque' not in current_app.module_manager.active_modules or 'brewstation/feature_yeast_bank' not in current_app.module_manager.active_features):
                continue
            result.append({'code':'TX_REPORT_EMIT_'+name.upper().replace('-','_'),'label':label,
                           'route':'/'+addon+'/reports/'+name,'parent_code':group,'icon':icon,
                           'permission_required':'report_templates.render'})
    return result


def templates(screen):
    config = authorize(screen)
    from .report_consumer_service import templates_for_contract
    contract = library.definition(config[0])['data_schema']['properties']['contract']['const']
    return templates_for_contract(contract)


def metadata(screen):
    config = authorize(screen)
    records = library.choices(config[0],action='render')
    options = {}
    if screen in ('banco-leveduras','disponibilidade-validade'):
        rows = library.yeast_rows()
        for field in ('status','strain_id','location'):
            options[field] = [{'value':value,'label':str(value)} for value in sorted({v[field] for v in rows if v.get(field) is not None},key=str)]
        names = {v['strain_id']:v['strain_name'] for v in rows}
        for option in options['strain_id']:
            option['label'] = names.get(option['value']) or str(option['value'])
    elif screen == 'starters':
        rows = library.starter_rows()
        for field in ('starter_status','strain_name'):
            options[field] = [{'value':v,'label':v} for v in sorted({row[field] for row in rows if row.get(field)})]
    return {'records':records,'filters':options,'templates':templates(screen)}


def filtered_data(screen, options, filters):
    config = authorize(screen)
    if type(options) is not dict or type(filters) is not dict or set(filters)-set(FILTERS[screen]):
        raise ReportError('reports.error.input')
    for key,value in filters.items():
        if key == 'positive_only':
            if type(value) is not bool:
                raise ReportError('reports.error.input')
        elif key == 'strain_id':
            if type(value) is not int or value < 1:
                raise ReportError('reports.error.input')
        elif type(value) is not str or not value or len(value)>120:
            raise ReportError('reports.error.input')
        if key in ('date_from','date_to'):
            try:
                if date.fromisoformat(value).isoformat()!=value:
                    raise ValueError()
            except ValueError:
                raise ReportError('reports.error.input')
    if filters.get('date_from','')>filters.get('date_to','9999-12-31'):
        raise ReportError('reports.error.input')
    value = library.data(config[0],options,action='render')
    if screen in ('banco-leveduras','disponibilidade-validade','starters'):
        fields = ('available','expiring','expired','undated') if screen=='disponibilidade-validade' else ('items',)
        for field in fields:
            rows = value[field]
            for key,expected in filters.items():
                if key=='date_from':
                    rows=[row for row in rows if row.get('start_date') and row['start_date'][:10]>=expected]
                elif key=='date_to':
                    rows=[row for row in rows if row.get('start_date') and row['start_date'][:10]<=expected]
                else:
                    rows=[row for row in rows if row.get(key)==expected]
            value[field]=rows
    elif screen=='estoque' and filters.get('positive_only'):
        from decimal import Decimal
        value['items']=[row for row in value['items'] if Decimal(row['quantidade_atual'])>0]
    elif screen=='dashboard' and filters.get('search'):
        search=filters['search'].casefold()
        for field in ('sessions','yeast','starters'):
            value[field]=[row for row in value[field] if any(search in str(row.get(key) or '').casefold() for key in ('name','strain_name','location'))]
    return value


def generate(screen, payload):
    if type(payload) is not dict:
        raise ReportError('reports.error.input')
    selected=next((v for v in templates(screen) if v['key']==payload.get('template') and v['version']==payload.get('version')),None)
    if selected is None:
        raise ReportError('reports.error.not_found', status=404)
    value=filtered_data(screen,payload.get('options',{}),payload.get('filters',{}))
    return reports.generate_report(selected['key'],version=selected['version'],data=value,
                                   parameters=payload.get('parameters',{}),format=payload.get('format','html'))
