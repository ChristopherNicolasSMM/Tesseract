"""Catálogo de Relatórios; preserva tabelas compatíveis criadas no boot."""
from alembic import op
import sqlalchemy as sa

revision = 'c93e0f54b128'
down_revision = 'b82d9e43a017'
branch_labels = None
depends_on = None


def tables():
    metadata = sa.MetaData()
    sa.Table('tesseract_user', metadata, sa.Column('id', sa.Integer, primary_key=True))
    template = sa.Table('tesseract_reports_report_template', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('active_version_number', sa.Integer),
        sa.Column('is_deleted', sa.Boolean, nullable=False),
        sa.Column('deleted_at', sa.DateTime),
        sa.Column('created_by_user_id', sa.Integer, sa.ForeignKey('tesseract_user.id')),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False))
    version = sa.Table('tesseract_reports_report_template_version', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('template_id', sa.Integer, sa.ForeignKey(template.c.id), nullable=False),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('lock_version', sa.Integer, nullable=False),
        sa.Column('layout_json', sa.JSON, nullable=False),
        sa.Column('data_schema_json', sa.JSON, nullable=False),
        sa.Column('sample_data_json', sa.JSON, nullable=False),
        sa.Column('content_hash', sa.String(64)),
        sa.Column('published_at', sa.DateTime),
        sa.Column('created_by_user_id', sa.Integer, sa.ForeignKey('tesseract_user.id')),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('template_id', 'version_number', name='uq_reports_revision'),
        sa.CheckConstraint("status IN ('draft', 'published')", name='ck_reports_revision_status'))
    parameter = sa.Table('tesseract_reports_report_parameter', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('version_id', sa.Integer, sa.ForeignKey(version.c.id), nullable=False),
        sa.Column('key', sa.String(80), nullable=False),
        sa.Column('label', sa.String(120), nullable=False),
        sa.Column('schema_json', sa.JSON, nullable=False),
        sa.Column('is_required', sa.Boolean, nullable=False),
        sa.Column('has_default', sa.Boolean, nullable=False),
        sa.Column('default_json', sa.JSON),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('version_id', 'key', name='uq_reports_parameter'))
    return [template, version, parameter]


def validate_existing(inspector, table):
    actual = {column['name']: column for column in inspector.get_columns(table.name)}
    if set(actual) != set(table.c.keys()):
        raise RuntimeError(f'Schema incompatível: {table.name}')
    for column in table.c:
        found = actual[column.name]
        if (not isinstance(found['type'], type(column.type)) or found['nullable'] != column.nullable
                or getattr(found['type'], 'length', None) != getattr(column.type, 'length', None)):
            raise RuntimeError(f'Coluna incompatível: {table.name}.{column.name}')
    if inspector.get_pk_constraint(table.name)['constrained_columns'] != ['id']:
        raise RuntimeError(f'PK incompatível: {table.name}')
    unique = {tuple(item['column_names']) for item in inspector.get_unique_constraints(table.name)}
    required = {tuple(c.name for c in constraint.columns) for constraint in table.constraints
                if isinstance(constraint, sa.UniqueConstraint)}
    if not required <= unique:
        raise RuntimeError(f'Unicidade incompatível: {table.name}')
    existing_fks = {(tuple(fk['constrained_columns']), fk['referred_table'], tuple(fk['referred_columns']))
                    for fk in inspector.get_foreign_keys(table.name)}
    for fk in table.foreign_keys:
        if ((fk.parent.name,), fk.column.table.name, (fk.column.name,)) not in existing_fks:
            raise RuntimeError(f'FK incompatível: {table.name}.{fk.parent.name}')
    if table.name.endswith('_version'):
        checks = inspector.get_check_constraints(table.name)
        if not any(c['name'] == 'ck_reports_revision_status' and
                   'draft' in c['sqltext'] and 'published' in c['sqltext'] for c in checks):
            raise RuntimeError(f'CHECK incompatível: {table.name}')


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    definitions = tables()
    # Validar tudo antes de criar qualquer tabela; não mascarar schema divergente.
    for table in definitions:
        if table.name in existing:
            validate_existing(inspector, table)
    for table in definitions:
        if table.name not in existing:
            table.create(bind)


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(tables()):
        if table.name in existing:
            op.drop_table(table.name)
