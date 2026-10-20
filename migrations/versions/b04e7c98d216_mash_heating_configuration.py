"""Heating preparation per vessel (sources, primary sensor, HLT/sparge)."""
from alembic import op
import sqlalchemy as sa

revision = "b04e7c98d216"
down_revision = "a93dbe671ca5"
branch_labels = depends_on = None
TABLE = "tesseract_brewstation_mashctrl_plant_vessel"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE):
        raise RuntimeError("Tabela de tanques ausente: aplique as migrations anteriores.")
    columns = {c["name"]: c for c in inspector.get_columns(TABLE)}
    if "heating_config_json" in columns and not isinstance(columns["heating_config_json"]["type"], sa.JSON):
        raise RuntimeError("heating_config_json existente tem tipo incompatível.")
    if "heating_version" in columns and (not isinstance(columns["heating_version"]["type"], sa.Integer) or columns["heating_version"]["nullable"]):
        raise RuntimeError("heating_version existente tem definição incompatível.")
    if "heating_config_json" not in columns:
        op.add_column(TABLE, sa.Column("heating_config_json", sa.JSON(), nullable=True))
    if "heating_version" not in columns:
        op.add_column(TABLE, sa.Column("heating_version", sa.Integer(), server_default="0", nullable=False))


def downgrade():
    connection = op.get_bind()
    columns = {c["name"] for c in sa.inspect(connection).get_columns(TABLE)}
    if "heating_version" in columns and connection.execute(sa.text(f'SELECT COUNT(*) FROM "{TABLE}" WHERE heating_version > 0')).scalar():
        raise RuntimeError("Downgrade bloqueado: preserve as configurações de aquecimento.")
    if "heating_config_json" in columns:
        table = sa.Table(TABLE, sa.MetaData(), autoload_with=connection)
        if any(value is not None for value in connection.execute(sa.select(table.c.heating_config_json)).scalars()):
            raise RuntimeError("Downgrade bloqueado: preserve as configurações de aquecimento.")
    with op.batch_alter_table(TABLE) as batch:
        for name in ("heating_version", "heating_config_json"):
            if name in columns:
                batch.drop_column(name)
