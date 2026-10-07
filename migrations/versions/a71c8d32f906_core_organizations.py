"""Identidade Core de organizações; sem preencher vínculo ou moeda legada."""
from alembic import op
import sqlalchemy as sa
revision = 'a71c8d32f906'
down_revision = 'f8c214ab709e'
branch_labels = None
depends_on = None
TABLE = 'tesseract_organization'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE in inspector.get_table_names():
        reflected = {c['name']: c for c in inspector.get_columns(TABLE)}
        columns = set(reflected)
        unique = [c['column_names'] for c in inspector.get_unique_constraints(TABLE)]
        unique += [c['column_names'] for c in inspector.get_indexes(TABLE) if c['unique']]
        if columns != {'id', 'code', 'name', 'is_active', 'created_at', 'updated_at'} or ['code'] not in unique:
            raise RuntimeError('Schema de organização incompatível; nenhuma adaptação automática foi aplicada.')
        expected = {'id': sa.Integer, 'code': sa.String, 'name': sa.String,
                    'is_active': sa.Boolean, 'created_at': sa.DateTime, 'updated_at': sa.DateTime}
        if any(not isinstance(reflected[name]['type'], kind) for name, kind in expected.items()) or any(
                reflected[name]['nullable'] for name in columns - {'id'}) or not reflected['id']['primary_key'] or (
                reflected['code']['type'].length != 40 or reflected['name']['type'].length != 120):
            raise RuntimeError('Tipos ou restrições de organização incompatíveis.')
        return
    op.create_table(TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(40), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))


def downgrade():
    if TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    if op.get_bind().execute(sa.text(f'SELECT COUNT(*) FROM {TABLE}')).scalar():
        raise RuntimeError('Downgrade bloqueado: organizações existentes devem ser preservadas.')
    op.drop_table(TABLE)
