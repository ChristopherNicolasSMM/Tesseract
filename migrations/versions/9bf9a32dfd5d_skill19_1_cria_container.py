"""skill 19 (1/6) - cria tesseract_brewstation_yeastbank_container

Ver docs/skills/19-proposta-reestruturacao-yeast-bank-container.md para
o plano completo em 6 passos. Este passo só cria a tabela nova — nenhum
dado é tocado ainda (passo 2 faz o backfill).

Revision ID: 9bf9a32dfd5d
Revises: aa7341e86ae3
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bf9a32dfd5d'
down_revision = 'aa7341e86ae3'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_container'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou esta tabela
    # (boot antes do primeiro `flask db upgrade`), create_table falha
    # como "already exists" sem esta checagem.
    if not _table_exists(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('container_type', sa.String(40), nullable=False, server_default='Caixa'),
            sa.Column(
                'device_id', sa.Integer(),
                sa.ForeignKey('tesseract_brewstation_yeastbank_storage_device.id'),
                nullable=False,
            ),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )


def downgrade():
    if _table_exists(_TABLE):
        op.drop_table(_TABLE)
