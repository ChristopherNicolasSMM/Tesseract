"""Dashboard/custos/fechamento gerencial e reparo de FK duplicada do Model Builder."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
from migrations.sqlite_foreign_keys import repair_model_builder_foreign_keys
revision='a93dbe671ca5'
down_revision='f82cad560b94'
branch_labels=depends_on=None


def definitions():
    meta=sa.MetaData();tables=[]
    tables.append(sa.Table('tesseract_financeiro_result_close',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('period',sa.Date,nullable=False),
        sa.Column('version',sa.Integer,nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('snapshot_json',sa.Text,nullable=False),
        sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('organization_code','period','version',name='uq_result_close_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_result_close_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_result_reopen',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('close_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_result_close.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('idempotency_key',sa.String(80),nullable=False),
        sa.Column('request_json',sa.Text,nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('close_id',name='uq_result_reopen_0'),
        sa.UniqueConstraint('organization_code','idempotency_key',name='uq_result_reopen_1'),
    ))
    tables.append(sa.Table('tesseract_financeiro_result_close_active',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_code',sa.String(40),nullable=False),
        sa.Column('period',sa.Date,nullable=False),
        sa.Column('close_id',sa.Integer,sa.ForeignKey('tesseract_financeiro_result_close.id',ondelete='RESTRICT'),nullable=False),
        sa.UniqueConstraint('organization_code','period',name='uq_result_close_active_0'),
        sa.UniqueConstraint('close_id',name='uq_result_close_active_1'),
    ))
    return tables


def upgrade():
    connection=op.get_bind();inspector=sa.inspect(connection);tables=definitions();names=inspector.get_table_names()
    for table in tables:
        if table.name in names:validate_existing(inspector,table)
    repair_model_builder_foreign_keys(op)
    for table in tables:
        if table.name not in names:table.create(connection)


def downgrade():
    connection=op.get_bind();tables=list(reversed(definitions()));names=sa.inspect(connection).get_table_names()
    for table in tables:
        if table.name in names and connection.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve os fechamentos gerenciais.')
    for table in tables:
        if table.name in names:table.drop(connection)
    # O reparo de FK duplicada não é revertido: não recriar um defeito no Core.
