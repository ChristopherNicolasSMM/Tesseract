"""Área organizacional na cotação, entregue por extensão sem editar CRUD gerado."""
from flask import request, jsonify, render_template, abort
from flask_login import current_user, login_required
from core.permissions import permission_required
from services.core.organization_service import list_organizations
from addons.addon_estoque.root.services.purchase_context_service import document, get_context, bind_context


@login_required
@permission_required('processo_cotacaos.detail')
def quotation_organization_view(id):
    try:
        process = document('process', id)
    except ValueError:
        abort(404)
    if request.method == 'POST':
        if not current_user.has_permission('processo_cotacaos.update'):
            abort(403)
        result = bind_context('process', id, request.get_json(silent=True), actor=current_user.username)
        return jsonify(success=result.success, data=result.data, error=result.error), result.code
    context = get_context('process', id)
    organizations = [{'code': org.code, 'name': org.name} for org in list_organizations() if org.is_active]
    template = 'purchase_context/_quotation_organization.html'
    return jsonify(success=True, data=context.to_dict() if context else None,
        html=render_template(template, process=process, context=context, organizations=organizations, location='header'),
        modal_html=render_template(template, process=process, context=context, organizations=organizations, location='modal'))
