"""Fluxo, transferências e conciliação; sem movimentar dados legados."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'e71b9d45fa83'
down_revision = 'd60a8c34e972'
branch_labels = depends_on = None


def definitions():
    meta=sa.MetaData()
    # Foreign metadata stubs only; these existing tables are never created here.
    for name in ('treasury_account','treasury_movement'):
        sa.Table('tesseract_financeiro_'+name,meta,sa.Column('id',sa.Integer,primary_key=True))
    tables=[]
    tables.append(sa.Table('tesseract_financeiro_cash_transfer',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('source_account_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_account.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('destination_account_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_account.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('amount',sa.String(64),nullable=False),
        sa.Column('operation_date',sa.Date,nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_cash_transfer_0'),
    ))
    tables.append(sa.Table('tesseract_financeiro_cash_transfer_reversal',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('transfer_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_cash_transfer.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('operation_date',sa.Date,nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('transfer_id',name='uq_cash_transfer_reversal_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_cash_transfer_reversal_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_bank_statement',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('account_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_account.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('currency_code',sa.String(3),nullable=False),
        sa.Column('reference',sa.String(120),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_bank_statement_0'),
    ))
    tables.append(sa.Table('tesseract_financeiro_bank_statement_line',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('statement_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_bank_statement.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('account_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_account.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('external_id',sa.String(120),nullable=False),
        sa.Column('operation_date',sa.Date,nullable=False),
        sa.Column('amount',sa.String(64),nullable=False),
        sa.Column('description',sa.String(1000),nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('account_id','external_id',name='uq_bank_statement_line_0'),
    ))
    tables.append(sa.Table('tesseract_financeiro_bank_reconciliation',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('account_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_account.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('line_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_bank_statement_line.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('movement_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_movement.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_bank_reconciliation_0'),
    ))
    tables.append(sa.Table('tesseract_financeiro_bank_reconciliation_undo',meta,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('reconciliation_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_bank_reconciliation.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('reconciliation_id',name='uq_bank_reconciliation_undo_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_bank_reconciliation_undo_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_bank_reconciliation_active',meta,
        sa.Column('line_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_bank_statement_line.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('movement_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_movement.id',ondelete='RESTRICT'),nullable=False,unique=True),
        sa.Column('reconciliation_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_bank_reconciliation.id',ondelete='RESTRICT'),nullable=False,unique=True)))
    return tables


def upgrade():
    connection=op.get_bind(); inspector=sa.inspect(connection); tables=definitions()
    names=inspector.get_table_names()
    for table in tables:
        if table.name in names: validate_existing(inspector,table)
    for table in tables:
        if table.name not in names: table.create(connection)


def downgrade():
    connection=op.get_bind(); tables=list(reversed(definitions())); names=sa.inspect(connection).get_table_names()
    for table in tables:
        if table.name in names and connection.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve o histórico de transferências e conciliação.')
    for table in tables:
        if table.name in names: table.drop(connection)
