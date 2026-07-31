"""Fase 10, Patch 1 — fundacao de schema do Designer v2 (Acoes + Dados
+ substituicao de tela CrudGen). Ver docs/skills/16 (a formalizar) e
BACKLOG.md, Fase 10.

- tesseract_odata_connection ganha is_local (marca a conexao que
  representa o provedor OData do proprio Tesseract)
- tesseract_designer_page ganha replaces_entity_key / replaces_view /
  replace_in_menu (schema apenas -- resolver fica pro Patch 6)
- tabela nova tesseract_designer_data_action (Acao de Dado)

Revision ID: 5f1d8a3c7e92
Revises: 13b65e703ad9
Create Date: 2026-07-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f1d8a3c7e92'
down_revision = '13b65e703ad9'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Achado real, ja registrado em BACKLOG.md (skill 05, 07b, etc.):
    quando db.create_all() ja criou a tabela/coluna com o shape atual
    do model, add_column falharia como "duplicate column name" sem
    essa checagem."""
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    # ── tesseract_odata_connection.is_local ─────────────────────────
    if _table_exists("tesseract_odata_connection"):
        with op.batch_alter_table("tesseract_odata_connection") as batch_op:
            if not _column_exists("tesseract_odata_connection", "is_local"):
                batch_op.add_column(
                    sa.Column("is_local", sa.Boolean(), nullable=False, server_default=sa.false())
                )

    # ── tesseract_designer_page.replaces_* ──────────────────────────
    if _table_exists("tesseract_designer_page"):
        with op.batch_alter_table("tesseract_designer_page") as batch_op:
            if not _column_exists("tesseract_designer_page", "replaces_entity_key"):
                batch_op.add_column(sa.Column("replaces_entity_key", sa.String(150), nullable=True))
            if not _column_exists("tesseract_designer_page", "replaces_view"):
                batch_op.add_column(sa.Column("replaces_view", sa.String(20), nullable=True))
            if not _column_exists("tesseract_designer_page", "replace_in_menu"):
                batch_op.add_column(
                    sa.Column("replace_in_menu", sa.Boolean(), nullable=False, server_default=sa.false())
                )

    # ── tesseract_designer_data_action (tabela nova) ────────────────
    if not _table_exists("tesseract_designer_data_action"):
        op.create_table(
            "tesseract_designer_data_action",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("connection_id", sa.Integer(), sa.ForeignKey("tesseract_odata_connection.id"), nullable=False),
            sa.Column("entity_name", sa.String(100), nullable=False),
            sa.Column("operation", sa.String(20), nullable=False, server_default="query"),
            sa.Column("static_params", sa.JSON(), nullable=True),
            sa.Column("permission_required", sa.String(150), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("tesseract_user.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade():
    if _table_exists("tesseract_designer_data_action"):
        op.drop_table("tesseract_designer_data_action")

    if _table_exists("tesseract_designer_page"):
        with op.batch_alter_table("tesseract_designer_page") as batch_op:
            if _column_exists("tesseract_designer_page", "replace_in_menu"):
                batch_op.drop_column("replace_in_menu")
            if _column_exists("tesseract_designer_page", "replaces_view"):
                batch_op.drop_column("replaces_view")
            if _column_exists("tesseract_designer_page", "replaces_entity_key"):
                batch_op.drop_column("replaces_entity_key")

    if _table_exists("tesseract_odata_connection"):
        with op.batch_alter_table("tesseract_odata_connection") as batch_op:
            if _column_exists("tesseract_odata_connection", "is_local"):
                batch_op.drop_column("is_local")
