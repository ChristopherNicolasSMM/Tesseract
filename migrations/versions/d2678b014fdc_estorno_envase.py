"""Registra estorno rastreável de envase.

Revision ID: d2678b014fdc
Revises: c7540e226daf
"""
from alembic import op
import sqlalchemy as sa

revision = "d2678b014fdc"
down_revision = "c7540e226daf"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tesseract_brewstation_env_envase") as batch_op:
        batch_op.add_column(sa.Column("estorno_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("cancelado_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("motivo_cancelamento", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("cancelado_por_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("tesseract_brewstation_env_envase") as batch_op:
        batch_op.drop_column("cancelado_por_id")
        batch_op.drop_column("motivo_cancelamento")
        batch_op.drop_column("cancelado_em")
        batch_op.drop_column("estorno_snapshot")
