"""adiciona source_recipe_step_id em tesseract_brewstation_mashctrl_session_step
(conversa — Dashboard de Brassagem, Ponto 2: etapa atual/próxima no
Dashboard. Liga cada BrewSessionStep de volta ao RecipeStep que o
originou, pra permitir resync_session_steps() sem duplicar etapa —
mesmo espírito do source_recipe_ingredient_id já usado em
sync_hop_alerts.)

Revision ID: 729d8d2f7f25
Revises: f7a4c916e830
Create Date: 2026-07-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '729d8d2f7f25'
down_revision = 'f7a4c916e830'
branch_labels = None
depends_on = None

_TABLE = "tesseract_brewstation_mashctrl_session_step"
_RECIPE_STEP_TABLE = "tesseract_brewstation_mashctrl_recipe_step"
_COLUMN = "source_recipe_step_id"


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
        # FK inline (mesmo padrão de 3a91c7de5f42) — nomeada explicitamente
        # pra ficar estável entre bancos, mas o downgrade não depende do
        # nome: em SQLite, batch_alter_table recria a tabela inteira, então
        # basta dropar a coluna que a FK some junto (drop_constraint
        # separado quebra — SQLite não preserva nome de constraint em
        # batch recreate).
        batch_op.add_column(sa.Column(
            _COLUMN, sa.Integer(),
            sa.ForeignKey(f"{_RECIPE_STEP_TABLE}.id", name="fk_session_step_source_recipe_step"),
            nullable=True,
        ))


def downgrade():
    if not _table_exists(_TABLE):
        return
    if not _column_exists(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
