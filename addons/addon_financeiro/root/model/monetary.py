"""Catálogo e política inicial imutável; nenhuma moeda inferida do legado."""
from datetime import datetime, timezone
from annotations import label, plural, display_field
from core.db import db


@label('Moeda')
@plural('currencies')
@display_field('name')
class Currency(db.Model):
    __tablename__ = 'tesseract_financeiro_currency'
    code = db.Column(db.String(3), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    decimal_places = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_currency_scale'),)

    def to_dict(self):
        return {field: getattr(self, field) for field in ('code', 'name', 'decimal_places')}


@label('Política monetária')
@plural('monetary_policies')
@display_field('organization_code')
class MonetaryPolicy(db.Model):
    __tablename__ = 'tesseract_financeiro_monetary_policy'
    id = db.Column(db.Integer, primary_key=True)
    # Referência fraca ao Core, validada pelo serviço público de identidade.
    organization_code = db.Column(db.String(40), nullable=False, unique=True)
    currency_code = db.Column(db.String(3), db.ForeignKey('tesseract_financeiro_currency.code', ondelete='RESTRICT'), nullable=False)
    decimal_places = db.Column(db.Integer, nullable=False)
    rounding = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        db.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_policy_scale'),
        db.CheckConstraint("rounding IN ('HALF_UP', 'HALF_EVEN')", name='ck_fin_policy_rounding'),)

    def to_dict(self):
        return {field: getattr(self, field) for field in ('id', 'organization_code', 'currency_code', 'decimal_places', 'rounding')} | {'created_at': self.created_at.isoformat()}


# Configuração inicial é imutável também para escritas ORM fora das rotas.
from sqlalchemy import event


def _immutable(mapper, connection, target):
    raise ValueError('Configuração monetária inicial imutável; use futura versão explícita.')


for _model in (Currency, MonetaryPolicy):
    event.listen(_model, 'before_update', _immutable)
    event.listen(_model, 'before_delete', _immutable)
