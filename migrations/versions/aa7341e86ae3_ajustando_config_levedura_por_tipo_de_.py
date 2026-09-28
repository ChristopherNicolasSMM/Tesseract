"""ajustando config levedura por tipo de harmazenamento

Revision ID: aa7341e86ae3
Revises: f6f47fbb19af
Create Date: 2026-08-20 12:55:14.742816

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aa7341e86ae3'
down_revision = 'f6f47fbb19af'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_config'


def _column_exists():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return False
    return 'storage_type' in {column['name'] for column in inspector.get_columns(_TABLE)}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names() or _column_exists():
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.add_column(sa.Column('storage_type', sa.String(length=40), nullable=False))


def downgrade():
    if not _column_exists():
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column('storage_type')
