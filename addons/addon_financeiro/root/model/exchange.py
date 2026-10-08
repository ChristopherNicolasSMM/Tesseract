"""Taxas direcionais e conversões confirmadas, preservadas como histórico."""
import json
from datetime import datetime, timezone
from sqlalchemy import event
from annotations import label, plural, display_field, menu_icon
from core.db import db
def _immutable(mapper, connection, target):
    raise ValueError("Histórico de câmbio imutável; cadastre um novo registro.")

@menu_icon('bi-currency-exchange')
@label('Taxa de câmbio')
@plural('exchange_rates')
@display_field('source')
class ExchangeRate(db.Model):
    __tablename__ = 'tesseract_financeiro_exchange_rate'
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    source_currency = db.Column(db.String(3), db.ForeignKey('tesseract_financeiro_currency.code', ondelete='RESTRICT'), nullable=False)
    target_currency = db.Column(db.String(3), db.ForeignKey('tesseract_financeiro_currency.code', ondelete='RESTRICT'), nullable=False)
    rate = db.Column(db.String(31), nullable=False)
    valid_on = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(120), nullable=False)
    rate_type = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(120), nullable=False)
    __table_args__ = (db.CheckConstraint('source_currency <> target_currency', name='ck_fin_rate_pair'), db.CheckConstraint("rate_type IN ('MANUAL', 'CONTRACTUAL')", name='ck_fin_rate_type'))

    def to_dict(self):
        return {key: getattr(self, key) for key in ('id', 'organization_code', 'source_currency', 'target_currency', 'rate', 'source', 'rate_type', 'created_by')} | {'valid_on': self.valid_on.isoformat(), 'created_at': self.created_at.isoformat()}

@menu_icon('bi-clock-history')
@label('Conversão monetária')
@plural('monetary_conversions')
@display_field('reference')
class MonetaryConversion(db.Model):
    __tablename__ = 'tesseract_financeiro_conversion'
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    reference = db.Column(db.String(120), nullable=False)
    snapshot = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_conversion_key'),)

    def to_dict(self):
        return {key: getattr(self, key) for key in ('id', 'organization_code', 'idempotency_key', 'reference', 'created_by')} | {'snapshot': json.loads(self.snapshot), 'created_at': self.created_at.isoformat()}

for model in (ExchangeRate, MonetaryConversion):
    event.listen(model, 'before_update', _immutable)
    event.listen(model, 'before_delete', _immutable)
