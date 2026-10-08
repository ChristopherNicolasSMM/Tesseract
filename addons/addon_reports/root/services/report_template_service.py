"""Contrato público de catálogo; chamadas internas também usam RBAC do Core."""
import copy
import hashlib
import json
import re
from flask_login import current_user
from core.db import db
from sqlalchemy.exc import IntegrityError
from ..model.report_template import ReportTemplate, utcnow
from ..model.report_template_version import ReportTemplateVersion
from ..model.report_parameter import ReportParameter
from .report_layout_service import ReportError, ReportLayoutService, default_document, validate_data, validate_schema


def authorize(action):
    if not current_user.is_authenticated:
        raise ReportError('reports.error.auth', status=401)
    if not current_user.has_permission('report_templates.' + action):
        raise ReportError('reports.error.forbidden', status=403)


def guard_json(value):
    def walk(item, depth=0):
        if depth > 32:
            raise ReportError('reports.error.input')
        if type(item) is dict:
            if any(type(k) is not str for k in item):
                raise ReportError('reports.error.input')
            for v in item.values():
                walk(v, depth + 1)
        elif type(item) is list:
            for v in item:
                walk(v, depth + 1)
        elif item is not None and type(item) not in (str, bool, int, float):
            raise ReportError('reports.error.input')
    walk(value)
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ReportError('reports.error.input') from exc
    if len(encoded.encode()) > 1024 * 1024:
        raise ReportError('reports.error.size', status=413)


def list_templates():
    authorize('list')
    return [obj.to_dict() for obj in ReportTemplate.query.filter_by(is_deleted=False).order_by(ReportTemplate.name).all()]


def get_template(ident):
    obj = db.session.get(ReportTemplate, ident)
    if not obj or obj.is_deleted:
        raise ReportError('reports.error.not_found', status=404)
    return obj


def get_version(ident, number):
    get_template(ident)
    obj = ReportTemplateVersion.query.filter_by(template_id=ident, version_number=number).first()
    if not obj:
        raise ReportError('reports.error.not_found', status=404)
    return obj


def parameter_definitions(version):
    return [p.to_dict() for p in ReportParameter.query.filter_by(version_id=version.id).order_by(ReportParameter.id).all()]


def read_version(ident, number):
    authorize('detail')
    version = get_version(ident, number)
    return {**version.to_dict(), 'parameters': parameter_definitions(version)}


def create_template(payload):
    authorize('create')
    guard_json(payload)
    if type(payload) is not dict or set(payload) != {'key', 'name'}:
        raise ReportError('reports.error.input')
    key, name = payload['key'], payload['name']
    if type(key) is not str or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,99}', key) or type(name) is not str or not 1 <= len(name.strip()) <= 120:
        raise ReportError('reports.error.input')
    obj = ReportTemplate(key=key, name=name.strip(), created_by_user_id=current_user.id)
    db.session.add(obj)
    try:
        db.session.flush()
        version = ReportTemplateVersion(template_id=obj.id, version_number=1, layout_json=default_document(),
                    data_schema_json={'type': 'object'}, sample_data_json={}, created_by_user_id=current_user.id)
        db.session.add(version)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReportError('reports.error.conflict', status=409) from exc
    return obj.to_dict()


