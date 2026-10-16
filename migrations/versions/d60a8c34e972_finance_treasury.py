"""Tesouraria, títulos, parcelas e liquidações com histórico preservado."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'd60a8c34e972'
down_revision = 'c59f7a23d861'
branch_labels = depends_on = None
PREFIX = 'tesseract_financeiro_treasury_'


def definitions():
    meta = sa.MetaData()
    def col(name, type_, nullable=False, **kwargs): return sa.Column(name, type_, nullable=nullable, **kwargs)
    def pk(): return col('id', sa.Integer, primary_key=True)
    def org(): return col('organization_code', sa.String(40))
    def audit(): return [col('created_by', sa.String(120)), col('created_at', sa.DateTime)]
    def fk(name, table, *, nullable=False, unique=False):
        return sa.Column(name, sa.Integer, sa.ForeignKey(PREFIX + table + '.id', ondelete='RESTRICT'), nullable=nullable, unique=unique)
    def table(name, *columns): return sa.Table(PREFIX + name, meta, *columns)
    accounts = table('account', pk(), org(), col('name', sa.String(100)), col('kind', sa.String(10)), col('currency_code', sa.String(3)),
        col('bank_name', sa.String(100), True), col('branch', sa.String(30), True), col('account_number', sa.String(40), True),
        col('opening_date', sa.Date), col('balance', sa.String(64)), col('opening_json', sa.Text),
        col('is_active', sa.Boolean), col('version', sa.Integer), *audit(),
        sa.UniqueConstraint('organization_code', 'name', name='uq_fin_account_name'),
        sa.CheckConstraint("kind IN ('BANK','CASH')", name='ck_fin_account_kind'))
    categories = table('category', pk(), org(), col('name', sa.String(100)), col('direction', sa.String(12)),
        col('is_active', sa.Boolean), col('version', sa.Integer), *audit(),
        sa.UniqueConstraint('organization_code', 'name', name='uq_fin_category_name'),
        sa.CheckConstraint("direction IN ('PAYABLE','RECEIVABLE')", name='ck_fin_category_direction'))
    centers = table('cost_center', pk(), org(), col('name', sa.String(100)), col('is_active', sa.Boolean), col('version', sa.Integer), *audit(),
        sa.UniqueConstraint('organization_code', 'name', name='uq_fin_center_name'))
    titles = table('title', pk(), org(), col('kind', sa.String(12)), col('reference', sa.String(120)), col('counterparty', sa.String(200)),
        col('currency_code', sa.String(3)), col('amount', sa.String(64)), col('base_amount', sa.String(64)), col('issue_date', sa.Date),
        fk('category_id', 'category'), fk('cost_center_id', 'cost_center'), col('source_reference', sa.String(80), True, unique=True),
        col('idempotency_key', sa.String(80)), col('request_json', sa.Text), col('snapshot_json', sa.Text), *audit(),
        sa.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_title_key'),
        sa.CheckConstraint("kind IN ('PAYABLE','RECEIVABLE')", name='ck_fin_title_kind'))
    installments = table('installment', pk(), fk('title_id', 'title'), col('number', sa.Integer), col('due_date', sa.Date),
        col('amount', sa.String(64)), col('base_amount', sa.String(64)),
        sa.UniqueConstraint('title_id', 'number', name='uq_fin_installment_number'))
    settlements = table('settlement', pk(), org(), fk('installment_id', 'installment'), fk('account_id', 'account'),
        col('principal', sa.String(64)), col('carrying_base', sa.String(64)), col('cash_base', sa.String(64)), col('operation_date', sa.Date),
        col('idempotency_key', sa.String(80)), col('request_json', sa.Text), col('snapshot_json', sa.Text), *audit(),
        sa.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_settlement_key'))
    reversals = table('reversal', pk(), fk('settlement_id', 'settlement', unique=True), org(), col('operation_date', sa.Date),
        col('reason', sa.String(1000)), col('idempotency_key', sa.String(80)), *audit(),
        sa.UniqueConstraint('organization_code', 'idempotency_key', name='uq_fin_reversal_key'))
    cancellations = table('cancellation', sa.Column('title_id', sa.Integer, sa.ForeignKey(PREFIX + 'title.id', ondelete='RESTRICT'), primary_key=True),
        col('reason', sa.String(1000)), *audit())
    movements = table('movement', pk(), fk('account_id', 'account'), col('reference', sa.String(80)), col('amount_delta', sa.String(64)),
        col('balance_after', sa.String(64)), col('operation_date', sa.Date), col('snapshot_json', sa.Text), *audit(),
        sa.UniqueConstraint('account_id', 'reference', name='uq_fin_movement_reference'))
    return [accounts, categories, centers, titles, installments, settlements, reversals, cancellations, movements]


def upgrade():
    connection = op.get_bind(); inspector = sa.inspect(connection); tables = definitions()
    names = inspector.get_table_names()
    for table in tables:
        if table.name in names: validate_existing(inspector, table)
    for table in tables:
        if table.name not in names: table.create(connection)


def downgrade():
    connection = op.get_bind(); tables = list(reversed(definitions())); names = sa.inspect(connection).get_table_names()
    for table in tables:
        if table.name in names and connection.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve cadastros e histórico da tesouraria.')
    for table in tables:
        if table.name in names: op.drop_table(table.name)
