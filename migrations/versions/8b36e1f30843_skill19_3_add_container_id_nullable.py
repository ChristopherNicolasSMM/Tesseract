"""skill 19 (3/6) - adiciona tesseract_brewstation_yeastbank_bank_item.container_id
(nullable nesta etapa — passo 5 torna obrigatorio depois do backfill do passo 4)

Ver docs/skills/19-proposta-reestruturacao-yeast-bank-container.md.

Revision ID: 8b36e1f30843
Revises: 77ebb453fa4c
Create Date: 2026-08-20 00:00:00.000002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b36e1f30843'
down_revision = '77ebb453fa4c'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_item'
_CONTAINER_TABLE = 'tesseract_brewstation_yeastbank_container'


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


def upgrade():
    if _table_exists(_TABLE) and not _column_exists(_TABLE, 'container_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column('container_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_bank_item_container_id', _CONTAINER_TABLE, ['container_id'], ['id'],
            )


def downgrade():
    if _table_exists(_TABLE) and _column_exists(_TABLE, 'container_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_constraint('fk_bank_item_container_id', type_='foreignkey')
            batch_op.drop_column('container_id')
