"""Workspace padrão do Tesseract, com catálogo compartilhado autorizado."""
import secrets
from flask import Blueprint, render_template, session, current_app
from flask_login import current_user
from core.db import db
from core.permissions import permission_required
from ..services import report_template_service as svc

report_templates_bp = Blueprint('report_templates', __name__, url_prefix='/reports')


@report_templates_bp.app_context_processor
def consumer_context():
    from ..services.report_consumer_service import CONSUMERS
    with db.session.no_autoflush:
        visible = current_user.is_authenticated and current_user.has_permission('report_templates.render')
        permissions = {name: bool(visible and addon in current_app.module_manager.active_modules
                       and all(current_user.has_permission(p) for p in perms))
                       for name, (addon, _, perms) in CONSUMERS.items()}
    return {'reports_consumers': permissions}


@report_templates_bp.get('/', endpoint='list')
@permission_required('report_templates.list')
def workspace():
    token = session.setdefault('reports_csrf', secrets.token_urlsafe(32))
    return render_template('addon_reports/workspace.html', items=svc.list_templates(), csrf=token)
