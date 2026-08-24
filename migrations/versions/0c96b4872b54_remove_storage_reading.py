"""remove tesseract_brewstation_yeastbank_reading (skill 21)

Decisao do Christopher (2026-08-24): "seria util em etapa de
fermentacao, nao e o caso aqui" - o historico de temperatura solto
nunca teve consumidor real (achado da auditoria de campos, BACKLOG
Fase 18); YeastStorageDevice.current_temperature_c/last_temperature_at
continuam existindo como cache do ultimo valor.

Achado real ao validar esta migration: o __tablename__ original do
model era o nome curto "reading" (nao "storage_reading" como o nome
do arquivo/classe sugeria) - a tabela real e
tesseract_brewstation_yeastbank_reading. Confirmado via
`git show HEAD:.../yeast_storage_reading.py` antes de escrever esta
migration definitiva (a primeira tentativa usou o nome errado por
suposicao a partir do nome do arquivo, sem checar o __tablename__
real - corrigido antes de aplicar em qualquer ambiente real).

Ver docs/skills/21-tela-integrada-navegacao-unificacao-evento-starter-contagem.md.

Revision ID: 0c96b4872b54
Revises: 35b59cb8c0ee
Create Date: 2026-08-24 00:00:00.000002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c96b4872b54'
down_revision = '35b59cb8c0ee'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_reading'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    if _table_exists(_TABLE):
        op.drop_table(_TABLE)


def downgrade():
    # Best-effort: recria o schema (dado histórico não é recuperável
    # a partir daqui — a tabela em si já não existe mais no código).
    if not _table_exists(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'device_id', sa.Integer(),
                sa.ForeignKey('tesseract_brewstation_yeastbank_storage_device.id'),
                nullable=True,
            ),
            sa.Column('recorded_at', sa.DateTime(), nullable=True),
            sa.Column('temperature_c', sa.Float(), nullable=False),
            sa.Column('humidity_percent', sa.Float(), nullable=True),
            sa.Column('source_type', sa.String(30), nullable=True),
            sa.Column('source_ref', sa.String(120), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
