"""Extensões web/JSON de saldo e avaliação; usa permissões já existentes."""
from datetime import date
from flask import request, render_template, jsonify, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from core.permissions import permission_required
from core.db import db
from services.core.organization_service import list_organizations, resolve_organization_by_code
from addons.addon_estoque.root.services.financial_stock_contract import stock_valuation_options
from addons.addon_estoque.root.model.organization_stock import OrganizationBalance, OrganizationMovement, OrderValuation
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.services.purchase_context_service import document, get_context
from addons.addon_estoque.root.services.order_valuation_service import build_snapshot, prepare_valuation
from addons.addon_estoque.root.services import estoque_service


def _optional_id(value):
    if value is None or value == '':
        return None
    if request.is_json:
        if type(value) is not int or not 1 <= value <= 2147483647:
            raise ValueError('Identificador deve ser inteiro positivo ou null.')
        return value
    if not isinstance(value,str) or not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 2147483647:
        raise ValueError('Identificador inválido.')
    return int(value)


@login_required
@permission_required('saldos.list')
def organization_stock_view(*, selected_code=None, form_values=None, response_status=200):
    code=selected_code if selected_code is not None else request.args.get('organization_code')
    try:
        page=int(request.args.get('page','1'))
        if not 1 <= page <= 1000000:
            raise ValueError('Página inválida.')
        resolved=resolve_organization_by_code(code,require_active=False) if code else None
        org={key:resolved[key] for key in ('code','name','is_active')} if resolved else None
    except ValueError as exc:
        return jsonify(success=False,error=str(exc)),422
    balances=[]; movements=[]; has_next=False
    if org:
        balances=OrganizationBalance.query.filter_by(organization_code=org['code']).order_by(OrganizationBalance.material_id).limit(50).offset((page-1)*50).all()
        movements=OrganizationMovement.query.filter_by(organization_code=org['code']).order_by(OrganizationMovement.id.desc()).limit(51).offset((page-1)*50).all()
        has_next=len(movements)>50 or OrganizationBalance.query.filter_by(organization_code=org['code']).count()>page*50
        movements=movements[:50]
    if request.is_json:
        return jsonify(success=True,organization=org,balances=[row.to_dict() for row in balances],
                       movements=[row.to_dict() for row in movements],page=page,has_next=has_next)
    ids={row.material_id for row in balances+movements}
    identities={row.id:{'name':row.nome,'unit':row.unidade_medida} for row in Material.query.filter(Material.id.in_(ids)).all()} if ids else {}
    return render_template('organization_stock/manage.html',organizations=list_organizations(),selected=org,
        balances=[row.to_dict() for row in balances],movements=[row.to_dict() for row in movements],page=page,has_next=has_next,
        identities=identities,materials=Material.query.filter_by(is_deleted=False,ativo=True).order_by(Material.nome).all(),
        options=stock_valuation_options(org['code'] if org else None),values=form_values or {},today=date.today().isoformat()),response_status


@login_required
@permission_required('movimentacaos.create')
def organization_movement_view():
    try:
        data=request.get_json(silent=True) if request.is_json else request.form.to_dict()
        required={'organization_code','material_id','tipo_movimentacao','quantidade','custo_unitario','source_currency',
                  'operation_date','rate_id','policy_version_id','idempotency_key','observacoes'}
        if not isinstance(data,dict) or set(data)-required-({'csrf_token'} if not request.is_json else set()):
            raise ValueError('Campos inválidos.')
        if not request.is_json:
            data={key:value for key,value in data.items() if key != 'csrf_token'}
        data={'custo_unitario':None,'source_currency':None,'rate_id':None,'policy_version_id':None,'observacoes':None}|data
        data['material_id']=_optional_id(data.get('material_id'))
        for field in ('rate_id','policy_version_id'):
            data[field]=_optional_id(data[field])
        if not request.is_json:
            for field in ('custo_unitario','source_currency','observacoes'):
                data[field]=data.get(field) or None
        if data.get('tipo_movimentacao')=='saida' or (data.get('tipo_movimentacao')=='ajuste' and str(data.get('quantidade','')).startswith('-')):
            # O formulário apresenta as opções de entrada; usuário sai sem custo externo.
            if not request.is_json:
                data['custo_unitario']=data['source_currency']=data['rate_id']=None
        result=estoque_service.registrar_movimentacao(data.get('material_id'),data.get('tipo_movimentacao'),data.get('quantidade'),
            organization_code=data.get('organization_code'),custo_unitario=data['custo_unitario'],source_currency=data['source_currency'],
            operation_date=data.get('operation_date'),rate_id=data['rate_id'],policy_version_id=data['policy_version_id'],
            idempotency_key=data.get('idempotency_key'),observacoes=data['observacoes'],actor=current_user.username)
        if request.is_json:
            return jsonify(success=True,**result),200 if result.get('replayed') else 201
        flash('Movimentação organizacional registrada.','success')
        return redirect(url_for('saldos.organization_stock',organization_code=data['organization_code']))
    except ValueError as exc:
        db.session.rollback()
        if request.is_json:
            return jsonify(success=False,error=str(exc)),422
        flash(str(exc),'error')
        return organization_stock_view(selected_code=request.form.get('organization_code'),
                                       form_values=request.form.to_dict(),response_status=422)


@login_required
@permission_required('pedido_compras.update')
def order_valuation_view(id):
    try:
        order=document('order',id)
        context=get_context('order',id)
        if context is None:
            raise ValueError('Pedido exige vínculo organizacional explícito.')
    except ValueError as exc:
        return jsonify(success=False,error=str(exc)),422
    plan=OrderValuation.query.filter_by(order_id=id).first()
    preview=None;status=200;values={}
    if request.method=='POST':
        try:
            payload=request.get_json(silent=True) if request.is_json else request.form.to_dict()
            allowed={'action','source_currency','operation_date','rate_id','policy_version_id'}
            if not isinstance(payload,dict) or set(payload)-allowed-({'csrf_token'} if not request.is_json else set()):
                raise ValueError('Campos de avaliação inválidos.')
            action=payload.get('action')
            data={key:payload.get(key) for key in ('source_currency','operation_date','rate_id','policy_version_id')}
            data['rate_id']=_optional_id(data['rate_id']);data['policy_version_id']=_optional_id(data['policy_version_id'])
            values=data
            if action=='preview':
                preview=build_snapshot(id,data)
                if request.is_json:
                    return jsonify(success=True,data=preview)
            elif action=='confirm':
                result=prepare_valuation(id,data,actor=current_user.username)
                if request.is_json:
                    return jsonify(success=result.success,data=result.data,error=result.error),result.code
                flash('Avaliação congelada. Use a Entrada de Mercadoria do pedido para receber.' if result.success else result.error,
                      'success' if result.success else 'error')
                if result.success:
                    return redirect(request.path)
                status=result.code
            else:
                raise ValueError('Ação deve ser preview ou confirm.')
        except ValueError as exc:
            db.session.rollback()
            if request.is_json:
                return jsonify(success=False,error=str(exc)),422
            flash(str(exc),'error');status=422
    if request.is_json:
        return jsonify(success=True,data=plan.to_dict() if plan else None)
    return render_template('organization_stock/valuation.html',item=order,context=context,plan=plan.to_dict() if plan else None,
                           preview=preview,values=values,options=stock_valuation_options(context.organization_code),today=date.today().isoformat()),status
