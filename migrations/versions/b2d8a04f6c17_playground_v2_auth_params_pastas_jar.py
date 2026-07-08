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


def upgrade():
    op.create_table(
        "tesseract_playground_folder",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("tesseract_playground_folder.id"), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("tesseract_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "tesseract_playground_cookie_jar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("tesseract_user.id"), nullable=False, unique=True),
        sa.Column("cookies_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    with op.batch_alter_table("tesseract_playground_request") as batch_op:
        batch_op.add_column(sa.Column("params_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("auth_type", sa.String(length=20), nullable=True, server_default="none"))
        batch_op.add_column(sa.Column("auth_config", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key(
            "fk_playground_request_folder_id",
            "tesseract_playground_folder",
            ["folder_id"], ["id"],
        )


def downgrade():
    with op.batch_alter_table("tesseract_playground_request") as batch_op:
        batch_op.drop_constraint("fk_playground_request_folder_id", type_="foreignkey")
        batch_op.drop_column("is_archived")
        batch_op.drop_column("folder_id")
        batch_op.drop_column("auth_config")
        batch_op.drop_column("auth_type")
        batch_op.drop_column("params_json")

    op.drop_table("tesseract_playground_cookie_jar")
    op.drop_table("tesseract_playground_folder")
