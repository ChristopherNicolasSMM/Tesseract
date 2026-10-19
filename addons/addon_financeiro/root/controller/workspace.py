"""Workspace server-rendered; reaproveita controllers e serviços operacionais."""
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, request, session, g, url_for, render_template, abort, current_app
from flask_login import login_required, current_user
from werkzeug.datastructures import ImmutableMultiDict
from services.core.organization_service import list_organizations, resolve_organization_by_code
from ..services import cash_flow_service as flow, workspace_service

workspace_bp=Blueprint('finance_workspace',__name__)
# (área, visão): endpoint existente e permissões de origem, conferidas também no destino.
VIEWS={
 ('overview','dashboard'):('finance_workspace.index',('financial_movements.list','financial_titles.list')),
 ('titles','list'):('financial_titles.list',('financial_titles.list',)),
 ('titles','detail'):('financial_titles.detail',('financial_titles.list',)),
 ('titles','settlements'):('financial_settlements.list',('financial_settlements.list',)),
 ('cash','accounts'):('financial_accounts.list',('financial_accounts.list',)),
 ('cash','flow'):('financial_cash_flow.list',('financial_movements.list','financial_titles.list')),
 ('cash','movements'):('financial_movements.history',('financial_movements.list',)),
 ('cash','transfers'):('financial_transfers.list',('financial_transfers.list',)),
 ('reconciliation','list'):('financial_reconciliations.list',('financial_reconciliations.list','financial_movements.list')),
 ('settings','categories'):('financial_categories.list',('financial_categories.list',)),
 ('settings','centers'):('financial_cost_centers.list',('financial_cost_centers.list',)),
 ('settings','currencies'):('currencies.list',('currencies.list',)),
 ('settings','policies'):('monetary_policies.list',('monetary_policies.list',)),
 ('settings','versions'):('policy_versions.list',('policy_versions.list',)),
 ('settings','rates'):('exchange_rates.list',('exchange_rates.list',)),
 ('settings','conversions'):('monetary_conversions.list',('monetary_conversions.list',)),
}
LABELS={'overview':'Visão geral','titles':'Títulos','cash':'Caixa e bancos','reconciliation':'Conciliação','settings':'Configurações'}
VIEW_LABELS={'list':'Títulos','detail':'Detalhe do título','settlements':'Pagamentos e recebimentos','accounts':'Contas',
 'flow':'Fluxo de caixa','movements':'Lançamentos','transfers':'Transferências','categories':'Categorias','centers':'Centros de custo',
 'currencies':'Moedas','policies':'Políticas','versions':'Versões monetárias','rates':'Taxas de câmbio','conversions':'Conversões'}
REVERSE={config[0]:key for key,config in VIEWS.items() if config[0]!='finance_workspace.index'}
REVERSE['financial_movements.list']=('cash','flow')
CONTEXT_KEYS=('organization_code','date_from','date_to')


def today_date(): return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def allowed(key): return all(current_user.has_permission(p) for p in VIEWS[key][1])


def link(tab=None,view=None,**extra):
    context=dict(getattr(g,'finance_context',{}))
    context.pop('title_id',None)
    if tab: context['tab']=tab
    if view: context['view']=view
    if context.get('tab') not in ('cash','reconciliation'): context.pop('account_id',None)
    context.update(extra)
    return url_for('finance_workspace.index',**{key:value for key,value in context.items() if value is not None and value!=''})


def page_link(page):
    values=request.args.to_dict(); values.pop('tab',None); values.pop('view',None); values['page']=page
    return link(**values)


def finance_url(endpoint,**values):
    if endpoint in REVERSE:
        tab,view=REVERSE[endpoint]
        if endpoint=='financial_titles.detail': values['title_id']=values.pop('row_id')
        return link(tab,view,**values)
    if endpoint=='finance_workspace.index': return link(**values)
    return url_for(endpoint,**values)


