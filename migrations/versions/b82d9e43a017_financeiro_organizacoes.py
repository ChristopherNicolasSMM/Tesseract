"""Fundação financeira e cadastro ampliado; sem atribuir moeda/vínculos legados."""
from alembic import op
import sqlalchemy as sa
revision = 'b82d9e43a017'
down_revision = 'a71c8d32f906'
branch_labels = None
depends_on = None
PROFILE = {'legal_name': 200, 'trade_name': 120, 'cnpj': 14, 'state_registration': 40, 'municipal_registration': 40, 'email': 254, 'phone': 16, 'website': 250, 'cep': 8, 'logradouro': 200, 'numero': 20, 'complemento': 100, 'bairro': 100, 'cidade': 100, 'estado': 2, 'pais': 60}
ORG = 'tesseract_organization'
CONTACT = 'tesseract_organization_contact'
CURRENCY = 'tesseract_financeiro_currency'
POLICY = 'tesseract_financeiro_monetary_policy'


def tables():
    metadata = sa.MetaData()
    sa.Table(ORG, metadata, sa.Column('id', sa.Integer, primary_key=True))
    contacts = sa.Table(CONTACT, metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_id', sa.Integer, sa.ForeignKey(ORG + '.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('role', sa.String(80), nullable=False),
        sa.Column('cpf', sa.String(11)), sa.Column('email', sa.String(254)), sa.Column('phone', sa.String(16)),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()))
    currency = sa.Table(CURRENCY, metadata,
        sa.Column('code', sa.String(3), primary_key=True), sa.Column('name', sa.String(80), nullable=False),
        sa.Column('decimal_places', sa.Integer, nullable=False),
        sa.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_currency_scale'))
    policy = sa.Table(POLICY, metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_code', sa.String(40), nullable=False, unique=True),
        sa.Column('currency_code', sa.String(3), sa.ForeignKey(CURRENCY + '.code', ondelete='RESTRICT'), nullable=False),
        sa.Column('decimal_places', sa.Integer, nullable=False), sa.Column('rounding', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.CheckConstraint('decimal_places >= 0 AND decimal_places <= 6', name='ck_fin_policy_scale'),
        sa.CheckConstraint("rounding IN ('HALF_UP', 'HALF_EVEN')", name='ck_fin_policy_rounding'))
    return [contacts, currency, policy]


def validate_existing(inspector, table):
    actual = {column['name']: column for column in inspector.get_columns(table.name)}
    if set(actual) != set(table.columns.keys()):
        raise RuntimeError(f'Schema incompatível: {table.name}.')
    for column in table.columns:
        found = actual[column.name]
        if not isinstance(found['type'], type(column.type)) or found['nullable'] != column.nullable or (
                isinstance(column.type, sa.String) and found['type'].length != column.type.length):
            raise RuntimeError(f'Tipo/restrição incompatível: {table.name}.{column.name}.')
    if inspector.get_pk_constraint(table.name)['constrained_columns'] != [column.name for column in table.primary_key]:
        raise RuntimeError(f'Chave primária incompatível: {table.name}.')
    unique = [item['column_names'] for item in inspector.get_unique_constraints(table.name)]
    unique += [item['column_names'] for item in inspector.get_indexes(table.name) if item['unique']]
    for column in table.columns:
        if column.unique and [column.name] not in unique:
            raise RuntimeError(f'Unicidade incompatível: {table.name}.{column.name}.')
    foreign = inspector.get_foreign_keys(table.name)
    for fk in table.foreign_keys:
        if not any(item['constrained_columns'] == [fk.parent.name] and item['referred_table'] == fk.column.table.name and item['referred_columns'] == [fk.column.name] and item['options'].get('ondelete', '').upper() == 'RESTRICT' for item in foreign):
            raise RuntimeError(f'Referência incompatível: {table.name}.{fk.parent.name}.')
    expected_checks = [item for item in table.constraints if isinstance(item, sa.CheckConstraint)]
    actual_checks = {item['name']: item['sqltext'] for item in inspector.get_check_constraints(table.name)}
    def normalized(expression):
        return ''.join(char for char in str(expression).lower() if not char.isspace() and char not in '()')
    if any(item.name not in actual_checks or normalized(actual_checks[item.name]) != normalized(item.sqltext) for item in expected_checks):
        raise RuntimeError(f'CHECK ausente: {table.name}.')


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    present = set(inspector.get_table_names())
    if ORG not in present:
        raise RuntimeError('Execute primeiro a migration de organizações Core.')
    definitions = tables()
    # Validate every existing target before doing any DDL.
    for table in definitions:
        if table.name in present:
            validate_existing(inspector, table)
    columns = {column['name']: column for column in inspector.get_columns(ORG)}
    for name, limit in PROFILE.items():
        if name in columns and (not isinstance(columns[name]['type'], sa.String) or columns[name]['type'].length != limit or not columns[name]['nullable']):
            raise RuntimeError(f'Perfil de organização incompatível: {name}.')
    unique = [item['column_names'] for item in inspector.get_unique_constraints(ORG)]
    unique += [item['column_names'] for item in inspector.get_indexes(ORG) if item['unique']]
    if 'cnpj' in columns and ['cnpj'] not in unique:
        raise RuntimeError('CNPJ existente sem unicidade; revisão manual necessária.')
    missing = set(PROFILE) - set(columns)
    if missing:
        with op.batch_alter_table(ORG) as batch:
            for name, limit in PROFILE.items():
                if name in missing:
                    batch.add_column(sa.Column(name, sa.String(limit), nullable=True))
            if 'cnpj' in missing:
                batch.create_unique_constraint('uq_organization_cnpj', ['cnpj'])
    for table in definitions:
        if table.name not in present:
            table.create(bind=connection)


def downgrade():
    connection = op.get_bind()
    present = set(sa.inspect(connection).get_table_names())
    for name in (CONTACT, CURRENCY, POLICY):
        if name in present and connection.execute(sa.text(f'SELECT COUNT(*) FROM {name}')).scalar():
            raise RuntimeError('Downgrade bloqueado: dados financeiros/cadastrais devem ser preservados.')
    columns = {column['name'] for column in sa.inspect(connection).get_columns(ORG)} if ORG in present else set()
    profile = set(PROFILE) & columns
    if profile and connection.execute(sa.text('SELECT COUNT(*) FROM ' + ORG + ' WHERE ' + ' OR '.join(name + ' IS NOT NULL' for name in profile))).scalar():
        raise RuntimeError('Downgrade bloqueado: perfil da organização deve ser preservado.')
    for name in (POLICY, CURRENCY, CONTACT):
        if name in present:
            op.drop_table(name)
    if profile:
        from migrations.schema_compat import drop_columns_with_references
        drop_columns_with_references(op, ORG, sorted(profile))
