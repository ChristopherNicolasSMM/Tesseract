"""Playground v2 (skill 06 §8) — Auth, Params, Pastas e Cookie Jar

Cria tesseract_playground_folder e tesseract_playground_cookie_jar;
adiciona params_json/auth_type/auth_config/folder_id/is_archived em
tesseract_playground_request.

Revision ID: b2d8a04f6c17
Revises: a1c7f92e5b04
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2d8a04f6c17'
down_revision = 'a1c7f92e5b04'
branch_labels = None
depends_on = None


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


def _fk_exists(table_name: str, fk_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return fk_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk["name"]}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou estas
    # tabelas/colunas (boot antes do primeiro `flask db upgrade`),
    # create_table/add_column/create_foreign_key falham como "already
    # exists"/"duplicate column" sem estas checagens.
    if not _table_exists("tesseract_playground_folder"):
        op.create_table(
            "tesseract_playground_folder",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("tesseract_playground_folder.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("tesseract_user.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not _table_exists("tesseract_playground_cookie_jar"):
        op.create_table(
            "tesseract_playground_cookie_jar",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("tesseract_user.id"), nullable=False, unique=True),
            sa.Column("cookies_json", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    with op.batch_alter_table("tesseract_playground_request") as batch_op:
        if not _column_exists("tesseract_playground_request", "params_json"):
            batch_op.add_column(sa.Column("params_json", sa.JSON(), nullable=True))
        if not _column_exists("tesseract_playground_request", "auth_type"):
            batch_op.add_column(sa.Column("auth_type", sa.String(length=20), nullable=True, server_default="none"))
        if not _column_exists("tesseract_playground_request", "auth_config"):
            batch_op.add_column(sa.Column("auth_config", sa.JSON(), nullable=True))
        if not _column_exists("tesseract_playground_request", "folder_id"):
            batch_op.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
        if not _column_exists("tesseract_playground_request", "is_archived"):
            batch_op.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not _fk_exists("tesseract_playground_request", "fk_playground_request_folder_id"):
            batch_op.create_foreign_key(
                "fk_playground_request_folder_id",
                "tesseract_playground_folder",
                ["folder_id"], ["id"],
            )


def downgrade():
    with op.batch_alter_table("tesseract_playground_request") as batch_op:
        if _fk_exists("tesseract_playground_request", "fk_playground_request_folder_id"):
            batch_op.drop_constraint("fk_playground_request_folder_id", type_="foreignkey")
        if _column_exists("tesseract_playground_request", "is_archived"):
            batch_op.drop_column("is_archived")
        if _column_exists("tesseract_playground_request", "folder_id"):
            batch_op.drop_column("folder_id")
        if _column_exists("tesseract_playground_request", "auth_config"):
            batch_op.drop_column("auth_config")
        if _column_exists("tesseract_playground_request", "auth_type"):
            batch_op.drop_column("auth_type")
        if _column_exists("tesseract_playground_request", "params_json"):
            batch_op.drop_column("params_json")

    if _table_exists("tesseract_playground_cookie_jar"):
        op.drop_table("tesseract_playground_cookie_jar")
    if _table_exists("tesseract_playground_folder"):
        op.drop_table("tesseract_playground_folder")