@workspace_bp.before_app_request
def prepare():
    if not current_user.is_authenticated or not request.endpoint: return
    if request.endpoint=='finance_workspace.index':
        tab=request.args.get('tab','overview'); view=request.args.get('view')
        if view is None: view=next((key[1] for key in VIEWS if key[0]==tab and key[1]!='detail' and allowed(key)),None) or next((key[1] for key in VIEWS if key[0]==tab),None)
        key=(tab,view)
        if key not in VIEWS: abort(404)
        # Entrada sem aba explícita abre a primeira área autorizada.
        if not request.args.get('tab') and not allowed(key):
            key=next((key for key in VIEWS if allowed(key)),None)
            if key is None: abort(403)
    elif request.endpoint in REVERSE: key=REVERSE[request.endpoint]
    elif request.path.startswith('/financeiro/') and request.blueprint not in ('report_emission',None):
        key=REVERSE.get(request.blueprint+'.list',('settings','currencies'))
    else: return
    if not allowed(key) and request.method=='GET': abort(403)
    saved=dict(session.get('finance_workspace',{}))
    today=today_date()
    context={'date_from':today.replace(day=1).isoformat(),'date_to':today.isoformat(),**saved}
    if 'organization_code' in request.args and request.args['organization_code']!=context.get('organization_code'):
        context.pop('account_id',None)
    for field in CONTEXT_KEYS+('account_id',):
        if field in request.args: context[field]=request.args[field]
    if request.method=='POST' and request.form.get('organization_code'): context['organization_code']=request.form['organization_code']
    if context.get('account_id')=='': context.pop('account_id',None)
    context.update(tab=key[0],view=key[1])
    if key[0] not in ('cash','reconciliation') or key[1]=='transfers': context.pop('account_id',None)
    merged=request.args.to_dict()
    for field in CONTEXT_KEYS+('account_id',):
        if field in context and field not in merged: merged[field]=context[field]
    request.args=ImmutableMultiDict(merged)
    g.finance_context=context
    if request.method=='GET':
        try:
            if context.get('organization_code'): resolve_organization_by_code(context['organization_code'],require_active=False)
            start,end=flow.day(context['date_from']),flow.day(context['date_to'])
            if end<start or (end-start).days>365: raise ValueError('Período inválido.')
            session['finance_workspace']={k:v for k,v in context.items() if k in CONTEXT_KEYS+('account_id',)}
        except ValueError: pass


@workspace_bp.app_url_defaults
def persist_context(endpoint,values):
    if not getattr(g,'finance_context',None): return
    if endpoint in REVERSE or endpoint.startswith(('financial_','finance_workspace.','currencies.','monetary_policies.','exchange_rates.','monetary_conversions.','policy_versions.','finance_setup.')) or endpoint=='report_emission.financeiro':
        for key in CONTEXT_KEYS:
            if key in g.finance_context: values.setdefault(key,g.finance_context[key])
        if endpoint.startswith(('financial_transfers.','financial_reconciliations.','financial_movements.')) and g.finance_context.get('account_id'):
            values.setdefault('account_id',g.finance_context['account_id'])


@workspace_bp.app_context_processor
def context():
    if not getattr(g,'finance_context',None): return {}
    ctx=g.finance_context
    tabs=[]; subviews=[]
    for tab,label in LABELS.items():
        permitted=[key for key in VIEWS if key[0]==tab and key[1]!='detail' and allowed(key)]
        if permitted: tabs.append({'key':tab,'label':label,'url':link(*permitted[0])})
        if tab==ctx['tab']:
            subviews=[{'key':key[1],'label':VIEW_LABELS.get(key[1],label),'url':link(*key)} for key in permitted if key[1]!='dashboard']
    orgs=list_organizations(); accounts=[]
    if ctx.get('organization_code') and ctx['tab'] in ('cash','reconciliation') and current_user.has_permission('financial_accounts.list'):
        from ..model.treasury import FinancialAccount
        accounts=FinancialAccount.query.filter_by(organization_code=ctx['organization_code']).order_by(FinancialAccount.name).all()
    screens={('overview','dashboard'):'financeiro-fluxo-caixa',('cash','flow'):'financeiro-fluxo-caixa',('titles','list'):'financeiro-titulos',('titles','settlements'):'financeiro-liquidacoes',('reconciliation','list'):'financeiro-conciliacao'}
    report=screens.get((ctx['tab'],ctx['view']))
    if 'reports' not in current_app.module_manager.active_modules or not current_user.has_permission('report_templates.render'): report=None
    return {'fw':ctx,'fw_tabs':tabs,'fw_views':subviews,'fw_organizations':orgs,'fw_accounts':accounts,
        'fw_url':link,'fw_page':page_link,'finance_url':finance_url,'fw_report':report}


@workspace_bp.get('/financeiro/',endpoint='index')
@login_required
def index():
    ctx=g.finance_context; key=(ctx['tab'],ctx['view'])
    if not allowed(key): abort(403)
    if key==('overview','dashboard'):
        data=None;error=None;status=200
        if ctx.get('organization_code'):
            try: data=workspace_service.dashboard({k:ctx[k] for k in CONTEXT_KEYS})
            except ValueError as exc:error,status=str(exc),422
        return render_template('financeiro/dashboard.html',data=data,error=error),status
    endpoint=VIEWS[key][0]
    if key==('titles','detail'):
        raw=request.args.get('title_id','')
        if not raw.isascii() or not raw.isdigit():abort(404)
        from ..services.treasury_service import title_detail
        try: item=title_detail(int(raw))
        except ValueError:abort(404)
        if ctx.get('organization_code') and item['organization_code']!=ctx['organization_code']:abort(404)
        return current_app.view_functions[endpoint](row_id=int(raw))
    return current_app.view_functions[endpoint]()
