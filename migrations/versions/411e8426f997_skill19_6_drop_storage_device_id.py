"""skill 19 (6/6) - remove tesseract_brewstation_yeastbank_bank_item.storage_device_id
(substituido por container_id — dispositivo agora e sempre resolvido via
item.container.device, sem FK redundante)

Ultimo passo da reestruturacao. Ver
docs/skills/19-proposta-reestruturacao-yeast-bank-container.md.

Revision ID: 411e8426f997
Revises: 5d57e2e5a9aa
Create Date: 2026-08-20 00:00:00.000005

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '411e8426f997'
down_revision = '5d57e2e5a9aa'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_item'
_DEVICE_TABLE = 'tesseract_brewstation_yeastbank_storage_device'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _fk_name_for(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk.get("constrained_columns", []):
            return fk.get("name")
    return None


def upgrade():
    if _table_exists(_TABLE) and _column_exists(_TABLE, 'storage_device_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            fk_name = _fk_name_for(_TABLE, 'storage_device_id')
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.drop_column('storage_device_id')


def downgrade():
    # Best-effort: a coluna volta nullable e vazia — a resolução
    # 1:1 original (storage_device_id -> container_id -> device_id) não
    # é reconstruível com certeza se um item tiver sido movido de
    # container manualmente entre o upgrade e o downgrade.
    if _table_exists(_TABLE) and not _column_exists(_TABLE, 'storage_device_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column('storage_device_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_bank_item_storage_device_id', _DEVICE_TABLE, ['storage_device_id'], ['id'],
            )

        bind = op.get_bind()
        bind.execute(
            sa.text(
                f"""
                UPDATE {_TABLE}
                SET storage_device_id = (
                    SELECT device_id FROM tesseract_brewstation_yeastbank_container c
                    WHERE c.id = {_TABLE}.container_id
                )
                """
            )
        )
