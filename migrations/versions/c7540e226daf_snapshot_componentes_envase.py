"""Congela componentes e custos de embalagem do envase.

Revision ID: c7540e226daf
Revises: b493ea0c61d4
"""
from alembic import op
import sqlalchemy as sa

revision = "c7540e226daf"
down_revision = "b493ea0c61d4"
branch_labels = None
depends_on = None


def upgrade():
    # Os registros anteriores mantêm NULL e continuam usando a leitura
    # dinâmica de composição e custo até uma reconciliação explícita.
    with op.batch_alter_table("tesseract_brewstation_env_envase") as batch_op:
        batch_op.add_column(sa.Column("componentes_snapshot", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("tesseract_brewstation_env_envase") as batch_op:
        batch_op.drop_column("componentes_snapshot")
