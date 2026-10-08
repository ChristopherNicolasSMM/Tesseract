"""Organizações Core: componentes administrativos compartilhados, sem CRUD genérico."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required
from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from model.core.organization import Organization, PROFILE_FIELDS
from services.core.organization_service import save_organization, save_organization_contact

admin_organizations_bp = Blueprint('admin_organizations', __name__, url_prefix='/admin/organizations')
HEADERS = ['code', 'name', 'legal_name', 'cnpj', 'cidade', 'estado', 'is_active']


def filtered(search):
    query = Organization.query.order_by(Organization.name, Organization.id)
    if search:
        pattern = f'%{search}%'
        query = query.filter(db.or_(*(getattr(Organization, field).ilike(pattern) for field in ('code', 'name', 'legal_name', 'cnpj'))))
    return query


def render_list(*, submitted=None, error=None, status=200):
    search = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    items, total, pages = paginate(filtered(search), page)
    return render_template('core/admin/organizations_manage.html', items=items, search=search,
                           page=page, total=total, pages=pages, submitted=submitted, form_error=error), status


def render_detail(obj, *, submitted=None, error=None, status=200, contact_id=None, contact_data=None):
    data = obj.to_dict()
    if submitted:
        data.update({field: value for field, value in submitted.items() if field != 'code'})
    if contact_data is not None and contact_id is not None:
        data['contacts'] = [contact | contact_data if contact['id'] == contact_id else contact for contact in data['contacts']]
    return render_template('core/admin/organizations_detail.html', item=data, form_error=error,
                           contact_id=contact_id, contact_data=contact_data), status


@admin_organizations_bp.get('/')
@login_required
@permission_required('admin')
def manage():
    return render_list()


@admin_organizations_bp.get('/<int:ident>')
@login_required
@permission_required('admin')
def detail(ident):
    obj = db.session.get(Organization, ident)
    if obj is None:
        abort(404)
    return render_detail(obj)


@admin_organizations_bp.post('/')
@admin_organizations_bp.post('/<int:ident>')
@login_required
@permission_required('admin')
def save(ident=None):
    # Fields omitted by partial/legacy forms must not erase persisted values.
    data = {field: request.form[field] for field in ('name', 'code', *PROFILE_FIELDS) if field in request.form}
    if 'is_active' in request.form or '_active_present' in request.form:
        data['is_active'] = request.form.get('is_active') in {'on', 'true', '1'}
    result = save_organization(data, ident)
    if not result.success:
        if ident is None:
            return render_list(submitted=data, error=result.error, status=result.code)
        obj = db.session.get(Organization, ident)
        if obj is None:
            abort(404)
        return render_detail(obj, submitted=data, error=result.error, status=result.code)
    flash('Organização salva.', 'success')
    return redirect(url_for('admin_organizations.detail', ident=result.data['id']))


@admin_organizations_bp.get('/export.<kind>')
@login_required
@permission_required('admin')
def export(kind):
    if kind not in {'csv', 'xlsx'}:
        abort(404)
    rows = [[getattr(item, field) for field in HEADERS] for item in filtered((request.args.get('q') or '').strip()).all()]
    if kind == 'csv':
        return export_csv_response(HEADERS, rows, 'organizacoes')
    return export_xlsx_response(HEADERS, rows, 'organizacoes', 'Organizações')


@admin_organizations_bp.post('/<int:organization_id>/contacts')
@admin_organizations_bp.post('/<int:organization_id>/contacts/<int:ident>')
@login_required
@permission_required('admin')
def contact(organization_id, ident=None):
    data = {field: request.form[field] for field in ('name', 'role', 'cpf', 'email', 'phone') if field in request.form}
    if 'is_active' in request.form or '_active_present' in request.form:
        data['is_active'] = request.form.get('is_active') in {'on', 'true', '1'}
    result = save_organization_contact(organization_id, data, ident)
    if not result.success:
        obj = db.session.get(Organization, organization_id)
        if obj is None:
            abort(404)
        return render_detail(obj, error=result.error, status=result.code,
                             contact_id=ident, contact_data=data)
    flash('Responsável salvo.', 'success')
    return redirect(url_for('admin_organizations.detail', ident=organization_id))
