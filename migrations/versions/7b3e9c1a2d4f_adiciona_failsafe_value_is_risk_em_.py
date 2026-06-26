"""adiciona failsafe_value/is_risk em tesseract_dvm_actor (extensao do
DeviceActor existente, sem criar tabela nova - decisao registrada em
docs/skills/05-proposta-addon-device-manager-e-mqtt.md, secao 4)

Revision ID: 7b3e9c1a2d4f
Revises: 4a8524f00549
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b3e9c1a2d4f'
down_revision = '4a8524f00549'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tesseract_dvm_actor") as batch_op:
        batch_op.add_column(sa.Column("failsafe_value", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column("is_risk", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table("tesseract_dvm_actor") as batch_op:
        batch_op.drop_column("is_risk")
        batch_op.drop_column("failsafe_value")
