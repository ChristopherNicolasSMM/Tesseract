"""Ledger e cache organizacionais; decimais exatos também em SQLite."""
import json
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from sqlalchemy import event
from sqlalchemy.types import TypeDecorator, String
from annotations import label, plural, display_field, weak_ref
from core.db import db


class ExactDecimal(TypeDecorator):
    # SQLite converte NUMERIC em REAL: guardar texto evita essa perda silenciosa.
    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError('Persistência exige Decimal finito.')
        return format(value, 'f')

    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None


def decimal_string(value):
    return format(value, 'f')


@label('Saldo por organização')
@plural('organization_balances')
@display_field('organization_code')
@weak_ref('material_id', resolver='addons.addon_estoque.root.services.material_lookup.get_material', options='materials')
class OrganizationBalance(db.Model):
    __tablename__ = 'tesseract_estoque_organization_balance'
    __crudgen_no_create__ = True
    __crudgen_no_delete__ = True
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id', ondelete='RESTRICT'), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    quantity = db.Column(ExactDecimal(), nullable=False)
    stock_value = db.Column(ExactDecimal(), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('organization_code', 'material_id', name='uq_org_stock_balance'),)

    def to_dict(self):
        with localcontext() as ctx:
            ctx.prec = 64
            average = (self.stock_value / self.quantity).quantize(Decimal('0.000000000001'), rounding=ROUND_HALF_EVEN) if self.quantity else Decimal(0)
        return {'id': self.id, 'organization_code': self.organization_code, 'material_id': self.material_id,
                'currency_code': self.currency_code, 'quantidade_atual': decimal_string(self.quantity),
                'valor_total_estoque': decimal_string(self.stock_value), 'custo_medio': decimal_string(average),
                'ultima_atualizacao': self.updated_at.isoformat()}


@label('Movimentação por organização')
@plural('organization_movements')
@display_field('idempotency_key')
@weak_ref('material_id', resolver='addons.addon_estoque.root.services.material_lookup.get_material', options='materials')
@weak_ref('material_unidade_id', resolver='addons.addon_estoque.root.services.material_unidade_lookup.get_material_unidade', options='material_unidades')
class OrganizationMovement(db.Model):
    __tablename__ = 'tesseract_estoque_organization_movement'
    __crudgen_immutable__ = True
    __crudgen_no_delete__ = True
    id = db.Column(db.Integer, primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id', ondelete='RESTRICT'), nullable=False)
    material_unidade_id = db.Column(db.Integer, db.ForeignKey('material_unidade.id', ondelete='RESTRICT'))
    pedido_compra_item_id = db.Column(db.Integer, db.ForeignKey('item_pedido_compra.id', ondelete='RESTRICT'))
    currency_code = db.Column(db.String(3), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    quantity_delta = db.Column(ExactDecimal(), nullable=False)
    value_delta = db.Column(ExactDecimal(), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        db.UniqueConstraint('organization_code', 'idempotency_key', name='uq_org_stock_movement_key'),
        db.UniqueConstraint('pedido_compra_item_id', name='uq_org_stock_receipt_item'),
        db.CheckConstraint("kind IN ('entrada', 'saida', 'ajuste')", name='ck_org_stock_kind'),)

    def to_dict(self):
        return {'id': self.id, 'organization_code': self.organization_code, 'material_id': self.material_id,
                'material_unidade_id': self.material_unidade_id, 'pedido_compra_item_id': self.pedido_compra_item_id,
                'currency_code': self.currency_code, 'tipo_movimentacao': self.kind,
                'quantidade': decimal_string(self.quantity_delta), 'custo_total': decimal_string(self.value_delta),
                'idempotency_key': self.idempotency_key, 'snapshot': json.loads(self.snapshot_json),
                'created_by': self.created_by, 'created_at': self.created_at.isoformat()}


@label('Avaliação monetária de recebimento')
@plural('order_valuations')
@display_field('order_id')
class OrderValuation(db.Model):
    __tablename__ = 'tesseract_estoque_order_valuation'
    __crudgen_immutable__ = True
    __crudgen_no_delete__ = True
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id', ondelete='RESTRICT'), nullable=False, unique=True)
    request_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {'id': self.id, 'order_id': self.order_id, 'request': json.loads(self.request_json),
                'snapshot': json.loads(self.snapshot_json), 'created_by': self.created_by,
                'created_at': self.created_at.isoformat()}


def _immutable(mapper, connection, target):
    raise ValueError('Histórico organizacional imutável; corrija por nova movimentação.')


for model in (OrganizationMovement, OrderValuation):
    for operation in ('before_update', 'before_delete'):
        event.listen(model, operation, _immutable)
