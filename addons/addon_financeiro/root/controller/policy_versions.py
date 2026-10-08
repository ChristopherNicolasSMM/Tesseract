"""Cadastro manual de revisões e descoberta padrão de menu/permissão."""
from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from services.core.organization_service import list_organizations
from addons.addon_financeiro.root.model.monetary import MonetaryPolicy
from addons.addon_financeiro.root.model.policy_version import MonetaryPolicyVersion
from addons.addon_financeiro.root.services.policy_version_service import create_policy_version

policy_versions_bp = Blueprint('policy_versions', __name__, url_prefix='/financeiro/policy-versions')


def render_panel(*, submitted=None, error=None, status=200):
    search = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    query = MonetaryPolicyVersion.query.join(MonetaryPolicy).order_by(MonetaryPolicyVersion.id.desc())
    if search:
        query = query.filter(MonetaryPolicy.organization_code.ilike(f'%{search}%') |
                             MonetaryPolicyVersion.reason.ilike(f'%{search}%'))
    items, total, pages = paginate(query, page)
    latest = {}
    for version in MonetaryPolicyVersion.query.order_by(MonetaryPolicyVersion.version_number).all():
        latest[version.policy_id] = version
    choices = []
    active_codes = {item.code for item in list_organizations() if item.is_active}
    for policy in MonetaryPolicy.query.order_by(MonetaryPolicy.organization_code).all():
        if policy.organization_code not in active_codes:
            continue
        version = latest.get(policy.id)
        choices.append(policy.to_dict() | {
            'last_version': version.version_number if version else 1,
            'last_scale': version.decimal_places if version else policy.decimal_places,
            'last_rounding': version.rounding if version else policy.rounding})
    return render_template('financeiro/policy_versions.html', items=[item.to_dict() for item in items],
                           policies=choices, submitted=submitted or {}, form_error=error,
                           search=search, page=page, total=total, pages=pages), status


@policy_versions_bp.get('/', endpoint='list')
@login_required
@permission_required('policy_versions.list')
def list_versions():
    return render_panel()


@policy_versions_bp.post('/')
@login_required
@permission_required('admin')
def create():
    submitted = request.form.to_dict()
    data = dict(submitted)
    for field in ('expected_version', 'decimal_places'):
        try:
            data[field] = int(data.get(field, ''))
        except ValueError:
            data[field] = None
    result = create_policy_version(data, actor=current_user.username)
    if not result.success:
        return render_panel(submitted=submitted, error=result.error, status=result.code)
    flash('Versão cadastrada. Selecione-a explicitamente nas novas conversões.', 'success')
    return redirect(url_for('policy_versions.list'))
