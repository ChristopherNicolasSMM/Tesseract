"""API administrativa manual; identidade compartilhada sem exclusão."""
from flask import Blueprint, jsonify, request
from flask_login import login_required
from core.permissions import permission_required
from services.core.organization_service import list_organizations, resolve_organization, save_organization

organizations_api_bp = Blueprint('organizations_api', __name__, url_prefix='/api/admin/organizations')


@organizations_api_bp.route('/', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def collection():
    if request.method == 'GET':
        return jsonify(success=True, items=[obj.to_dict() for obj in list_organizations(request.args.get('q', ''))])
    result = save_organization(request.get_json(silent=True))
    return jsonify(success=result.success, item=result.data, error=result.error), result.code


@organizations_api_bp.route('/<int:ident>', methods=['GET', 'PUT'])
@login_required
@permission_required('admin')
def detail(ident):
    if request.method == 'GET':
        try:
            return jsonify(success=True, item=resolve_organization(ident, require_active=False))
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 404
    result = save_organization(request.get_json(silent=True), ident)
    return jsonify(success=result.success, item=result.data, error=result.error), result.code
