"""DRE gerencial: classificações, apropriações e reversões preservadas."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision='f82cad560b94'
down_revision='e71b9d45fa83'
branch_labels=depends_on=None


def definitions():
    meta=sa.MetaData()
    for name in ('treasury_category','treasury_cost_center'):
        sa.Table('tesseract_financeiro_'+name,meta,sa.Column('id',sa.Integer,primary_key=True))
    tables=[]
    tables.append(sa.Table('tesseract_financeiro_result_classification',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('category_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_category.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('version',sa.Integer,nullable=False),
        sa.Column('group_code',sa.String(30),nullable=False),
        sa.Column('valid_from',sa.Date,nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('category_id','version',name='uq_result_classification_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_result_classification_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_accrual_entry',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('source_key',sa.String(180),nullable=False),
        sa.Column('source_type',sa.String(15),nullable=False),
        sa.Column('source_id',sa.Integer,nullable=True),
        sa.Column('component',sa.String(20),nullable=True),
        sa.Column('reference',sa.String(120),nullable=False),
        sa.Column('classification_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_result_classification.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('effect',sa.String(12),nullable=False),
        sa.Column('amount',sa.String(64),nullable=False),
        sa.Column('currency_code',sa.String(3),nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_accrual_entry_0'),
    ))
    tables.append(sa.Table('tesseract_financeiro_accrual_allocation',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('entry_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_accrual_entry.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('period',sa.Date,nullable=False),
        sa.Column('cost_center_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_treasury_cost_center.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('amount',sa.String(64),nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
    ))
    tables.append(sa.Table('tesseract_financeiro_accrual_reversal',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('entry_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_accrual_entry.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('entry_id',name='uq_accrual_reversal_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_accrual_reversal_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_accrual_active',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('source_key',sa.String(180),nullable=False),
        sa.Column('entry_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_accrual_entry.id',ondelete='RESTRICT'),nullable=False),
        sa.UniqueConstraint('organization_code','source_key',name='uq_accrual_active_0'),
        sa.UniqueConstraint('entry_id',name='uq_accrual_active_1'),
    ))
    return tables


def upgrade():
    connection=op.get_bind(); inspector=sa.inspect(connection); tables=definitions();names=inspector.get_table_names()
    for table in tables:
        if table.name in names: validate_existing(inspector,table)
    for table in tables:
        if table.name not in names:table.create(connection)


def downgrade():
    connection=op.get_bind(); tables=list(reversed(definitions()));names=sa.inspect(connection).get_table_names()
    for table in tables:
        if table.name in names and connection.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve o histórico de competência/DRE.')
    for table in tables:
        if table.name in names:table.drop(connection)
