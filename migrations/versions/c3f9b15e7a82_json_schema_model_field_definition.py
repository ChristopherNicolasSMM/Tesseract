"""adiciona json_schema em tesseract_model_field_definition
(Model Builder — tipo de campo "json" com sub-campos de documentação)

Revision ID: c3f9b15e7a82
Revises: b2d8a04f6c17
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3f9b15e7a82'
down_revision = 'b2d8a04f6c17'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou a coluna
    # (boot antes do primeiro `flask db upgrade`), add_column falha
    # como "duplicate column name" sem esta checagem.
    if _column_exists("tesseract_model_field_definition", "json_schema"):
        return
    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        batch_op.add_column(sa.Column("json_schema", sa.JSON(), nullable=True))


def downgrade():
    if not _column_exists("tesseract_model_field_definition", "json_schema"):
        return
    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        batch_op.drop_column("json_schema")
