"""Model Builder — tabela filha de verdade (relacionamento 1:1/1:N)

Adiciona parent_model_definition_id/parent_fk_column_name/
parent_relation_label/parent_relation_type em tesseract_model_definition
e child_model_definition_id em tesseract_model_field_definition.

Revision ID: d4e0a26f9c31
Revises: c3f9b15e7a82
Create Date: 2026-07-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e0a26f9c31'
down_revision = 'c3f9b15e7a82'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _fk_exists(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return fk_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk["name"]}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou estas
    # colunas (boot antes do primeiro `flask db upgrade`), add_column
    # falha como "duplicate column name" sem esta checagem.
    with op.batch_alter_table("tesseract_model_definition") as batch_op:
        if not _column_exists("tesseract_model_definition", "parent_model_definition_id"):
            batch_op.add_column(sa.Column("parent_model_definition_id", sa.Integer(), nullable=True))
        if not _column_exists("tesseract_model_definition", "parent_fk_column_name"):
            batch_op.add_column(sa.Column("parent_fk_column_name", sa.String(length=100), nullable=True))
        if not _column_exists("tesseract_model_definition", "parent_relation_label"):
            batch_op.add_column(sa.Column("parent_relation_label", sa.String(length=150), nullable=True))
        if not _column_exists("tesseract_model_definition", "parent_relation_type"):
            batch_op.add_column(sa.Column("parent_relation_type", sa.String(length=20), nullable=True))
        if not _fk_exists("tesseract_model_definition", "fk_model_definition_parent_id"):
            batch_op.create_foreign_key(
                "fk_model_definition_parent_id",
                "tesseract_model_definition",
                ["parent_model_definition_id"], ["id"],
            )

    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        if not _column_exists("tesseract_model_field_definition", "child_model_definition_id"):
            batch_op.add_column(sa.Column("child_model_definition_id", sa.Integer(), nullable=True))
        if not _fk_exists("tesseract_model_field_definition", "fk_model_field_definition_child_id"):
            batch_op.create_foreign_key(
                "fk_model_field_definition_child_id",
                "tesseract_model_definition",
                ["child_model_definition_id"], ["id"],
            )


def downgrade():
    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        if _fk_exists("tesseract_model_field_definition", "fk_model_field_definition_child_id"):
            batch_op.drop_constraint("fk_model_field_definition_child_id", type_="foreignkey")
        if _column_exists("tesseract_model_field_definition", "child_model_definition_id"):
            batch_op.drop_column("child_model_definition_id")

    with op.batch_alter_table("tesseract_model_definition") as batch_op:
        if _fk_exists("tesseract_model_definition", "fk_model_definition_parent_id"):
            batch_op.drop_constraint("fk_model_definition_parent_id", type_="foreignkey")
        if _column_exists("tesseract_model_definition", "parent_relation_type"):
            batch_op.drop_column("parent_relation_type")
        if _column_exists("tesseract_model_definition", "parent_relation_label"):
            batch_op.drop_column("parent_relation_label")
        if _column_exists("tesseract_model_definition", "parent_fk_column_name"):
            batch_op.drop_column("parent_fk_column_name")
        if _column_exists("tesseract_model_definition", "parent_model_definition_id"):
            batch_op.drop_column("parent_model_definition_id")
