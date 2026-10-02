"""Congela volume/unidades do envase e base do cálculo de precificação.

Revision ID: f8c214ab709e
Revises: e6274a913bc0
"""
from alembic import op
import sqlalchemy as sa

revision = 'f8c214ab709e'
down_revision = 'e6274a913bc0'
branch_labels = None
depends_on = None
_FIELDS = [('tesseract_brewstation_env_envase', 'producao_snapshot'),
           ('tesseract_brewstation_env_calculo_precificacao', 'base_calculo_snapshot')]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, field in _FIELDS:
        if field not in {column['name'] for column in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column(field, sa.JSON(), nullable=True))
    # Não reconstrói dados históricos a partir dos cadastros atuais.


def downgrade():
    for table, field in reversed(_FIELDS):
        if field in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.drop_column(field)
