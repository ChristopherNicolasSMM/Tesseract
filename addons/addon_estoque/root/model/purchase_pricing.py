"""Cadastro monetário explícito; colunas Float antigas são só compatibilidade."""
import json
from datetime import datetime, timezone
from sqlalchemy import event
from annotations import label, plural, display_field
from core.db import db


@label('Cadastro monetário de compra')
@plural('purchase_pricings')
@display_field('id')
class PurchasePricing(db.Model):
    __tablename__ = 'purchase_pricing'
    __crudgen_immutable__ = True
    __crudgen_no_create__ = True
    __crudgen_no_delete__ = True
    __table_args__ = (db.CheckConstraint(
        '(order_id IS NOT NULL AND quotation_id IS NULL) OR '
        '(order_id IS NULL AND quotation_id IS NOT NULL)', name='ck_purchase_pricing_owner'),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id', ondelete='RESTRICT'), unique=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('cotacao.id', ondelete='RESTRICT'), unique=True)
    organization_code = db.Column(db.String(40), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {'id': self.id, 'order_id': self.order_id, 'quotation_id': self.quotation_id,
                'organization_code': self.organization_code, 'currency_code': self.currency_code,
                'snapshot': json.loads(self.snapshot_json), 'created_by': self.created_by,
                'created_at': self.created_at.isoformat()}


def immutable(mapper, connection, target):
    raise ValueError('Cadastro monetário imutável; preserve o documento e crie outro rascunho.')


event.listen(PurchasePricing, 'before_update', immutable)
event.listen(PurchasePricing, 'before_delete', immutable)
