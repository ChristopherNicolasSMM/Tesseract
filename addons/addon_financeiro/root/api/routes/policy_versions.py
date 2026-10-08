from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from addons.addon_financeiro.root.model.monetary import MonetaryPolicy
from addons.addon_financeiro.root.model.policy_version import MonetaryPolicyVersion
from addons.addon_financeiro.root.services.policy_version_service import create_policy_version

policy_versions_api_bp = Blueprint('finance_policy_versions_api', __name__, url_prefix='/api/financeiro/policy-versions')


@policy_versions_api_bp.route('', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def versions():
    if request.method == 'POST':
        result = create_policy_version(request.get_json(silent=True), actor=current_user.username)
        return jsonify(success=result.success, item=result.data, error=result.error), result.code
    query = MonetaryPolicyVersion.query.join(MonetaryPolicy).order_by(MonetaryPolicyVersion.id.desc())
    if request.args.get('organization_code'):
        query = query.filter(MonetaryPolicy.organization_code == request.args['organization_code'])
    page = max(1, request.args.get('page', 1, type=int))
    items, total, pages = paginate(query, page)
    return jsonify(success=True, items=[item.to_dict() for item in items], page=page, total=total, pages=pages)
