"""Vínculo do inventário Brewfather com Material do estoque.

Revision ID: 6abac6de2f17
Revises: d2678b014fdc
"""
from alembic import op
import sqlalchemy as sa


revision = "6abac6de2f17"
down_revision = "d2678b014fdc"
branch_labels = None
depends_on = None

TABLE = "tesseract_brewstation_brewfather_inventory_link"


def upgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("categoria", sa.String(length=20), nullable=False),
        sa.Column("remote_id", sa.String(length=100), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("categoria", "remote_id", name="uq_bf_inventory_remote"),
        sa.UniqueConstraint("categoria", "material_id", name="uq_bf_inventory_material"),
    )
    op.create_index("ix_bf_inventory_link_material_id", TABLE, ["material_id"])


def downgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
