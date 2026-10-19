"""DRE integrada ao workspace, sem inferência de competência no legado."""
from uuid import uuid4
from flask import Blueprint,request,render_template,redirect,flash,g
from flask_login import login_required,current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from ..services import accrual_service as s,result_closing_service as closing_service,result_dashboard_service as dashboard_service
from .workspace import finance_url,link

results_bp=Blueprint('financial_results',__name__,url_prefix='/financeiro/resultados')


def panel(*,values=None,error=None,status=200,preview=None):
    values=values if values is not None else request.form.to_dict()
    code=request.args.get('organization_code','');view=request.args.get('view') or getattr(g,'finance_context',{}).get('view','dre')
    if getattr(g,'finance_context',None):g.finance_context.update(tab='results',view=view)
    data=None;review=None;costs=None;conference=None;closings=[];entries=[];classifications=[];categories=[];centers=[];total=0;pages=0
    page=max(1,min(request.args.get('page',1,type=int),1000000))
    if code:
        try:
            if view=='dashboard':
                data=dashboard_service.dashboard({k:request.args[k] for k in ('organization_code','date_from','date_to')})
            if view=='costs':costs=s.cost_review(code)
            if view=='closing':
                month=request.args.get('period',request.args['date_to'][:7])
                conference=closing_service.conference(code,month)
                closed_rows,closed_total,closed_pages=paginate(closing_service.Close.query.filter_by(organization_code=code).order_by(closing_service.Close.period.desc(),closing_service.Close.version.desc()),page)
                closings=[closing_service.close_detail(row) for row in closed_rows]
            if view=='dre':
                options={k:request.args[k] for k in ('organization_code','date_from','date_to')}
                if request.args.get('cost_center_id'):options['cost_center_id']=int(request.args['cost_center_id'])
                if request.args.get('group_code'):options['group_code']=request.args['group_code']
                data=s.statement(options)
            if view=='review':review=s.review(code)
            categories=s.f.bounded(s.t.Category.query.filter_by(organization_code=code).order_by(s.t.Category.name),2000)
            centers=s.f.bounded(s.t.Center.query.filter_by(organization_code=code).order_by(s.t.Center.name),2000)
            classifications=s.f.bounded(s.Classification.query.filter_by(organization_code=code).order_by(s.Classification.category_id,s.Classification.version.desc()),2000)
            query=s.Entry.query.filter_by(organization_code=code)
            if view=='entries' and request.args.get('entry_id'):query=query.filter(s.Entry.id==s.t.ident(int(request.args['entry_id'])))
            rows,total,pages=paginate(query.order_by(s.Entry.id.desc()),page)
            entries=[s.entry_detail(row) for row in rows]
            if view=='closing':total,pages=closed_total,closed_pages
        except ValueError as exc:error,status=str(exc),422
    if not values and request.args.get('source_type'):
        values={k:request.args[k] for k in ('source_type','source_id','component','reference','amount','currency_code','classification_id') if k in request.args}
    latest={}
    for classification in classifications:
        if classification.category_id not in latest:latest[classification.category_id]=classification.version
    allocation_rows=list(zip(request.form.getlist('allocation_period'),request.form.getlist('allocation_amount'),request.form.getlist('allocation_center')))[:120]
    if not allocation_rows:allocation_rows=[('','','')]
    return render_template('financeiro/results.html',data=data,review=review,costs=costs,conference=conference,closings=closings,values=values,error=error,preview=preview,
        result_view=view,allocation_rows=allocation_rows,groups=s.GROUPS,classifications=classifications,categories=categories,centers=centers,entries=entries,latest=latest,
        new_key=uuid4().hex,page=page,pages=pages,total=total),status


@results_bp.get('/',endpoint='list')
@login_required
@permission_required('financial_results.list')
def results():return panel()


