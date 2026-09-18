"""adiciona is_workspace em tesseract_transaction

Suporte a destaque de tela consolidada na home (skill de consolidacao
de telas, is_workspace=True nao desativa nem reordena nenhuma
transacao existente - so decide se o card aparece na faixa em
destaque da home.html).

Revision ID: a829b579b1f2
Revises: 730e0d92ce65
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a829b579b1f2'
down_revision = '730e0d92ce65'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    if not _column_exists('tesseract_transaction', 'is_workspace'):
        with op.batch_alter_table('tesseract_transaction') as batch_op:
            batch_op.add_column(
                sa.Column('is_workspace', sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade():
    if _column_exists('tesseract_transaction', 'is_workspace'):
        with op.batch_alter_table('tesseract_transaction') as batch_op:
            batch_op.drop_column('is_workspace')
