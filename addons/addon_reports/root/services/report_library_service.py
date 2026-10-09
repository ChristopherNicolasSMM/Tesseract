"""Modelos operacionais e projeções somente de leitura de serviços existentes."""
import importlib
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from flask import current_app
from flask_login import current_user
from core.db import db
from werkzeug.exceptions import HTTPException
from services.core.i18n_service import translate
from . import report_template_service as reports
from .report_layout_service import ReportError

CATALOG = {
    'receita-completa': ('recipe', 'reports.library.recipe'),
    'sessao-detalhada': ('session', 'reports.library.session'),
    'estoque-atual': ('stock', 'reports.library.stock'),
    'banco-leveduras': ('yeast', 'reports.library.yeast'),
    'dashboard-geral': ('dashboard', 'reports.library.dashboard'),
    'disponibilidade-validade': ('expiry', 'reports.library.expiry'),
    'planejamento-starters': ('starters', 'reports.library.starters'),
    'checklist-receita': ('recipe', 'reports.library.checklist'),
}
PERMISSIONS = {
    'recipe': ('mash_recipes.list', 'recipe_ingredients.list', 'recipe_steps.list','fermentation_steps.list','water_profiles.list'),
    'session': ('brew_sessions.list', 'brew_plants.list', 'brew_session_steps.list','brew_session_logs.list','brew_session_alarms.list'),
    'stock': ('saldos.list', 'materials.list'),
    'yeast': ('yeast_bank_items.list', 'yeast_strains.list', 'yeast_containers.list'),
    'starters': ('yeast_bank_events.list', 'yeast_bank_items.list', 'yeast_strains.list', 'yeast_containers.list'),
}
PERMISSIONS['expiry'] = PERMISSIONS['yeast']
PERMISSIONS['dashboard'] = tuple(dict.fromkeys(PERMISSIONS['recipe'] + PERMISSIONS['session'] + PERMISSIONS['stock'] + PERMISSIONS['yeast'] + PERMISSIONS['starters']))
MASH = 'addons.addon_brewstation.features.feature_mash_control.services.'
YEAST = 'addons.addon_brewstation.features.feature_yeast_bank.services.'


def definition(name):
    if name not in CATALOG and name not in ('estoque-saldos', 'brewstation-session'):
        raise ReportError('reports.error.not_found', status=404)
    return json.loads((Path(__file__).resolve().parents[2] / 'examples' / (name+'.json')).read_text(encoding='utf-8'))


def authorize(name):
    reports.authorize('detail')
    if name not in CATALOG:
        raise ReportError('reports.error.not_found', status=404)
    source = CATALOG[name][0]
    addons = ('estoque',) if source=='stock' else ('brewstation','estoque') if source=='dashboard' else ('brewstation',)
    with db.session.no_autoflush:
        if not all(addon in current_app.module_manager.active_modules for addon in addons):
            raise ReportError('reports.error.consumer_unavailable', status=503)
        features=() if source=='stock' else ('feature_mash_control','feature_yeast_bank') if source=='dashboard' else ('feature_mash_control',) if source in ('recipe','session') else ('feature_yeast_bank',)
        if not all('brewstation/'+feature in current_app.module_manager.active_features for feature in features):
            raise ReportError('reports.error.consumer_unavailable',status=503)
        if not all(current_user.has_permission(p) for p in PERMISSIONS[source]):
            raise ReportError('reports.error.forbidden', status=403)
    return source


def service(prefix, module, cls):
    return getattr(importlib.import_module(prefix+module), cls)()


def records(prefix, module, cls):
    values = service(prefix,module,cls).list()
    if len(values)>2000:
        raise ReportError('reports.error.size', status=413)
    return values


def choices(name):
    source=authorize(name)
    with db.session.no_autoflush:
        if source=='recipe':
            values=records(MASH,'mash_recipe_service','MashRecipeService')
            return [{'value':{'recipe_id':v.id},'label':v.name} for v in values]
        if source=='session':
            values=records(MASH,'brew_session_service','BrewSessionService')
            return [{'value':{'session_id':v.id,'plant_id':v.plant_id},'label':v.name} for v in values]
    return []


def yeast_rows():
    values=records(YEAST,'yeast_bank_item_service','YeastBankItemService')
    rows=[]
    for item in values:
        value=item.to_dict()
        rows.append({k:value.get(k) for k in ('id','strain_id','storage_type','location','storage_slot','label_text','prepared_date','expiry_date','status','last_checked','estimated_viability_pct','estimated_viability_updated_at','viability_notes')} | {
            'strain_name':(value.get('strain') or {}).get('name'),
            'container_name':(value.get('container') or {}).get('name')})
    return rows


def starter_rows():
    values=records(YEAST,'yeast_bank_event_service','YeastBankEventService')
    rows=[]
    for event in values:
        if event.event_type!='Starter' or event.starter_status not in ('planned','active'):
            continue
        value=event.to_dict()
        if not value.get('bank_item') or value['bank_item'].get('is_deleted'):
            continue
        rows.append({k:value.get(k) for k in ('id','bank_item_id','starter_status','brew_date','start_date','target_volume_l','objective','notes')} | {
            'strain_name':(value['bank_item'].get('strain') or {}).get('name')})
    rows.sort(key=lambda v:(v['start_date'] is None,v['start_date'] or '',v['id']))
    return rows