def form():
    values=request.form.to_dict();values.pop('csrf_token',None)
    for key in ('source_id','classification_id','policy_version_id','category_id','expected_version'):
        if key in values:
            if values[key]=='':values[key]=None
            elif values[key].isascii() and values[key].isdigit():values[key]=int(values[key])
    if values.get('component')=='':values['component']=None
    return values


@results_bp.post('/classificar')
@login_required
@permission_required('admin')
def classify():
    values=form()
    if isinstance(values.get('valid_from'),str) and len(values['valid_from'])==7:values['valid_from']+='-01'
    result=s.classify(values,actor=current_user.username)
    if not result.success:return panel(error=result.error,status=result.code)
    flash('Nova classificação registrada; reconhecimentos anteriores preservados.','success')
    return redirect(link('results','classifications',organization_code=result.data['organization_code']))


@results_bp.post('/apropriar')
@login_required
@permission_required('admin')
def recognize():
    try:
        values=form();action=values.pop('action','preview')
        if action not in ('preview','confirm'):raise ValueError('Ação inválida.')
        periods=request.form.getlist('allocation_period');amounts=request.form.getlist('allocation_amount');centers=request.form.getlist('allocation_center')
        for key in ('allocation_period','allocation_amount','allocation_center'):values.pop(key,None)
        if not len(periods)==len(amounts)==len(centers):raise ValueError('Apropriações incompletas.')
        values['allocations']=[{'period':period,'amount':amount,'cost_center_id':int(center) if center.isascii() and center.isdigit() else center} for period,amount,center in zip(periods,amounts,centers)]
    except ValueError as exc:return panel(error=str(exc),status=422)
    result=(s.preview if action=='preview' else s.recognize)(values,actor=current_user.username)
    if not result.success:return panel(error=result.error,status=result.code)
    if action=='preview':return panel(preview=result.data)
    flash('Reconhecimento registrado sem movimentar caixa ou estoque.','success')
    return redirect(link('results','entries',organization_code=result.data['organization_code']))


@results_bp.post('/<int:row_id>/estornar')
@login_required
@permission_required('admin')
def reverse(row_id):
    result=s.reverse(row_id,form(),actor=current_user.username)
    if not result.success:return panel(error=result.error,status=result.code)
    flash('Reconhecimento estornado; competência original reapresentada e histórico preservado.','success')
    return redirect(link('results','entries',organization_code=result.data['organization_code']))


@results_bp.get('/revisao',endpoint='review')
@login_required
@permission_required('financial_results.list')
def review():return panel()


@results_bp.get('/classificacoes',endpoint='classifications')
@login_required
@permission_required('financial_results.list')
def classifications():return panel()


@results_bp.get('/apropriacoes',endpoint='entries')
@login_required
@permission_required('financial_results.list')
def entries():return panel()


@results_bp.get('/dashboard',endpoint='dashboard')
@login_required
@permission_required('financial_results.list')
def dashboard():return panel()


@results_bp.get('/custos',endpoint='costs')
@login_required
@permission_required('financial_results.list')
def costs():return panel()


@results_bp.get('/fechamento',endpoint='closing')
@login_required
@permission_required('financial_results.list')
def closing():return panel()


@results_bp.post('/fechar')
@login_required
@permission_required('admin')
def close():
    values=form()
    values['attestations']={key:values.pop(key,None)=='true' for key in closing_service.ATTESTATIONS}
    result=closing_service.close(values,actor=current_user.username)
    if not result.success:return panel(error=result.error,status=result.code)
    flash('Competência fechada com snapshot e cobertura declarada.','success')
    return redirect(link('results','closing',organization_code=result.data['organization_code'],period=result.data['period'][:7]))


@results_bp.post('/fechamentos/<int:row_id>/reabrir')
@login_required
@permission_required('admin')
def reopen(row_id):
    result=closing_service.reopen(row_id,form(),actor=current_user.username)
    if not result.success:return panel(error=result.error,status=result.code)
    flash('Competência reaberta; snapshot anterior preservado.','success')
    return redirect(link('results','closing',organization_code=result.data['organization_code']))
