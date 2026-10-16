"""Vínculo produtivo sem reatribuição histórica."""
from alembic import op
import sqlalchemy as sa
from migrations.versions.b82d9e43a017_financeiro_organizacoes import validate_existing
revision = 'c59f7a23d861'
down_revision = 'e59f6ab8d704'
branch_labels = depends_on = None


def definitions():
    meta = sa.MetaData()
    sa.Table('tesseract_brewstation_mashctrl_session', meta, sa.Column('id', sa.Integer, primary_key=True))
    tables = []
    for suffix in ('organization', 'consumption'):
        columns = [sa.Column('session_id', sa.Integer, sa.ForeignKey('tesseract_brewstation_mashctrl_session.id', ondelete='RESTRICT'), primary_key=True),
                   sa.Column('snapshot_json', sa.Text, nullable=False), sa.Column('created_at', sa.DateTime, nullable=False)]
        if suffix == 'organization':
            columns += [sa.Column('organization_code', sa.String(40), nullable=False), sa.Column('created_by', sa.String(120), nullable=False)]
        tables.append(sa.Table('tesseract_brewstation_mashctrl_production_' + suffix, meta, *columns))
    return tables


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = definitions()
    for table in tables:
        if table.name in inspector.get_table_names():
            validate_existing(inspector, table)
    for table in tables:
        if table.name not in inspector.get_table_names():
            table.create(connection)


def downgrade():
    connection = op.get_bind()
    tables = list(reversed(definitions()))
    for table in tables:
        if table.name in sa.inspect(connection).get_table_names() and connection.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            raise RuntimeError('Downgrade bloqueado: preserve os vínculos/custos produtivos.')
    for table in tables:
        if table.name in sa.inspect(connection).get_table_names():
            op.drop_table(table.name)
