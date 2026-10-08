"""Versões monetárias explícitas; política inicial/snapshots legados preservados."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'e15a2b76d340'
down_revision = 'd04f1a65c239'
branch_labels = None
depends_on = None
NAME = 'tesseract_financeiro_policy_version'


def table_definition():
    metadata = sa.MetaData()
    sa.Table('tesseract_financeiro_monetary_policy', metadata, sa.Column('id', sa.Integer, primary_key=True))
    return sa.Table(NAME, metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('policy_id', sa.Integer, sa.ForeignKey('tesseract_financeiro_monetary_policy.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('version_number', sa.Integer, nullable=False), sa.Column('decimal_places', sa.Integer, nullable=False),
        sa.Column('rounding', sa.String(16), nullable=False), sa.Column('valid_from', sa.Date, nullable=False),
        sa.Column('reason', sa.String(200), nullable=False), sa.Column('created_by', sa.String(120), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('policy_id', 'version_number', name='uq_fin_policy_version_number'),
        sa.CheckConstraint('version_number >= 2', name='ck_fin_policy_version_number'),
        sa.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_policy_version_scale'),
        sa.CheckConstraint("rounding IN ('HALF_UP', 'HALF_EVEN')", name='ck_fin_policy_version_rounding'))


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    present = set(inspector.get_table_names())
    if 'tesseract_financeiro_monetary_policy' not in present:
        raise RuntimeError('Execute a fundação financeira antes das versões monetárias.')
    table = table_definition()
    if NAME in present:
        validate_existing(inspector, table)
        uniques = [item['column_names'] for item in inspector.get_unique_constraints(NAME)]
        uniques += [item['column_names'] for item in inspector.get_indexes(NAME) if item['unique']]
        if ['policy_id', 'version_number'] not in uniques:
            raise RuntimeError('Schema incompatível: versões sem unicidade por política.')
    else:
        table.create(conn)


def downgrade():
    conn = op.get_bind()
    if not sa.inspect(conn).has_table(NAME):
        return
    if conn.execute(sa.text(f'SELECT COUNT(*) FROM {NAME}')).scalar():
        raise RuntimeError('Downgrade bloqueado: versões monetárias devem ser preservadas.')
    op.drop_table(NAME)
