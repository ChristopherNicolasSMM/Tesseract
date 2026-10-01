"""Protege registro de envase contra repetição de requisição.

Revision ID: e6274a913bc0
Revises: d5a81c4e09f2
"""
from alembic import op
import sqlalchemy as sa

revision = "e6274a913bc0"
down_revision = "d5a81c4e09f2"
branch_labels = None
depends_on = None
_TABLE = "tesseract_brewstation_env_envase"
_INDEX = "uq_brewstation_envase_request_key"


def upgrade():
    # create_all não altera tabelas antigas; conferir a coluna E o índice.
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(_TABLE)}
    if "idempotency_key" not in columns:
        with op.batch_alter_table(_TABLE) as batch:
            batch.add_column(sa.Column("idempotency_key", sa.String(32), nullable=True))
    indexes = sa.inspect(op.get_bind()).get_indexes(_TABLE)
    if not any(item["name"] == _INDEX for item in indexes):
        op.create_index(_INDEX, _TABLE, ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index(_INDEX, table_name=_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_column("idempotency_key")
