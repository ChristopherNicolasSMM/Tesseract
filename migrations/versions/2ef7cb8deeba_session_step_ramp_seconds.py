"""adiciona ramp_seconds em tesseract_brewstation_mashctrl_session_step
(conversa — ajuste pos-Ponto 2: fase de rampa era descartada na
geracao da sessao, so o hold virava duration_seconds. ramp_seconds
guarda a fase de rampa separada, pro card de Etapa do Dashboard
mostrar as duas barras — rampa some quando termina, hold assume.)

Revision ID: 2ef7cb8deeba
Revises: 729d8d2f7f25
Create Date: 2026-07-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ef7cb8deeba'
down_revision = '729d8d2f7f25'
branch_labels = None
depends_on = None

_TABLE = "tesseract_brewstation_mashctrl_session_step"
_COLUMN = "ramp_seconds"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    if not _table_exists(_TABLE):
        return
    if _column_exists(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.add_column(sa.Column(_COLUMN, sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    if not _table_exists(_TABLE):
        return
    if not _column_exists(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
