"""Reconhecimento gerencial por competência, independente de caixa e parcelas."""
from sqlalchemy import event
from annotations import label, plural, display_field, menu_icon
from core.db import db
from .treasury import Money, now, dto, immutable

class ResultClassification(db.Model):
    __tablename__ = 'result_classification'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40),nullable=False)
    category_id = db.Column(db.Integer,db.ForeignKey('treasury_category.id',ondelete='RESTRICT'),nullable=False)
    version = db.Column(db.Integer,nullable=False)
    group_code = db.Column(db.String(30),nullable=False)
    valid_from = db.Column(db.Date,nullable=False)
    reason = db.Column(db.String(1000),nullable=False)
    idempotency_key = db.Column(db.String(80),nullable=False)
    request_json = db.Column(db.Text,nullable=False)
    snapshot_json = db.Column(db.Text,nullable=False)
    created_by = db.Column(db.String(120),nullable=False)
    created_at = db.Column(db.DateTime,nullable=False,default=now)
    __table_args__ = (db.UniqueConstraint('category_id','version',name='uq_result_classification_0'),db.UniqueConstraint('organization_code','idempotency_key',name='uq_result_classification_1'),)
    to_dict = dto

event.listen(ResultClassification,'before_update',immutable)
event.listen(ResultClassification,'before_delete',immutable)

@label('DRE e resultados')
@plural('financial_results')
@display_field('reference')
@menu_icon('bi-table')
class AccrualEntry(db.Model):
    __tablename__ = 'accrual_entry'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40),nullable=False)
    source_key = db.Column(db.String(180),nullable=False)
    source_type = db.Column(db.String(15),nullable=False)
    source_id = db.Column(db.Integer,nullable=True)
    component = db.Column(db.String(20),nullable=True)
    reference = db.Column(db.String(120),nullable=False)
    classification_id = db.Column(db.Integer,db.ForeignKey('result_classification.id',ondelete='RESTRICT'),nullable=False)
    effect = db.Column(db.String(12),nullable=False)
    amount = db.Column(Money(),nullable=False)
    currency_code = db.Column(db.String(3),nullable=False)
    reason = db.Column(db.String(1000),nullable=False)
    idempotency_key = db.Column(db.String(80),nullable=False)
    request_json = db.Column(db.Text,nullable=False)
    snapshot_json = db.Column(db.Text,nullable=False)
    created_by = db.Column(db.String(120),nullable=False)
    created_at = db.Column(db.DateTime,nullable=False,default=now)
    __table_args__ = (db.UniqueConstraint('organization_code','idempotency_key',name='uq_accrual_entry_0'),)
    to_dict = dto

event.listen(AccrualEntry,'before_update',immutable)
event.listen(AccrualEntry,'before_delete',immutable)

class AccrualAllocation(db.Model):
    __tablename__ = 'accrual_allocation'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer,db.ForeignKey('accrual_entry.id',ondelete='RESTRICT'),nullable=False)
    period = db.Column(db.Date,nullable=False)
    cost_center_id = db.Column(db.Integer,db.ForeignKey('treasury_cost_center.id',ondelete='RESTRICT'),nullable=False)
    amount = db.Column(Money(),nullable=False)
    snapshot_json = db.Column(db.Text,nullable=False)
    created_by = db.Column(db.String(120),nullable=False)
    created_at = db.Column(db.DateTime,nullable=False,default=now)
    to_dict = dto

event.listen(AccrualAllocation,'before_update',immutable)
event.listen(AccrualAllocation,'before_delete',immutable)

class AccrualReversal(db.Model):
    __tablename__ = 'accrual_reversal'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40),nullable=False)
    entry_id = db.Column(db.Integer,db.ForeignKey('accrual_entry.id',ondelete='RESTRICT'),nullable=False)
    reason = db.Column(db.String(1000),nullable=False)
    idempotency_key = db.Column(db.String(80),nullable=False)
    request_json = db.Column(db.Text,nullable=False)
    created_by = db.Column(db.String(120),nullable=False)
    created_at = db.Column(db.DateTime,nullable=False,default=now)
    __table_args__ = (db.UniqueConstraint('entry_id',name='uq_accrual_reversal_0'),db.UniqueConstraint('organization_code','idempotency_key',name='uq_accrual_reversal_1'),)
    to_dict = dto

event.listen(AccrualReversal,'before_update',immutable)
event.listen(AccrualReversal,'before_delete',immutable)

class ActiveAccrual(db.Model):
    __tablename__ = 'accrual_active'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40),nullable=False)
    source_key = db.Column(db.String(180),nullable=False)
    entry_id = db.Column(db.Integer,db.ForeignKey('accrual_entry.id',ondelete='RESTRICT'),nullable=False)
    __table_args__ = (db.UniqueConstraint('organization_code','source_key',name='uq_accrual_active_0'),db.UniqueConstraint('entry_id',name='uq_accrual_active_1'),)
    to_dict = dto
