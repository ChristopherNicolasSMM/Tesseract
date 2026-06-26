"""promove feature_device_manager a addon_device_manager (rename tabelas
tesseract_brewstation_dvm_* -> tesseract_dvm_*) e remove FKs cross-Addon
de feature_mash_control (sensor_function_id/actor_function_id/
device_function_id -> *_function_name, referencia fraca, skill 02)

Ver docs/skills/05-proposta-addon-device-manager-e-mqtt.md para o histórico
completo da decisao.

Revision ID: 4a8524f00549
Revises: 091f87025ce4
Create Date: 2026-06-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a8524f00549'
down_revision = '091f87025ce4'
branch_labels = None
depends_on = None


# Tabelas do antigo prefixo tri-nivel (Feature dentro de addon_brewstation)
# para o novo prefixo de Addon (dois niveis, sem o addon pai) - skill 02.
_TABLE_RENAMES = [
    ("tesseract_brewstation_dvm_function", "tesseract_dvm_function"),
    ("tesseract_brewstation_dvm_device", "tesseract_dvm_device"),
    ("tesseract_brewstation_dvm_actor", "tesseract_dvm_actor"),
    ("tesseract_brewstation_dvm_emulated_device", "tesseract_dvm_emulated_device"),
]


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # ── Passo 1: renomear as 4 tabelas do device_manager promovido ──────
    for old_name, new_name in _TABLE_RENAMES:
        if _table_exists(old_name) and not _table_exists(new_name):
            op.rename_table(old_name, new_name)

    # ── Passo 2: rule (automation_rule) — sensor/actor_function_id -> name ──
    if _table_exists("tesseract_brewstation_mashctrl_rule"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_rule") as batch_op:
            batch_op.add_column(sa.Column("sensor_function_name", sa.String(100), nullable=True))
            batch_op.add_column(sa.Column("actor_function_name", sa.String(100), nullable=True))

        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_rule
            SET sensor_function_name = (
                SELECT name FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.id = tesseract_brewstation_mashctrl_rule.sensor_function_id
            )
        """)
        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_rule
            SET actor_function_name = (
                SELECT name FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.id = tesseract_brewstation_mashctrl_rule.actor_function_id
            )
        """)

        with op.batch_alter_table("tesseract_brewstation_mashctrl_rule") as batch_op:
            batch_op.alter_column("sensor_function_name", nullable=False)
            batch_op.alter_column("actor_function_name", nullable=False)
            batch_op.drop_column("sensor_function_id")
            batch_op.drop_column("actor_function_id")

    # ── Passo 3: widget (dashboard_widget) — device_function_id -> name (nullable) ──
    if _table_exists("tesseract_brewstation_mashctrl_widget"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
            batch_op.add_column(sa.Column("device_function_name", sa.String(100), nullable=True))

        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_widget
            SET device_function_name = (
                SELECT name FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.id = tesseract_brewstation_mashctrl_widget.device_function_id
            )
            WHERE device_function_id IS NOT NULL
        """)

        with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
            batch_op.drop_column("device_function_id")

    # ── Passo 4: plant_mapping (brew_plant_mapping) — device_function_id -> name ──
    if _table_exists("tesseract_brewstation_mashctrl_plant_mapping"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_plant_mapping") as batch_op:
            batch_op.add_column(sa.Column("device_function_name", sa.String(100), nullable=True))

        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_plant_mapping
            SET device_function_name = (
                SELECT name FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.id = tesseract_brewstation_mashctrl_plant_mapping.device_function_id
            )
        """)

        with op.batch_alter_table("tesseract_brewstation_mashctrl_plant_mapping") as batch_op:
            batch_op.alter_column("device_function_name", nullable=False)
            batch_op.drop_column("device_function_id")


def downgrade():
    # Downgrade best-effort - restaura colunas *_id (perde resolucao por
    # nome se o registro de DeviceFunction correspondente tiver sido
    # apagado/renomeado entre o upgrade e o downgrade).
    if _table_exists("tesseract_brewstation_mashctrl_plant_mapping"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_plant_mapping") as batch_op:
            batch_op.add_column(sa.Column("device_function_id", sa.Integer(), nullable=True))
        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_plant_mapping
            SET device_function_id = (
                SELECT id FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.name = tesseract_brewstation_mashctrl_plant_mapping.device_function_name
            )
        """)
        with op.batch_alter_table("tesseract_brewstation_mashctrl_plant_mapping") as batch_op:
            batch_op.drop_column("device_function_name")

    if _table_exists("tesseract_brewstation_mashctrl_widget"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
            batch_op.add_column(sa.Column("device_function_id", sa.Integer(), nullable=True))
        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_widget
            SET device_function_id = (
                SELECT id FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.name = tesseract_brewstation_mashctrl_widget.device_function_name
            )
            WHERE device_function_name IS NOT NULL
        """)
        with op.batch_alter_table("tesseract_brewstation_mashctrl_widget") as batch_op:
            batch_op.drop_column("device_function_name")

    if _table_exists("tesseract_brewstation_mashctrl_rule"):
        with op.batch_alter_table("tesseract_brewstation_mashctrl_rule") as batch_op:
            batch_op.add_column(sa.Column("sensor_function_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("actor_function_id", sa.Integer(), nullable=True))
        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_rule
            SET sensor_function_id = (
                SELECT id FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.name = tesseract_brewstation_mashctrl_rule.sensor_function_name
            )
        """)
        op.execute("""
            UPDATE tesseract_brewstation_mashctrl_rule
            SET actor_function_id = (
                SELECT id FROM tesseract_dvm_function
                WHERE tesseract_dvm_function.name = tesseract_brewstation_mashctrl_rule.actor_function_name
            )
        """)
        with op.batch_alter_table("tesseract_brewstation_mashctrl_rule") as batch_op:
            batch_op.drop_column("sensor_function_name")
            batch_op.drop_column("actor_function_name")

    for old_name, new_name in _TABLE_RENAMES:
        if _table_exists(new_name) and not _table_exists(old_name):
            op.rename_table(new_name, old_name)
