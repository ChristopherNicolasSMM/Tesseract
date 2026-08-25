"""skill 22 (2/3) - cell_count_history ganha bank_event_id (rastreio
de origem) e campos brutos de entrada da câmara de Neubauer

Ver docs/skills/22-fusao-starter-bankevent-neubauer.md.

Revision ID: 27c13496373e
Revises: 6eede3637319
Create Date: 2026-08-24 00:00:00.000001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27c13496373e'
down_revision = '6eede3637319'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_cell_count_history'
_EVENT_TABLE = 'tesseract_brewstation_yeastbank_bank_event'

_NEW_COLUMNS = {
    'bank_event_id': (sa.Integer(), True),  # (tipo, tem FK)
    'cells_counted_live': (sa.Integer(), False),
    'cells_counted_dead': (sa.Integer(), False),
    'squares_counted': (sa.Integer(), False),
    'dilution_factor': (sa.Float(), False),
}


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
    if not _table_exists(_TABLE):
        return

    for col_name, (col_type, tem_fk) in _NEW_COLUMNS.items():
        if _column_exists(_TABLE, col_name):
            continue
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
            if tem_fk:
                batch_op.create_foreign_key(
                    'fk_cell_count_history_bank_event_id', _EVENT_TABLE, [col_name], ['id'],
                )


def downgrade():
    if not _table_exists(_TABLE):
        return

    for col_name, (_, tem_fk) in _NEW_COLUMNS.items():
        if not _column_exists(_TABLE, col_name):
            continue
        with op.batch_alter_table(_TABLE) as batch_op:
            if tem_fk:
                batch_op.drop_constraint('fk_cell_count_history_bank_event_id', type_='foreignkey')
            batch_op.drop_column(col_name)
