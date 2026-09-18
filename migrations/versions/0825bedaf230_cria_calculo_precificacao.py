"""cria tesseract_brewstation_env_calculo_precificacao e _item_custo_ingrediente

proposta-precificacao-envase.md - motor de precificacao de Envase.
envase_id fica nullable (fluxo simula -> calcula -> cria envase).

Revision ID: 0825bedaf230
Revises: 036b6d439201
Create Date: 2026-09-18 00:00:03.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '0825bedaf230'
down_revision = '036b6d439201'
branch_labels = None
depends_on = None

_TABLE_CALCULO = 'tesseract_brewstation_env_calculo_precificacao'
_TABLE_ITEM = 'tesseract_brewstation_env_item_custo_ingrediente'
_TABLE_SESSION = 'tesseract_brewstation_mashctrl_session'
_TABLE_ENVASE = 'tesseract_brewstation_env_envase'


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if _TABLE_CALCULO not in existing_tables:
        op.create_table(
            _TABLE_CALCULO,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('lote_id', sa.Integer(), sa.ForeignKey(f'{_TABLE_SESSION}.id'), nullable=False),
            sa.Column('envase_id', sa.Integer(), sa.ForeignKey(f'{_TABLE_ENVASE}.id'), nullable=True),
            sa.Column('custo_ingredientes_total', sa.Float(), nullable=False, server_default='0'),
            sa.Column('custo_embalagem_total', sa.Float(), nullable=False, server_default='0'),
            sa.Column('subtotal', sa.Float(), nullable=False, server_default='0'),
            sa.Column('percentual_lucro', sa.Float(), nullable=False, server_default='0'),
            sa.Column('valor_lucro', sa.Float(), nullable=False, server_default='0'),
            sa.Column('percentual_ipi', sa.Float(), nullable=False, server_default='0'),
            sa.Column('valor_ipi', sa.Float(), nullable=False, server_default='0'),
            sa.Column('percentual_icms', sa.Float(), nullable=False, server_default='0'),
            sa.Column('valor_icms', sa.Float(), nullable=False, server_default='0'),
            sa.Column('valor_total', sa.Float(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    if _TABLE_ITEM not in existing_tables:
        op.create_table(
            _TABLE_ITEM,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('calculo_id', sa.Integer(),
                      sa.ForeignKey(f'{_TABLE_CALCULO}.id', ondelete='CASCADE'), nullable=False),
            sa.Column('material_id', sa.Integer(), nullable=True),
            sa.Column('quantidade', sa.Float(), nullable=False),
            sa.Column('preco_unitario_usado', sa.Float(), nullable=False, server_default='0'),
            sa.Column('custo_total', sa.Float(), nullable=False, server_default='0'),
            sa.Column('origem_preco', sa.String(length=20), nullable=False, server_default='sem_preco'),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if _TABLE_ITEM in existing_tables:
        op.drop_table(_TABLE_ITEM)
    if _TABLE_CALCULO in existing_tables:
        op.drop_table(_TABLE_CALCULO)
