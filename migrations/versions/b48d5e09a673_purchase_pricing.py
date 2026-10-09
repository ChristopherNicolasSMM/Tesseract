"""Cadastro monetário explícito sem converter ou atribuir moeda ao legado."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'b48d5e09a673'
down_revision = 'a37c4d98f562'
branch_labels = None
depends_on = None
NAME = 'tesseract_estoque_purchase_pricing'


def definition():
    meta = sa.MetaData()
    for name in ('pedido_compra', 'cotacao'):
        sa.Table('tesseract_estoque_' + name, meta, sa.Column('id', sa.Integer, primary_key=True))
    return sa.Table(NAME, meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('tesseract_estoque_pedido_compra.id', ondelete='RESTRICT'), unique=True),
        sa.Column('quotation_id', sa.Integer, sa.ForeignKey('tesseract_estoque_cotacao.id', ondelete='RESTRICT'), unique=True),
        sa.Column('organization_code', sa.String(40), nullable=False),
        sa.Column('currency_code', sa.String(3), nullable=False),
        sa.Column('snapshot_json', sa.Text, nullable=False),
        sa.Column('created_by', sa.String(120), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.CheckConstraint('(order_id IS NOT NULL AND quotation_id IS NULL) OR '
                           '(order_id IS NULL AND quotation_id IS NOT NULL)', name='ck_purchase_pricing_owner'))


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    table = definition()
    if NAME in inspector.get_table_names():
        validate_existing(inspector, table)
    else:
        table.create(connection)


def downgrade():
    connection = op.get_bind()
    if NAME in sa.inspect(connection).get_table_names():
        if connection.execute(sa.text('SELECT COUNT(*) FROM ' + NAME)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve os cadastros monetários de compras.')
        op.drop_table(NAME)
