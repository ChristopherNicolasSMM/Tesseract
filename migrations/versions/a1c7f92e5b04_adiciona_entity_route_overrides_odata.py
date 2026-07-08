"""adiciona entity_route_overrides em tesseract_odata_connection
(bugfix registrado em BACKLOG.md, "Bugs de OData" — resolução de
nome de rota quando o metadata não declara EntitySet)

Revision ID: a1c7f92e5b04
Revises: 8e2f6b1a94dc
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c7f92e5b04'
down_revision = '8e2f6b1a94dc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tesseract_odata_connection") as batch_op:
        batch_op.add_column(sa.Column("entity_route_overrides", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("tesseract_odata_connection") as batch_op:
        batch_op.drop_column("entity_route_overrides")
