"""Adaptadores HTTP; toda autorização de negócio permanece no serviço."""
import secrets
from functools import wraps
from flask import Blueprint, jsonify, request, session, Response
from flask_login import current_user
from werkzeug.exceptions import RequestEntityTooLarge
from services.core.i18n_service import translate
from ...services import report_template_service as svc
from ...services.report_layout_service import ReportError
from ...services.report_pdf_service import render_pdf

reports_api_bp = Blueprint('reports_api', __name__, url_prefix='/api/reports')


def api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            if not current_user.is_authenticated:
                raise ReportError('reports.error.auth', status=401)
            if request.method != 'GET':
                request.max_content_length = 1024 * 1024
                supplied, expected = request.headers.get('X-Reports-CSRF', ''), session.get('reports_csrf', '')
                if not expected or not secrets.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
                    raise ReportError('reports.error.csrf', status=403)
                if request.content_length and request.content_length > 1024 * 1024:
                    raise ReportError('reports.error.size', status=413)
            return view(*args, **kwargs)
        except RequestEntityTooLarge:
            return jsonify(success=False, error={'code': 'reports.error.size', 'path': '', 'message': translate('reports.error.size')}), 413
        except ReportError as exc:
            return jsonify(success=False, error={'code': exc.code, 'path': exc.path, 'message': translate(exc.code)}), exc.status
    return wrapped


def payload(allowed):
    value = request.get_json(silent=True)
    if type(value) is not dict or set(value) - set(allowed):
        raise ReportError('reports.error.input', status=400)
    svc.guard_json(value)
    return value


@reports_api_bp.get('/session')
@api
def editing_session():
    token = session.setdefault('reports_csrf', secrets.token_urlsafe(32))
    return jsonify(success=True, csrf_token=token)


@reports_api_bp.route('/templates', methods=['GET', 'POST'])
@api
def collection():
    if request.method == 'GET':
        return jsonify(success=True, items=svc.list_templates())
    return jsonify(success=True, item=svc.create_template(payload(('key', 'name')))), 201


@reports_api_bp.get('/templates/<int:ident>/versions')
@api
def versions(ident):
    svc.authorize('detail')
    svc.get_template(ident)
    from ...model.report_template_version import ReportTemplateVersion
    items = ReportTemplateVersion.query.filter_by(template_id=ident).order_by(ReportTemplateVersion.version_number.desc()).all()
    return jsonify(success=True, items=[{'version': v.version_number, 'status': v.status} for v in items])


@reports_api_bp.route('/templates/<int:ident>/versions/<int:number>', methods=['GET', 'PUT'])
@api
def version(ident, number):
    value = svc.read_version(ident, number) if request.method == 'GET' else svc.save_version(ident, number, payload(('lock_version', 'layout', 'data_schema', 'sample_data', 'parameters')))
    return jsonify(success=True, item=value)


@reports_api_bp.post('/templates/<int:ident>/versions/<int:number>/clone')
@api
def clone(ident, number):
    payload(())
    return jsonify(success=True, item=svc.clone_version(ident, number)), 201


@reports_api_bp.post('/templates/<int:ident>/versions/<int:number>/publish')
@api
def publish(ident, number):
    data = payload(('lock_version', 'parameters'))
    return jsonify(success=True, item=svc.publish(ident, number, data.get('lock_version'), data.get('parameters', {})))


@reports_api_bp.post('/templates/<int:ident>/versions/<int:number>/preview')
@api
def preview(ident, number):
    data = payload(('parameters', 'format'))
    html = svc.preview(ident, number, data.get('parameters', {}))
    if data.get('format', 'html') == 'html':
        return jsonify(success=True, html=html)
    if data.get('format', 'html') != 'pdf':
        raise ReportError('reports.error.input')
    return pdf_response(render_pdf(html))


@reports_api_bp.post('/render')
@api
def render():
    data = payload(('template', 'version', 'data', 'parameters', 'format'))
    result = svc.generate_report(data.get('template'), version=data.get('version'), data=data.get('data', {}), parameters=data.get('parameters', {}), format=data.get('format', 'html'))
    return output_response(result, data.get('format', 'html'))


def output_response(result, format):
    if format == 'pdf':
        return pdf_response(result)
    return Response(result, mimetype='text/html', headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'",
    })


def pdf_response(pdf):
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'inline; filename="report.pdf"', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@reports_api_bp.get('/consumers/<consumer>/templates')
@api
def consumer_templates(consumer):
    from ...services.report_consumer_service import published_templates
    return jsonify(success=True, items=published_templates(consumer))


@reports_api_bp.post('/consumers/<consumer>/render')
@api
def consumer_render(consumer):
    from ...services.report_consumer_service import generate_consumer_report
    allowed = ('template', 'version', 'parameters', 'format', 'material_id') if consumer == 'stock' else ('template', 'version', 'parameters', 'format', 'session_id', 'plant_id')
    data = payload(allowed)
    return output_response(generate_consumer_report(consumer, data), data.get('format', 'html'))


@reports_api_bp.get('/examples/<name>')
@api
def example(name):
    import json
    from pathlib import Path
    svc.authorize('detail')
    if name not in ('estoque-saldos', 'brewstation-session'):
        raise ReportError('reports.error.not_found', status=404)
    example_path = Path(__file__).resolve().parents[3] / 'examples' / (name + '.json')
    return jsonify(success=True, item=json.loads(example_path.read_text(encoding='utf-8')))


@reports_api_bp.route('/blocks', methods=['GET', 'POST'])
@api
def blocks_collection():
    from ...services import report_block_service as blocks
    if request.method=='GET':
        return jsonify(success=True,items=blocks.list_blocks())
    return jsonify(success=True,item=blocks.create_block(payload(('key','name','template_id','version','node_id')))),201


@reports_api_bp.route('/blocks/<int:ident>', methods=['GET', 'DELETE'])
@api
def block_item(ident):
    from ...services import report_block_service as blocks
    if request.method=='GET':
        return jsonify(success=True,item=blocks.read_block(ident))
    return jsonify(success=True,item=blocks.archive_block(ident,payload(('lock_version',))))
