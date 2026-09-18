"""adiciona volume_planejado_litros (recipe) e volume_real_litros (session)

proposta-precificacao-envase.md (secao 6.6) - base minima planejado
vs real que a precificacao de Envase precisa, sem OG/FG (depende de
sensor/controlador externo ainda nao integrado).

Revision ID: 40a4b558cc4a
Revises: a829b579b1f2
Create Date: 2026-09-18 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '40a4b558cc4a'
down_revision = 'a829b579b1f2'
branch_labels = None
depends_on = None

_TABLE_RECIPE = 'tesseract_brewstation_mashctrl_recipe'
_TABLE_SESSION = 'tesseract_brewstation_mashctrl_session'


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    if not _column_exists(_TABLE_RECIPE, 'volume_planejado_litros'):
        with op.batch_alter_table(_TABLE_RECIPE) as batch_op:
            batch_op.add_column(sa.Column('volume_planejado_litros', sa.Float(), nullable=True))

    if not _column_exists(_TABLE_SESSION, 'volume_real_litros'):
        with op.batch_alter_table(_TABLE_SESSION) as batch_op:
            batch_op.add_column(sa.Column('volume_real_litros', sa.Float(), nullable=True))


def downgrade():
    if _column_exists(_TABLE_SESSION, 'volume_real_litros'):
        with op.batch_alter_table(_TABLE_SESSION) as batch_op:
            batch_op.drop_column('volume_real_litros')

    if _column_exists(_TABLE_RECIPE, 'volume_planejado_litros'):
        with op.batch_alter_table(_TABLE_RECIPE) as batch_op:
            batch_op.drop_column('volume_planejado_litros')
