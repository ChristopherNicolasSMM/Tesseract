"""Taxas e snapshots de conversão; sem backfill de valores antigos."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'd04f1a65c239'
down_revision = 'c93e0f54b128'
branch_labels = None
depends_on = None


def tables():
    metadata = sa.MetaData()
    sa.Table('tesseract_financeiro_currency', metadata, sa.Column('code', sa.String(3), primary_key=True))
    rate = sa.Table('tesseract_financeiro_exchange_rate', metadata,
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('organization_code', sa.String(40), nullable=False),
        sa.Column('source_currency', sa.String(3), sa.ForeignKey('tesseract_financeiro_currency.code', ondelete='RESTRICT'), nullable=False),
        sa.Column('target_currency', sa.String(3), sa.ForeignKey('tesseract_financeiro_currency.code', ondelete='RESTRICT'), nullable=False),
        sa.Column('rate', sa.String(31), nullable=False), sa.Column('valid_on', sa.Date, nullable=False),
        sa.Column('source', sa.String(120), nullable=False), sa.Column('rate_type', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False), sa.Column('created_by', sa.String(120), nullable=False),
        sa.CheckConstraint('source_currency <> target_currency', name='ck_fin_rate_pair'),
        sa.CheckConstraint("rate_type IN ('MANUAL', 'CONTRACTUAL')", name='ck_fin_rate_type'))
    conversion = sa.Table('tesseract_financeiro_conversion', metadata,
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('organization_code', sa.String(40), nullable=False),
        sa.Column('idempotency_key', sa.String(80), nullable=False), sa.Column('reference', sa.String(120), nullable=False),
        sa.Column('snapshot', sa.Text, nullable=False), sa.Column('created_by', sa.String(120), nullable=False), sa.Column('created_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_conversion_key'))
    return rate, conversion


def upgrade():
    conn = op.get_bind(); inspector = sa.inspect(conn); present = set(inspector.get_table_names())
    if 'tesseract_financeiro_monetary_policy' not in present: raise RuntimeError('Execute a fundação financeira antes do câmbio.')
    definitions = tables()
    for table in definitions:
        if table.name in present:
            validate_existing(inspector, table)
            if table.name.endswith('_conversion') and not any(item['column_names'] == ['organization_code', 'idempotency_key'] for item in inspector.get_unique_constraints(table.name)):
                raise RuntimeError('Schema incompatível: chave de idempotência sem unicidade.')
    for table in definitions:
        if table.name not in present: table.create(conn)


def downgrade():
    conn = op.get_bind(); present = set(sa.inspect(conn).get_table_names())
    names = [table.name for table in tables()]
    for name in names:
        if name in present and conn.execute(sa.text(f'SELECT COUNT(*) FROM {name}')).scalar(): raise RuntimeError('Downgrade bloqueado: histórico de câmbio deve ser preservado.')
    for name in reversed(names):
        if name in present: op.drop_table(name)
