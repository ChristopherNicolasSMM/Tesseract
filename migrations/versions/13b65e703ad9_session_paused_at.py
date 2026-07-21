"""adiciona paused_at em tesseract_brewstation_mashctrl_session
(conversa — achado real de uso: pausar a sessão não congelava o
timer da etapa nem o disparo de alertas agendados, porque o cálculo
de tempo decorrido sempre usava datetime.now() sem considerar o
status "paused". paused_at guarda o instante da pausa; ao retomar,
os timestamps started_at da sessão e das etapas são deslocados pra
frente pela duração da pausa.)

Revision ID: 13b65e703ad9
Revises: 2ef7cb8deeba
Create Date: 2026-07-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13b65e703ad9'
down_revision = '2ef7cb8deeba'
branch_labels = None
depends_on = None

_TABLE = "tesseract_brewstation_mashctrl_session"
_COLUMN = "paused_at"


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
        batch_op.add_column(sa.Column(_COLUMN, sa.DateTime(), nullable=True))


def downgrade():
    if not _table_exists(_TABLE):
        return
    if not _column_exists(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
