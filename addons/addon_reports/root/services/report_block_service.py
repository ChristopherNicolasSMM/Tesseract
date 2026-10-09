"""Catálogo de snapshots autorizado pelas permissões de modelos existentes."""
import copy
import hashlib
import json
import re
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from core.db import db
from ..model.report_block import ReportBlock
from ..model.report_template import utcnow
from . import report_template_service as templates
from .report_layout_service import ReportError, ReportLayoutService


def list_blocks():
    templates.authorize('list')
    columns = [getattr(ReportBlock,key) for key in ('id','key','name','content_hash','lock_version')]
    return [dict(row._mapping) for row in db.session.query(*columns).filter(ReportBlock.is_deleted.is_(False)).order_by(ReportBlock.name,ReportBlock.id).all()]


def block(ident):
    value = db.session.get(ReportBlock,ident)
    if not value or value.is_deleted:
        raise ReportError('reports.error.not_found',status=404)
    return value


def read_block(ident):
    templates.authorize('detail')
    value = block(ident)
    return {**value.to_dict(),'node':copy.deepcopy(value.node_json),'source':copy.deepcopy(value.source_json)}


def create_block(payload):
    templates.authorize('create')
    templates.authorize('detail')
    templates.guard_json(payload)
    if type(payload) is not dict or set(payload)!={'key','name','template_id','version','node_id'}:
        raise ReportError('reports.error.input')
    if type(payload['key']) is not str or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,99}',payload['key']) or type(payload['name']) is not str or not 1<=len(payload['name'].strip())<=120:
        raise ReportError('reports.error.input')
    if any(type(payload[key]) is not int or payload[key]<1 for key in ('template_id','version')) or type(payload['node_id']) is not str:
        raise ReportError('reports.error.input')
    revision = templates.get_version(payload['template_id'],payload['version'])
    def find(nodes):
        for node in nodes:
            if node['id']==payload['node_id']:return node
            found = find(node.get('children',[]))
            if found is not None:return found
    node = find(revision.layout_json['body'])
    if node is None:
        raise ReportError('reports.error.not_found',status=404)
    snapshot = copy.deepcopy(node)
    ReportLayoutService.validate({'schema_version':1,'body':[snapshot]})
    digest = hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
    value = ReportBlock(key=payload['key'],name=payload['name'].strip(),node_json=snapshot,
        source_json={'template_id':payload['template_id'],'version':payload['version'],'node_id':payload['node_id']},
        content_hash=digest,created_by_user_id=current_user.id)
    db.session.add(value)
    try:db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReportError('reports.error.conflict',status=409) from exc
    return value.to_dict()


def archive_block(ident,payload):
    templates.authorize('delete')
    templates.guard_json(payload)
    if type(payload) is not dict or set(payload)!={'lock_version'} or type(payload['lock_version']) is not int:
        raise ReportError('reports.error.input')
    value = block(ident)
    updated = ReportBlock.query.filter_by(id=value.id,is_deleted=False,lock_version=payload['lock_version']).update(
        {'is_deleted':True,'deleted_at':utcnow(),'lock_version':payload['lock_version']+1},synchronize_session=False)
    if updated!=1:
        db.session.rollback()
        raise ReportError('reports.error.conflict',status=409)
    db.session.commit()
    return {'id':ident,'is_deleted':True}
