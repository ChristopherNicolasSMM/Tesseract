"""Tela administrativa manual de identidade de organizações."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from core.permissions import permission_required
from services.core.organization_service import list_organizations, save_organization

admin_organizations_bp = Blueprint('admin_organizations', __name__, url_prefix='/admin/organizations')


@admin_organizations_bp.route('/', methods=['GET'])
@login_required
@permission_required('admin')
def manage():
    search = request.args.get('q', '')
    return render_template('core/admin/organizations_manage.html', items=list_organizations(search), search=search)


@admin_organizations_bp.route('/', methods=['POST'])
@admin_organizations_bp.route('/<int:ident>', methods=['POST'])
@login_required
@permission_required('admin')
def save(ident=None):
    data = {'name': request.form.get('name'), 'is_active': request.form.get('is_active') == 'on'}
    if ident is None:
        data['code'] = request.form.get('code')
    result = save_organization(data, ident)
    flash('Organização salva.' if result.success else result.error, 'success' if result.success else 'error')
    return redirect(url_for('admin_organizations.manage'))
