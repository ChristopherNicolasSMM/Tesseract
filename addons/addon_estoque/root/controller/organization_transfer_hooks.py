"""Transferência organizacional com as permissões existentes do estoque."""
from datetime import date
from flask import request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from core.permissions import permission_required
from services.core.organization_service import list_organizations, resolve_organization_by_code
from addons.addon_estoque.root.services.organization_transfer_service import FIELDS
from addons.addon_estoque.root.services.financial_stock_contract import stock_valuation_options
from addons.addon_estoque.root.services import estoque_service
from addons.addon_estoque.root.model.material import Material
from .organization_stock_hooks import _optional_id


@login_required
@permission_required('movimentacaos.create')
@permission_required('saldos.list')
def organization_transfer_view():
    values = request.args.to_dict() if request.method == 'GET' else (request.get_json(silent=True) if request.is_json else request.form.to_dict())
    status, error = 200, None
    if request.method == 'POST':
        try:
            if not isinstance(values, dict) or set(values) - FIELDS - ({'csrf_token'} if not request.is_json else set()) or FIELDS - set(values):
                raise ValueError('Dados da transferência inválidos.')
            data = {key: values[key] for key in FIELDS}
            for key in ('material_id', 'source_policy_version_id', 'destination_policy_version_id', 'rate_id'):
                data[key] = _optional_id(data[key])
            result = estoque_service.transferir_entre_organizacoes(data, actor=current_user.username)
            if request.is_json:
                return jsonify(success=True, data=result), 200 if result['replayed'] else 201
            flash('Transferência registrada: saída e entrada confirmadas juntas.', 'success')
            return redirect(url_for('saldos.organization_stock', organization_code=data['destination_organization']))
        except ValueError as exc:
            if request.is_json:
                return jsonify(success=False, error=str(exc)), 422
            status, error = 422, str(exc)
    if not isinstance(values, dict):
        values = {}
    options = {}
    for side in ('source', 'destination'):
        code = values.get(side + '_organization')
        try:
            if code:
                code = resolve_organization_by_code(code)['code']
                values[side + '_organization'] = code
            options[side] = stock_valuation_options(code)
        except ValueError as exc:
            status, error = 422, error or str(exc)
            options[side] = stock_valuation_options()
    organizations = [{'code': org.code, 'name': org.name} for org in list_organizations() if org.is_active]
    return render_template('organization_stock/transfer.html', values=values, options=options,
        organizations=organizations, error=error, today=date.today().isoformat(),
        materials=Material.query.filter_by(is_deleted=False, ativo=True).order_by(Material.nome).all()), status