def validate_parameters(definitions, supplied):
    if type(definitions) is not list or len(definitions) > 50 or type(supplied) is not dict:
        raise ReportError('reports.error.parameters')
    properties, required, values = {}, [], copy.deepcopy(supplied)
    for definition in definitions:
        if type(definition) is not dict or set(definition) - {'key', 'label', 'schema', 'required', 'default'}:
            raise ReportError('reports.error.parameters')
        key, label, schema = definition.get('key'), definition.get('label'), definition.get('schema')
        if type(key) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', key) or key in properties or type(label) is not str or not 1 <= len(label) <= 120 or type(definition.get('required', False)) is not bool:
            raise ReportError('reports.error.parameters')
        validate_schema(schema)
        properties[key] = schema
        if 'default' in definition:
            validate_data(schema, definition['default'])
            values.setdefault(key, definition['default'])
        if definition.get('required', False):
            required.append(key)
    validate_data({'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}, values)
    return values


def save_version(ident, number, payload):
    authorize('update')
    authorize('detail')
    guard_json(payload)
    if type(payload) is not dict or set(payload) != {'lock_version', 'layout', 'data_schema', 'sample_data', 'parameters'} or type(payload['lock_version']) is not int:
        raise ReportError('reports.error.input')
    obj = get_version(ident, number)
    if obj.status != 'draft':
        raise ReportError('reports.error.immutable', status=409)
    ReportLayoutService.validate(payload['layout'])
    validate_schema(payload['data_schema'])
    # Pode salvar rascunho com exemplos incompletos; publicação exige dados válidos.
    definitions = payload['parameters']
    if type(definitions) is not list:
        raise ReportError('reports.error.parameters')
    # Validação do contrato sem exigir valores de parâmetros obrigatórios.
    validate_parameters([{**d, 'required': False} if type(d) is dict else d for d in definitions], {})
    for d in definitions:
        if type(d.get('required', False)) is not bool:
            raise ReportError('reports.error.parameters')
    updated = ReportTemplateVersion.query.filter_by(id=obj.id, lock_version=payload['lock_version'], status='draft').update({
        'layout_json': payload['layout'], 'data_schema_json': payload['data_schema'], 'sample_data_json': payload['sample_data'],
        'lock_version': payload['lock_version'] + 1, 'updated_at': utcnow()}, synchronize_session=False)
    if updated != 1:
        db.session.rollback()
        raise ReportError('reports.error.conflict', status=409)
    ReportParameter.query.filter_by(version_id=obj.id).delete()
    for d in definitions:
        db.session.add(ReportParameter(version_id=obj.id, key=d['key'], label=d['label'], schema_json=d['schema'],
            is_required=d.get('required', False), has_default='default' in d, default_json=d.get('default')))
    db.session.commit()
    db.session.expire_all()
    return read_version(ident, number)


def compose_version(obj, data, parameters):
    guard_json({'data': data, 'parameters': parameters})
    validate_data(obj.data_schema_json, data)
    values = validate_parameters(parameter_definitions(obj), parameters)
    return ReportLayoutService.render(obj.layout_json, data, values)


def preview(ident, number, parameters):
    authorize('detail')
    obj = get_version(ident, number)
    html = compose_version(obj, obj.sample_data_json, parameters)
    db.session.rollback()  # Encerra leitura antes de iniciar o worker PDF.
    return html


def publish(ident, number, lock_version, parameters):
    authorize('publish')
    obj = get_version(ident, number)
    if type(lock_version) is not int or obj.status != 'draft' or obj.lock_version != lock_version:
        raise ReportError('reports.error.conflict', status=409)
    from .report_pdf_service import render_pdf
    html = compose_version(obj, obj.sample_data_json, parameters)
    revision_id = obj.id
    snapshot = {**obj.to_dict(), 'parameters': parameter_definitions(obj)}
    snapshot.pop('content_hash', None)
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    db.session.rollback()
    render_pdf(html)
    updated = ReportTemplateVersion.query.filter_by(id=revision_id, lock_version=lock_version, status='draft').update({
        'status': 'published', 'content_hash': digest, 'published_at': utcnow(), 'lock_version': lock_version + 1}, synchronize_session=False)
    if updated != 1:
        db.session.rollback()
        raise ReportError('reports.error.conflict', status=409)
    get_template(ident).active_version_number = number
    db.session.commit()
    db.session.expire_all()
    return {'version': number, 'content_hash': digest}


def clone_version(ident, number):
    authorize('update')
    obj = get_version(ident, number)
    latest = db.session.query(db.func.max(ReportTemplateVersion.version_number)).filter_by(template_id=ident).scalar() or 0
    new = ReportTemplateVersion(template_id=ident, version_number=latest + 1, layout_json=copy.deepcopy(obj.layout_json),
        data_schema_json=copy.deepcopy(obj.data_schema_json), sample_data_json=copy.deepcopy(obj.sample_data_json), created_by_user_id=current_user.id)
    try:
        db.session.add(new)
        db.session.flush()
        for d in parameter_definitions(obj):
            db.session.add(ReportParameter(version_id=new.id, key=d['key'], label=d['label'], schema_json=d['schema'],
                is_required=d['required'], has_default='default' in d, default_json=d.get('default')))
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReportError('reports.error.conflict', status=409) from exc
    return {'version': new.version_number}


def render_report(key, version, data, parameters):
    """Prepara HTML de versão publicada em leitura própria, sem rollback do consumidor."""
    with db.session.no_autoflush:
        authorize('render')
    if type(key) is not str or (version is not None and (type(version) is not int or version < 1)):
        raise ReportError('reports.error.input')
    guard_json({'data': data, 'parameters': parameters})
    # Não descartar ou confirmar alterações de outros addons na sessão do request.
    if db.session.new or db.session.dirty or db.session.deleted:
        raise ReportError('reports.error.transaction', status=409)
    with db.session.session_factory() as reader:
        obj = reader.query(ReportTemplate).filter_by(key=key, is_deleted=False).first()
        if not obj or not (number := version or obj.active_version_number):
            raise ReportError('reports.error.not_found', status=404)
        revision = reader.query(ReportTemplateVersion).filter_by(template_id=obj.id, version_number=number, status='published').first()
        if not revision:
            raise ReportError('reports.error.not_found', status=404)
        definitions = [p.to_dict() for p in reader.query(ReportParameter).filter_by(version_id=revision.id).order_by(ReportParameter.id).all()]
        layout, schema = copy.deepcopy(revision.layout_json), copy.deepcopy(revision.data_schema_json)
    validate_data(schema, data)
    values = validate_parameters(definitions, parameters)
    return ReportLayoutService.render(layout, data, values)


def generate_report(key, *, version=None, data, parameters=None):
    """Contrato público Python: devolve bytes PDF e revalida autorização."""
    from .report_pdf_service import render_pdf
    return render_pdf(render_report(key, version, data, {} if parameters is None else parameters))
