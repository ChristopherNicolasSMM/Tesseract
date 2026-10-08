"""Revisões append-only da política inicial, sem reinterpretar a moeda-base."""
from datetime import datetime, timezone
from sqlalchemy import event
from annotations import label, plural, display_field, menu_icon, field_labels
from core.db import db


@menu_icon('bi-journal-check')
@field_labels({'policy_id': 'Política inicial', 'version_number': 'Versão',
               'decimal_places': 'Casas decimais', 'rounding': 'Arredondamento',
               'valid_from': 'Válida a partir de', 'reason': 'Motivo', 'created_by': 'Autor'})
@label('Versão de política monetária')
@plural('policy_versions')
@display_field('reason')
class MonetaryPolicyVersion(db.Model):
    __tablename__ = 'tesseract_financeiro_policy_version'
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('tesseract_financeiro_monetary_policy.id', ondelete='RESTRICT'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    decimal_places = db.Column(db.Integer, nullable=False)
    rounding = db.Column(db.String(16), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    policy = db.relationship('MonetaryPolicy', lazy='joined')
    __table_args__ = (
        db.UniqueConstraint('policy_id', 'version_number', name='uq_fin_policy_version_number'),
        db.CheckConstraint('version_number >= 2', name='ck_fin_policy_version_number'),
        db.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_policy_version_scale'),
        db.CheckConstraint("rounding IN ('HALF_UP', 'HALF_EVEN')", name='ck_fin_policy_version_rounding'),)

    def to_dict(self):
        return {key: getattr(self, key) for key in (
            'id', 'policy_id', 'version_number', 'decimal_places', 'rounding', 'reason', 'created_by')} | {
                'organization_code': self.policy.organization_code,
                'currency_code': self.policy.currency_code,
                'valid_from': self.valid_from.isoformat(), 'created_at': self.created_at.isoformat()}


def _immutable(mapper, connection, target):
    raise ValueError('Versão monetária imutável; cadastre uma nova versão.')


for operation in ('before_update', 'before_delete'):
    event.listen(MonetaryPolicyVersion, operation, _immutable)
