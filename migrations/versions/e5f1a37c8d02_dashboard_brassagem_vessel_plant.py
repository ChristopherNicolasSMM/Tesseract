"""Dashboard de Brassagem — vessel_id em tesseract_brewstation_mashctrl_widget
e plant_id em tesseract_brewstation_mashctrl_layout (conversa —
arquitetura de dashboard consolidada com device_manager + mash_control)

Revision ID: e5f1a37c8d02
Revises: d4e0a26f9c31
Create Date: 2026-07-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f1a37c8d02'
down_revision = 'd4e0a26f9c31'
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
    # Achado real recorrente (BACKLOG.md): se db.create_all() já criou
    # estas colunas (boot antes do primeiro `flask db upgrade`),
    # add_column falha como "duplicate column name" sem esta checagem.
    with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
        if not _column_exists("tesseract_brewstation_mashctrl_widget", "vessel_id"):
            batch_op.add_column(sa.Column("vessel_id", sa.Integer(), nullable=True))
        if not _fk_exists("tesseract_brewstation_mashctrl_widget", "fk_mashctrl_widget_vessel_id"):
            batch_op.create_foreign_key(
                "fk_mashctrl_widget_vessel_id",
                "tesseract_brewstation_mashctrl_plant_vessel",
                ["vessel_id"], ["id"],
            )

    with op.batch_alter_table("tesseract_brewstation_mashctrl_layout") as batch_op:
        if not _column_exists("tesseract_brewstation_mashctrl_layout", "plant_id"):
            batch_op.add_column(sa.Column("plant_id", sa.Integer(), nullable=True))
        if not _fk_exists("tesseract_brewstation_mashctrl_layout", "fk_mashctrl_layout_plant_id"):
            batch_op.create_foreign_key(
                "fk_mashctrl_layout_plant_id",
                "tesseract_brewstation_mashctrl_plant",
                ["plant_id"], ["id"],
            )


def downgrade():
    with op.batch_alter_table("tesseract_brewstation_mashctrl_layout") as batch_op:
        if _fk_exists("tesseract_brewstation_mashctrl_layout", "fk_mashctrl_layout_plant_id"):
            batch_op.drop_constraint("fk_mashctrl_layout_plant_id", type_="foreignkey")
        if _column_exists("tesseract_brewstation_mashctrl_layout", "plant_id"):
            batch_op.drop_column("plant_id")

    with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
        if _fk_exists("tesseract_brewstation_mashctrl_widget", "fk_mashctrl_widget_vessel_id"):
            batch_op.drop_constraint("fk_mashctrl_widget_vessel_id", type_="foreignkey")
        if _column_exists("tesseract_brewstation_mashctrl_widget", "vessel_id"):
            batch_op.drop_column("vessel_id")