def recipe_data(ident):
    value=service(MASH,'mash_recipe_service','MashRecipeService').get_by_id(ident)
    if not value or value.is_deleted:
        raise ReportError('reports.error.not_found',status=404)
    ingredients=[v.to_dict() for v in records(MASH,'recipe_ingredient_service','RecipeIngredientService') if v.recipe_id==ident]
    steps=[v.to_dict() for v in records(MASH,'recipe_step_service','RecipeStepService') if v.recipe_id==ident]
    steps.sort(key=lambda v:(v['ordem'],v['id']))
    fermentation=[v.to_dict() for v in records(MASH,'fermentation_step_service','FermentationStepService') if v.recipe_id==ident]
    fermentation.sort(key=lambda v:(v['ordem'],v['id']))
    water=[v.to_dict() for v in records(MASH,'water_profile_service','WaterProfileService') if v.recipe_id==ident]
    return {'recipe':value.to_dict(),'ingredients':ingredients,'steps':steps,'fermentation':fermentation,'water':water}


def data(name, options):
    source=authorize(name)
    allowed={'recipe_id'} if source=='recipe' else {'session_id','plant_id'} if source=='session' else {'days','reference_date'} if source=='expiry' else set()
    if set(options)-allowed:
        raise ReportError('reports.error.input')
    if source in ('recipe','session') and (set(options)!=allowed or any(type(v) is not int or v<1 for v in options.values())):
        raise ReportError('reports.error.input')
    days=options.get('days',30)
    if source=='expiry' and (type(days) is not int or not 0<=days<=365):
        raise ReportError('reports.error.input')
    try:
        with db.session.no_autoflush:
            if source=='recipe':result=recipe_data(options['recipe_id'])
            elif source=='session':
                from addons.addon_brewstation.features.feature_mash_control.services.report_data_service import build_session_report_data
                result=build_session_report_data(options['session_id'],plant_id=options['plant_id'])
                result['logs']=[v.to_dict() for v in records(MASH,'brew_session_log_service','BrewSessionLogService') if v.session_id==options['session_id']]
                result['alarms']=[v.to_dict() for v in records(MASH,'brew_session_alarm_service','BrewSessionAlarmService') if v.session_id==options['session_id']]
                result['contract']='reports.library.session.v1'
            elif source=='stock':
                from addons.addon_estoque.root.services.report_data_service import build_stock_report_data
                result=build_stock_report_data()
            elif source=='yeast':result={'items':yeast_rows()}
            elif source=='starters':result={'items':starter_rows()}
            elif source=='expiry':
                items=yeast_rows()
                try:
                    today=date.fromisoformat(options['reference_date']) if 'reference_date' in options else datetime.now(timezone.utc).date()
                    if 'reference_date' in options and today.isoformat()!=options['reference_date']:raise ValueError('date')
                except (ValueError,TypeError):raise ReportError('reports.error.input')
                limit=today+timedelta(days=days)
                available=[v for v in items if v['status']=='active']
                result={'reference_date':today.isoformat(),'until_date':limit.isoformat(),
                    'available':[v for v in available if v['expiry_date'] and date.fromisoformat(v['expiry_date'])>limit],
                    'expiring':[v for v in available if v['expiry_date'] and today<=date.fromisoformat(v['expiry_date'])<=limit],
                    'expired':[v for v in available if v['expiry_date'] and date.fromisoformat(v['expiry_date'])<today],
                    'undated':[v for v in available if not v['expiry_date']]}
            else:
                recipe=records(MASH,'mash_recipe_service','MashRecipeService');sessions=records(MASH,'brew_session_service','BrewSessionService')
                yeast=yeast_rows();starters=starter_rows()
                from addons.addon_estoque.root.services.report_data_service import build_stock_report_data
                stock=build_stock_report_data()['items']
                result={'indicators':[{'name':translate('reports.library.indicator_recipes'),'count':len(recipe)},
                    {'name':translate('reports.library.indicator_sessions'),'count':len(sessions)},{'name':translate('reports.library.indicator_yeast'),'count':len(yeast)},
                    {'name':translate('reports.library.indicator_starters'),'count':len(starters)},{'name':translate('reports.library.indicator_stock'),'count':len(stock)}],
                    'sessions':[{'name':v.name,'status':v.status,'plant_id':v.plant_id} for v in sessions],
                    'yeast':yeast,'starters':starters}
    except HTTPException as exc:
        raise ReportError('reports.error.input' if exc.code==400 else 'reports.error.not_found' if exc.code==404 else 'reports.error.forbidden',status=exc.code or 422) from exc
    if source not in ('session','stock'):
        result['contract']='reports.library.'+source+'.v1'
    result['generated_at']=datetime.now(timezone.utc).isoformat()
    reports.guard_json(result)
    return result
