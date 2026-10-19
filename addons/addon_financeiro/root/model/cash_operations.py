"""Operações e conciliação: eventos imutáveis e vínculos ativos separados."""
from sqlalchemy import event
from annotations import label, plural, display_field, menu_icon
from core.db import db
from .treasury import Money, now, dto, immutable


@menu_icon('bi-arrow-left-right')
@label('Transferências financeiras')
@plural('financial_transfers')
@display_field('idempotency_key')
class FinancialTransfer(db.Model):
    __tablename__ = 'cash_transfer'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    source_account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    destination_account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    amount = db.Column(Money(), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_cash_transfer_0'),)
    to_dict = dto

event.listen(FinancialTransfer, 'before_update', immutable)
event.listen(FinancialTransfer, 'before_delete', immutable)

class FinancialTransferReversal(db.Model):
    __tablename__ = 'cash_transfer_reversal'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey('cash_transfer.id', ondelete='RESTRICT'), nullable=False)
    organization_code = db.Column(db.String(40), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('transfer_id', name='uq_cash_transfer_reversal_0'),db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_cash_transfer_reversal_1'),)
    to_dict = dto

event.listen(FinancialTransferReversal, 'before_update', immutable)
event.listen(FinancialTransferReversal, 'before_delete', immutable)


@menu_icon('bi-link-45deg')
@label('Conciliação bancária')
@plural('financial_reconciliations')
@display_field('reference')
class BankStatement(db.Model):
    __tablename__ = 'bank_statement'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    reference = db.Column(db.String(120), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_bank_statement_0'),)
    to_dict = dto

event.listen(BankStatement, 'before_update', immutable)
event.listen(BankStatement, 'before_delete', immutable)

class BankStatementLine(db.Model):
    __tablename__ = 'bank_statement_line'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    statement_id = db.Column(db.Integer, db.ForeignKey('bank_statement.id', ondelete='RESTRICT'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    external_id = db.Column(db.String(120), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    amount = db.Column(Money(), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('account_id', 'external_id', name='uq_bank_statement_line_0'),)
    to_dict = dto

event.listen(BankStatementLine, 'before_update', immutable)
event.listen(BankStatementLine, 'before_delete', immutable)

class BankReconciliation(db.Model):
    __tablename__ = 'bank_reconciliation'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    line_id = db.Column(db.Integer, db.ForeignKey('bank_statement_line.id', ondelete='RESTRICT'), nullable=False)
    movement_id = db.Column(db.Integer, db.ForeignKey('treasury_movement.id', ondelete='RESTRICT'), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_bank_reconciliation_0'),)
    to_dict = dto

event.listen(BankReconciliation, 'before_update', immutable)
event.listen(BankReconciliation, 'before_delete', immutable)

class BankReconciliationUndo(db.Model):
    __tablename__ = 'bank_reconciliation_undo'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    reconciliation_id = db.Column(db.Integer, db.ForeignKey('bank_reconciliation.id', ondelete='RESTRICT'), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('reconciliation_id', name='uq_bank_reconciliation_undo_0'),db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_bank_reconciliation_undo_1'),)
    to_dict = dto

event.listen(BankReconciliationUndo, 'before_update', immutable)
event.listen(BankReconciliationUndo, 'before_delete', immutable)

class ActiveBankReconciliation(db.Model):
    __tablename__ = 'bank_reconciliation_active'
    __crudgen_immutable__ = True
    line_id = db.Column(db.Integer, db.ForeignKey('bank_statement_line.id', ondelete='RESTRICT'), primary_key=True)
    movement_id = db.Column(db.Integer, db.ForeignKey('treasury_movement.id', ondelete='RESTRICT'), nullable=False, unique=True)
    reconciliation_id = db.Column(db.Integer, db.ForeignKey('bank_reconciliation.id', ondelete='RESTRICT'), nullable=False, unique=True)
