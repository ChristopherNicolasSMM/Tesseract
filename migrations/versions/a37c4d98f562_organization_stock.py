"""Ledger/saldos exatos por organização; não atribui registros legados."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'a37c4d98f562'
down_revision = 'f26b3c87e451'
branch_labels = None
depends_on = None
PREFIX = 'tesseract_estoque_'


def definitions():
    meta=sa.MetaData()
    for name in ('material','material_unidade','item_pedido_compra','pedido_compra'):
        sa.Table(PREFIX+name,meta,sa.Column('id',sa.Integer,primary_key=True))
    balance=sa.Table(PREFIX+'organization_balance',meta,
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('material_id',sa.Integer,sa.ForeignKey(PREFIX+'material.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('currency_code',sa.String(3),nullable=False),sa.Column('quantity',sa.String(64),nullable=False),
        sa.Column('stock_value',sa.String(64),nullable=False),sa.Column('updated_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','material_id',name='uq_org_stock_balance'))
    movement=sa.Table(PREFIX+'organization_movement',meta,
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('material_id',sa.Integer,sa.ForeignKey(PREFIX+'material.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('material_unidade_id',sa.Integer,sa.ForeignKey(PREFIX+'material_unidade.id',ondelete='RESTRICT')),
        sa.Column('pedido_compra_item_id',sa.Integer,sa.ForeignKey(PREFIX+'item_pedido_compra.id',ondelete='RESTRICT'),unique=True),
        sa.Column('currency_code',sa.String(3),nullable=False),sa.Column('kind',sa.String(10),nullable=False),
        sa.Column('quantity_delta',sa.String(64),nullable=False),sa.Column('value_delta',sa.String(64),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),sa.Column('created_by',sa.String(120),nullable=False),
        sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_org_stock_movement_key'),
        sa.CheckConstraint("kind IN ('entrada', 'saida', 'ajuste')",name='ck_org_stock_kind'))
    valuation=sa.Table(PREFIX+'order_valuation',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('order_id',sa.Integer,sa.ForeignKey(PREFIX+'pedido_compra.id',ondelete='RESTRICT'),nullable=False,unique=True),
        sa.Column('request_json',sa.Text,nullable=False),sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False))
    return [balance,movement,valuation]


def upgrade():
    conn=op.get_bind();inspector=sa.inspect(conn);tables=definitions()
    present=set(inspector.get_table_names())
    # Todos os schemas existentes são validados antes da primeira escrita DDL.
    for table in tables:
        if table.name in present:
            validate_existing(inspector,table)
            uniques=[item['column_names'] for item in inspector.get_unique_constraints(table.name)]
            uniques += [item['column_names'] for item in inspector.get_indexes(table.name) if item['unique']]
            for constraint in table.constraints:
                if isinstance(constraint,sa.UniqueConstraint) and list(constraint.columns.keys()) not in uniques:
                    raise RuntimeError('Schema incompatível: unicidade organizacional ausente.')
    for table in tables:
        if table.name not in present:
            table.create(conn)


def downgrade():
    conn=op.get_bind();names=[table.name for table in definitions()]
    present=set(sa.inspect(conn).get_table_names())
    if any(conn.execute(sa.text(f'SELECT COUNT(*) FROM {name}')).scalar() for name in names if name in present):
        raise RuntimeError('Downgrade bloqueado: histórico/saldos organizacionais devem ser preservados.')
    for name in reversed(names):
        if name in present:
            op.drop_table(name)
