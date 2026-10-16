"""Tela e JSON com prévia obrigatória, usando permissões de estoque."""
from datetime import date
from flask import request, render_template, jsonify
from flask_login import current_user, login_required
from core.permissions import permission_required
from core.db import db
from services.core.organization_service import list_organizations
from ..services.legacy_reconciliation_service import FIELDS
from ..services import estoque_service
from ..model.material import Material
from .organization_stock_hooks import _optional_id


@login_required
@permission_required('saldos.list')
@permission_required('movimentacaos.create')
def reconciliation_view():
    values, plan, result, error, status = {}, None, None, None, 200
    if request.method == 'POST':
        try:
            values = request.get_json(silent=True) if request.is_json else request.form.to_dict()
            if not isinstance(values, dict) or set(values) - FIELDS - {'action', 'preview_token', 'csrf_token'}:
                raise ValueError('Campos inválidos.')
            data = {field: values.get(field) for field in FIELDS}
            for field in ('material_id', 'rate_id', 'policy_version_id'):
                data[field] = _optional_id(data[field])
            if values.get('action') == 'preview':
                plan = estoque_service.previa_reconciliacao_legado(data)
            elif values.get('action') == 'confirm':
                result = estoque_service.reconciliar_legado(data, values.get('preview_token'), actor=current_user.username)
                status = 200 if result['replayed'] else 201
            else:
                raise ValueError('Selecione prévia ou confirmação.')
        except ValueError as exc:
            db.session.rollback(); error, status = str(exc), 422
        if request.is_json:
            return jsonify(success=error is None, preview=plan, data=result, error=error), status
    return render_template('organization_stock/reconciliation.html', values=values or {}, plan=plan,
        result=result, error=error, organizations=list_organizations(), today=date.today().isoformat(),
        materials=Material.query.filter_by(is_deleted=False, ativo=True).order_by(Material.nome).all()), status
