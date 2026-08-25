"""skill 22 (3/3) - remove tesseract_brewstation_yeastbank_starter_log
(fundida em bank_event nos passos 1-2)

Último passo — só roda depois que os passos 1/3 e 2/3 já migraram
qualquer dado real de starter_log pra dentro de bank_event.

Ver docs/skills/22-fusao-starter-bankevent-neubauer.md.

Revision ID: da6e6b8c5522
Revises: 27c13496373e
Create Date: 2026-08-24 00:00:00.000002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da6e6b8c5522'
down_revision = '27c13496373e'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_starter_log'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    if _table_exists(_TABLE):
        op.drop_table(_TABLE)


def downgrade():
    # Best-effort: recria o schema (dado histórico já foi migrado pra
    # bank_event no passo 1/3 — não volta pra cá automaticamente).
    if not _table_exists(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'bank_item_id', sa.Integer(),
                sa.ForeignKey('tesseract_brewstation_yeastbank_bank_item.id'),
                nullable=False,
            ),
            sa.Column('brew_date', sa.Date(), nullable=True),
            sa.Column('start_date', sa.Date(), nullable=True),
            sa.Column('target_volume_l', sa.Float(), nullable=True),
            sa.Column('objective', sa.String(30), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='planned'),
            sa.Column('result_viability_percent', sa.Float(), nullable=True),
            sa.Column('contamination_detected', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
