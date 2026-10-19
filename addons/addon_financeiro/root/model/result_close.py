"""Fechamentos gerenciais imutáveis e reaberturas explícitas."""
from sqlalchemy import event
from core.db import db
from .treasury import now,dto,immutable

class ResultClose(db.Model):
    __tablename__='result_close'
    __crudgen_immutable__=True
    id=db.Column(db.Integer,primary_key=True)
    organization_code=db.Column(db.String(40),nullable=False)
    period=db.Column(db.Date,nullable=False)
    version=db.Column(db.Integer,nullable=False)
    reason=db.Column(db.String(1000),nullable=False)
    idempotency_key=db.Column(db.String(80),nullable=False)
    request_json=db.Column(db.Text,nullable=False)
    snapshot_json=db.Column(db.Text,nullable=False)
    digest=db.Column(db.String(64),nullable=False)
    created_by=db.Column(db.String(120),nullable=False)
    created_at=db.Column(db.DateTime,nullable=False,default=now)
    __table_args__=(db.UniqueConstraint('organization_code','period','version',name='uq_result_close_0'),db.UniqueConstraint('organization_code','idempotency_key',name='uq_result_close_1'),)
    to_dict=dto

event.listen(ResultClose,'before_update',immutable)
event.listen(ResultClose,'before_delete',immutable)

class ResultReopen(db.Model):
    __tablename__='result_reopen'
    __crudgen_immutable__=True
    id=db.Column(db.Integer,primary_key=True)
    organization_code=db.Column(db.String(40),nullable=False)
    close_id=db.Column(db.Integer,db.ForeignKey('result_close.id',ondelete='RESTRICT'),nullable=False)
    reason=db.Column(db.String(1000),nullable=False)
    idempotency_key=db.Column(db.String(80),nullable=False)
    request_json=db.Column(db.Text,nullable=False)
    created_by=db.Column(db.String(120),nullable=False)
    created_at=db.Column(db.DateTime,nullable=False,default=now)
    __table_args__=(db.UniqueConstraint('close_id',name='uq_result_reopen_0'),db.UniqueConstraint('organization_code','idempotency_key',name='uq_result_reopen_1'),)
    to_dict=dto

event.listen(ResultReopen,'before_update',immutable)
event.listen(ResultReopen,'before_delete',immutable)

class ActiveResultClose(db.Model):
    __tablename__='result_close_active'
    __crudgen_immutable__=True
    id=db.Column(db.Integer,primary_key=True)
    organization_code=db.Column(db.String(40),nullable=False)
    period=db.Column(db.Date,nullable=False)
    close_id=db.Column(db.Integer,db.ForeignKey('result_close.id',ondelete='RESTRICT'),nullable=False)
    __table_args__=(db.UniqueConstraint('organization_code','period',name='uq_result_close_active_0'),db.UniqueConstraint('close_id',name='uq_result_close_active_1'),)
    to_dict=dto
