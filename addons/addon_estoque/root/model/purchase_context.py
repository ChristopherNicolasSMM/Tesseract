"""Vínculo explícito e imutável; catálogo permanece compartilhado."""
from datetime import datetime, timezone
from sqlalchemy import event, select, update
from annotations import label, plural, display_field
from core.db import db


@label('Contexto organizacional de compra')
@plural('purchase_contexts')
@display_field('organization_code')
class PurchaseContext(db.Model):
    __tablename__ = 'tesseract_estoque_purchase_context'
    __crudgen_immutable__ = True
    id = db.Column(db.Integer, primary_key=True)
    process_id = db.Column(db.Integer, db.ForeignKey('processo_cotacao.id', ondelete='RESTRICT'), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id', ondelete='RESTRICT'), nullable=True)
    organization_code = db.Column(db.String(40), nullable=False)
    organization_name = db.Column(db.String(120), nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        db.UniqueConstraint('process_id', name='uq_purchase_context_process'),
        db.UniqueConstraint('order_id', name='uq_purchase_context_order'),
        db.CheckConstraint('(process_id IS NOT NULL AND order_id IS NULL) OR (process_id IS NULL AND order_id IS NOT NULL)', name='ck_purchase_context_document'),
    )

    def to_dict(self):
        return {key: getattr(self, key) for key in ('id', 'process_id', 'order_id',
            'organization_code', 'organization_name', 'created_by')} | {'created_at': self.created_at.isoformat()}


def _immutable(mapper, connection, target):
    raise ValueError('Contexto organizacional imutável; preserve o documento e seu histórico.')


for operation in ('before_update', 'before_delete'):
    event.listen(PurchaseContext, operation, _immutable)


def protect_document(mapper, connection, target):
    # Também protege SQLite com foreign_keys desligado e exclusão ORM direta.
    field = PurchaseContext.order_id if target.__class__.__name__ == 'PedidoCompra' else PurchaseContext.process_id
    if connection.execute(select(PurchaseContext.id).where(field == target.id)).first():
        raise ValueError('Documento com contexto organizacional não pode ser excluído permanentemente.')


def protect_quotation_process(mapper, connection, target):
    table = mapper.local_table
    old = (connection.execute(select(table.c.processo_cotacao_id).where(table.c.id == target.id)).scalar()
           if target.id is not None else None)
    parent = next(iter(table.c.processo_cotacao_id.foreign_keys)).column.table
    # A criação/mudança de cotação participa da mesma reserva usada pelo vínculo.
    for ident in sorted({value for value in (old, target.processo_cotacao_id) if value is not None}):
        connection.execute(update(parent).where(parent.c.id == ident).values(updated_at=parent.c.updated_at))
    if old is not None and old != target.processo_cotacao_id and connection.execute(
            select(PurchaseContext.id).where(PurchaseContext.process_id.in_([old, target.processo_cotacao_id]))).first():
        raise ValueError('Cotação não pode mudar de processo quando há contexto organizacional vinculado.')
