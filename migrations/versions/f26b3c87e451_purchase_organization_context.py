"""Contexto explícito de compras; nenhum documento/saldo legado é atribuído."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'f26b3c87e451'
down_revision = 'e15a2b76d340'
branch_labels = None
depends_on = None
NAME = 'tesseract_estoque_purchase_context'


def table_definition():
    metadata = sa.MetaData()
    for name in ('processo_cotacao', 'pedido_compra'):
        sa.Table('tesseract_estoque_' + name, metadata, sa.Column('id', sa.Integer, primary_key=True))
    return sa.Table(NAME, metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('process_id', sa.Integer, sa.ForeignKey('tesseract_estoque_processo_cotacao.id', ondelete='RESTRICT')),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('tesseract_estoque_pedido_compra.id', ondelete='RESTRICT')),
        sa.Column('organization_code', sa.String(40), nullable=False),
        sa.Column('organization_name', sa.String(120), nullable=False),
        sa.Column('created_by', sa.String(120), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('process_id', name='uq_purchase_context_process'),
        sa.UniqueConstraint('order_id', name='uq_purchase_context_order'),
        sa.CheckConstraint('(process_id IS NOT NULL AND order_id IS NULL) OR (process_id IS NULL AND order_id IS NOT NULL)', name='ck_purchase_context_document'))


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table = table_definition()
    if inspector.has_table(NAME):
        validate_existing(inspector, table)
        uniques = [item['column_names'] for item in inspector.get_unique_constraints(NAME)]
        uniques += [item['column_names'] for item in inspector.get_indexes(NAME) if item['unique']]
        if any([field] not in uniques for field in ('process_id', 'order_id')):
            raise RuntimeError('Schema incompatível: contexto sem unicidade por documento.')
    else:
        # Mesmo com addon desativado, o schema histórico segue independente do registro ORM.
        table.create(conn)


def downgrade():
    conn = op.get_bind()
    if not sa.inspect(conn).has_table(NAME):
        return
    if conn.execute(sa.text(f'SELECT COUNT(*) FROM {NAME}')).scalar():
        raise RuntimeError('Downgrade bloqueado: vínculos organizacionais devem ser preservados.')
    op.drop_table(NAME)
