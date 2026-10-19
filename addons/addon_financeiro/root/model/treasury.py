"""Contas, títulos e trilha financeira. Decimal armazenado como texto exato."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import event, inspect
from sqlalchemy.types import TypeDecorator, String
from annotations import label, plural, display_field, menu_icon
from core.db import db


class Money(TypeDecorator):
    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
            raise ValueError('Persistência monetária exige Decimal finito.')
        return format(value, 'f') if value is not None else None

    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None


def now():
    return datetime.now(timezone.utc)


def dto(row):
    result = {}
    for col in row.__table__.columns:
        value = getattr(row, col.key)
        if isinstance(value, Decimal): value = format(value, 'f')
        elif hasattr(value, 'isoformat'): value = value.isoformat()
        if col.key.endswith('_json'):
            result[col.key[:-5]] = json.loads(value) if value else None
        else: result[col.key] = value
    return result


@menu_icon('bi-bank')
@label('Conta financeira')
@plural('financial_accounts')
@display_field('name')
class FinancialAccount(db.Model):
    __tablename__ = 'treasury_account'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    bank_name = db.Column(db.String(100))
    branch = db.Column(db.String(30))
    account_number = db.Column(db.String(40))
    opening_date = db.Column(db.Date, nullable=False)
    balance = db.Column(Money(), nullable=False)
    opening_json = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'name', name='uq_fin_account_name'),
        db.CheckConstraint("kind IN ('BANK','CASH')", name='ck_fin_account_kind'))
    to_dict = dto


@menu_icon('bi-tags')
@label('Categoria financeira')
@plural('financial_categories')
@display_field('name')
class FinancialCategory(db.Model):
    __tablename__ = 'treasury_category'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    direction = db.Column(db.String(12), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'name', name='uq_fin_category_name'),
        db.CheckConstraint("direction IN ('PAYABLE','RECEIVABLE')", name='ck_fin_category_direction'))
    to_dict = dto


@menu_icon('bi-diagram-3')
@label('Centro de custo')
@plural('financial_cost_centers')
@display_field('name')
class FinancialCostCenter(db.Model):
    __tablename__ = 'treasury_cost_center'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'name', name='uq_fin_center_name'),)
    to_dict = dto


@menu_icon('bi-journal-text')
@label('Títulos a pagar e receber')
@plural('financial_titles')
@display_field('reference')
class FinancialTitle(db.Model):
    __tablename__ = 'treasury_title'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    kind = db.Column(db.String(12), nullable=False)
    reference = db.Column(db.String(120), nullable=False)
    counterparty = db.Column(db.String(200), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    amount = db.Column(Money(), nullable=False)
    base_amount = db.Column(Money(), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('treasury_category.id', ondelete='RESTRICT'), nullable=False)
    cost_center_id = db.Column(db.Integer, db.ForeignKey('treasury_cost_center.id', ondelete='RESTRICT'), nullable=False)
    source_reference = db.Column(db.String(80), unique=True)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_title_key'),
        db.CheckConstraint("kind IN ('PAYABLE','RECEIVABLE')", name='ck_fin_title_kind'))
    to_dict = dto


class FinancialInstallment(db.Model):
    __tablename__ = 'treasury_installment'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    title_id = db.Column(db.Integer, db.ForeignKey('treasury_title.id', ondelete='RESTRICT'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(Money(), nullable=False)
    base_amount = db.Column(Money(), nullable=False)
    __table_args__ = (db.UniqueConstraint('title_id', 'number', name='uq_fin_installment_number'),)
    to_dict = dto


@menu_icon('bi-check2-circle')
@label('Pagamentos e recebimentos')
@plural('financial_settlements')
@display_field('idempotency_key')
class FinancialSettlement(db.Model):
    __tablename__ = 'treasury_settlement'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    installment_id = db.Column(db.Integer, db.ForeignKey('treasury_installment.id', ondelete='RESTRICT'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    principal = db.Column(Money(), nullable=False)
    carrying_base = db.Column(Money(), nullable=False)
    cash_base = db.Column(Money(), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_settlement_key'),)
    to_dict = dto


class FinancialReversal(db.Model):
    __tablename__ = 'treasury_reversal'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    settlement_id = db.Column(db.Integer, db.ForeignKey('treasury_settlement.id', ondelete='RESTRICT'), nullable=False, unique=True)
    organization_code = db.Column(db.String(40), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_reversal_key'),)
    to_dict = dto


class FinancialCancellation(db.Model):
    __tablename__ = 'treasury_cancellation'
    __crudgen_immutable__ = True
    title_id = db.Column(db.Integer, db.ForeignKey('treasury_title.id', ondelete='RESTRICT'), primary_key=True)
    reason = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    to_dict = dto


@menu_icon('bi-list-columns-reverse')
@label('Fluxo de caixa')
@plural('financial_movements')
@display_field('reference')
class FinancialMovement(db.Model):
    __tablename__ = 'treasury_movement'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('treasury_account.id', ondelete='RESTRICT'), nullable=False)
    reference = db.Column(db.String(80), nullable=False)
    amount_delta = db.Column(Money(), nullable=False)
    balance_after = db.Column(Money(), nullable=False)
    operation_date = db.Column(db.Date, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('account_id', 'reference', name='uq_fin_movement_reference'),)
    to_dict = dto


def immutable(*args):
    raise ValueError('Histórico financeiro imutável; utilize estorno ou cancelamento rastreável.')


for model in (FinancialTitle, FinancialInstallment, FinancialSettlement, FinancialReversal, FinancialCancellation, FinancialMovement):
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)


def protect_catalog(mapper, connection, row):
    editable = {'name', 'is_active', 'version'}
    if isinstance(row, FinancialAccount): editable |= {'bank_name', 'branch', 'account_number', 'balance'}
    for attr in inspect(row).attrs:
        if attr.key not in editable and attr.history.has_changes():
            raise ValueError('Identidade e abertura financeiras imutáveis.')


for model in (FinancialAccount, FinancialCategory, FinancialCostCenter):
    event.listen(model, 'before_update', protect_catalog)
    event.listen(model, 'before_delete', immutable)
