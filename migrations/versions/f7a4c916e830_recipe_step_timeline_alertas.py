"""Timeline unica da receita (RecipeStep substitui MashStep) + colunas
de disparo de alerta em BrewSessionStep (conversa - timeline de
alertas e etapas)

Revision ID: f7a4c916e830
Revises: e5f1a37c8d02
Create Date: 2026-07-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a4c916e830'
down_revision = 'e5f1a37c8d02'
branch_labels = None
depends_on = None

_OLD_TABLE = "tesseract_brewstation_mashctrl_mash_step"
_NEW_TABLE = "tesseract_brewstation_mashctrl_recipe_step"
_SESSION_STEP_TABLE = "tesseract_brewstation_mashctrl_session_step"


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
    # Achado real recorrente (BACKLOG.md): se db.create_all() já criou
    # a tabela nova (boot antes do primeiro `flask db upgrade`),
    # create_table falha como "already exists" sem esta checagem.
    if not _table_exists(_NEW_TABLE):
        op.create_table(
            _NEW_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("tesseract_brewstation_mashctrl_recipe.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("step_type", sa.String(length=20), nullable=False, server_default="mash"),
            sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("nome", sa.String(length=150), nullable=True),
            sa.Column("temperatura", sa.Float(), nullable=True),
            sa.Column("tempo_min", sa.Integer(), nullable=True),
            sa.Column("ramp_time_min", sa.Integer(), nullable=True),
            sa.Column("tipo", sa.String(length=20), nullable=True, server_default="temperature"),
            sa.Column("trigger_minutes_remaining", sa.Integer(), nullable=True),
            sa.Column("parent_step_id", sa.Integer(), sa.ForeignKey(f"{_NEW_TABLE}.id", ondelete="CASCADE"), nullable=True),
            sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
            sa.Column("source_recipe_ingredient_id", sa.Integer(), sa.ForeignKey("tesseract_brewstation_mashctrl_recipe_ingredient.id", ondelete="CASCADE"), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )

    # Migra dado real de mash_step (se a tabela antiga ainda existir) —
    # nunca perde histórico de receita já cadastrada.
    if _table_exists(_OLD_TABLE):
        op.execute(f"""
            INSERT INTO {_NEW_TABLE}
                (recipe_id, step_type, ordem, nome, temperatura, tempo_min, ramp_time_min, tipo, source, is_deleted)
            SELECT
                recipe_id, 'mash', ordem, nome, temperatura, tempo_min, ramp_time_min, tipo, 'manual', is_deleted
            FROM {_OLD_TABLE}
        """)
        op.drop_table(_OLD_TABLE)

    with op.batch_alter_table(_SESSION_STEP_TABLE) as batch_op:
        if not _column_exists(_SESSION_STEP_TABLE, "trigger_at_seconds"):
            batch_op.add_column(sa.Column("trigger_at_seconds", sa.Integer(), nullable=True))
        if not _column_exists(_SESSION_STEP_TABLE, "alarm_fired"):
            batch_op.add_column(sa.Column("alarm_fired", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table(_SESSION_STEP_TABLE) as batch_op:
        if _column_exists(_SESSION_STEP_TABLE, "alarm_fired"):
            batch_op.drop_column("alarm_fired")
        if _column_exists(_SESSION_STEP_TABLE, "trigger_at_seconds"):
            batch_op.drop_column("trigger_at_seconds")

    if not _table_exists(_OLD_TABLE) and _table_exists(_NEW_TABLE):
        op.create_table(
            _OLD_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("tesseract_brewstation_mashctrl_recipe.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("nome", sa.String(length=100), nullable=True),
            sa.Column("temperatura", sa.Float(), nullable=False),
            sa.Column("tempo_min", sa.Integer(), nullable=True),
            sa.Column("ramp_time_min", sa.Integer(), nullable=True),
            sa.Column("tipo", sa.String(length=20), nullable=True, server_default="temperature"),
            sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.execute(f"""
            INSERT INTO {_OLD_TABLE}
                (recipe_id, nome, temperatura, tempo_min, ramp_time_min, tipo, ordem, is_deleted)
            SELECT recipe_id, nome, temperatura, tempo_min, ramp_time_min, tipo, ordem, is_deleted
            FROM {_NEW_TABLE}
            WHERE step_type = 'mash' AND temperatura IS NOT NULL
        """)

    if _table_exists(_NEW_TABLE):
        op.drop_table(_NEW_TABLE)
