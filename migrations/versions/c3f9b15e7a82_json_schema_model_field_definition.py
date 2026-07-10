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


def upgrade():
    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        batch_op.add_column(sa.Column("json_schema", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("tesseract_model_field_definition") as batch_op:
        batch_op.drop_column("json_schema")
