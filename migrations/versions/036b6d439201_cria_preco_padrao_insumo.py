"""cria tesseract_brewstation_ingr_preco_padrao_insumo

proposta-precificacao-envase.md secao 6.1 - preco padrao por tipo de
insumo (malte/lupulo/levedura), consumido por feature_envase quando
nao ha preco real pago (ItemPedidoCompra) pro Material.

Revision ID: 036b6d439201
Revises: 40a4b558cc4a
Create Date: 2026-09-18 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '036b6d439201'
down_revision = '40a4b558cc4a'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_ingr_preco_padrao_insumo'


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo_insumo', sa.String(length=20), nullable=False),
        sa.Column('valor_padrao', sa.Float(), nullable=False, server_default='0'),
        sa.Column('unidade', sa.String(length=10), nullable=False, server_default='kg'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tipo_insumo', name='uq_preco_padrao_insumo_tipo'),
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
