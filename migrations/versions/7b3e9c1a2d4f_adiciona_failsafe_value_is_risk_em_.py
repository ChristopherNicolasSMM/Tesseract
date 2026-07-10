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


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Achado real (BACKLOG.md): quando `db.create_all()` já criou a
    tabela com o shape ATUAL do model, esta coluna já existe e o
    `add_column` falharia como "duplicate column name" sem essa
    checagem."""
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    if not _table_exists("tesseract_dvm_actor"):
        return
    with op.batch_alter_table("tesseract_dvm_actor") as batch_op:
        if not _column_exists("tesseract_dvm_actor", "failsafe_value"):
            batch_op.add_column(sa.Column("failsafe_value", sa.String(50), nullable=True))
        if not _column_exists("tesseract_dvm_actor", "is_risk"):
            batch_op.add_column(
                sa.Column("is_risk", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade():
    if not _table_exists("tesseract_dvm_actor"):
        return
    with op.batch_alter_table("tesseract_dvm_actor") as batch_op:
        if _column_exists("tesseract_dvm_actor", "is_risk"):
            batch_op.drop_column("is_risk")
        if _column_exists("tesseract_dvm_actor", "failsafe_value"):
            batch_op.drop_column("failsafe_value")
