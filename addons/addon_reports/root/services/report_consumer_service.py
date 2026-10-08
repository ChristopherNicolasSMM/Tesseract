"""Adaptadores opcionais: somente contratos públicos JSON entre addons."""
from flask import current_app
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from core.db import db
from ..model.report_template import ReportTemplate
from ..model.report_template_version import ReportTemplateVersion
from .report_layout_service import ReportError
from . import report_template_service as reports

CONSUMERS = {
    'stock': ('estoque', 'estoque.saldos.v1', ('saldos.list', 'materials.list')),
    'session': ('brewstation', 'brewstation.session.v1', ('brew_sessions.list', 'brew_plants.list', 'brew_session_steps.list')),
}


def authorize_consumer(consumer):
    with db.session.no_autoflush:
        reports.authorize('render')
        if consumer not in CONSUMERS:
            raise ReportError('reports.error.not_found', status=404)
        addon, _, permissions = CONSUMERS[consumer]
        if addon not in current_app.module_manager.active_modules:
            raise ReportError('reports.error.consumer_unavailable', status=503)
        if not all(current_user.has_permission(p) for p in permissions):
            raise ReportError('reports.error.forbidden', status=403)


def published_templates(consumer):
    """Catálogo de emissão: revisão ativa compatível, sem acesso a rascunhos."""
    authorize_consumer(consumer)
    contract = CONSUMERS[consumer][1]
    from ..model.report_parameter import ReportParameter
    with db.session.session_factory() as reader:
        rows = (reader.query(ReportTemplate, ReportTemplateVersion)
                .join(ReportTemplateVersion, (ReportTemplateVersion.template_id == ReportTemplate.id)
                      & (ReportTemplateVersion.version_number == ReportTemplate.active_version_number))
                .filter(ReportTemplate.is_deleted.is_(False), ReportTemplateVersion.status == 'published')
                .order_by(ReportTemplate.name).all())
        ids = [revision.id for _, revision in rows]
        definitions = {}
        for parameter in reader.query(ReportParameter).filter(ReportParameter.version_id.in_(ids)).order_by(ReportParameter.id).all():
            definitions.setdefault(parameter.version_id, []).append(parameter.to_dict())
        result = []
        for template, revision in rows:
            schema = revision.data_schema_json
            properties = schema.get('properties', {})
            field = properties.get('contract') if type(properties) is dict else None
            if type(field) is dict and field.get('const') == contract:
                result.append({'parameters':definitions.get(revision.id, []), 'key': template.key, 'name': template.name, 'version': revision.version_number})
        return result


def generate_consumer_report(consumer, payload):
    authorize_consumer(consumer)
    options = {'version': payload.get('version'), 'parameters': payload.get('parameters', {}), 'format': payload.get('format', 'html')}
    try:
        if consumer == 'stock':
            from addons.addon_estoque.root.services.report_data_service import generate_stock_report
            return generate_stock_report(payload.get('template'), material_id=payload.get('material_id'), **options)
        from addons.addon_brewstation.features.feature_mash_control.services.report_data_service import generate_session_report
        return generate_session_report(payload.get('template'), payload.get('session_id'), plant_id=payload.get('plant_id'), **options)
    except HTTPException as exc:
        code = {400: 'input', 401: 'auth', 403: 'forbidden', 404: 'not_found', 413: 'size'}.get(exc.code, 'input')
        raise ReportError('reports.error.' + code, status=exc.code or 400) from exc
