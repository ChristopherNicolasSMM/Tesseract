"""Normaliza TipoProduto antigo (nome) para descricao/codigo.

Revision ID: ee29a41c68f2
Revises: 6abac6de2f17
"""
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = 'ee29a41c68f2'
down_revision = '6abac6de2f17'
branch_labels = None
depends_on = None

TABLE = 'tesseract_estoque_tipo_produto'
CODES = {
    'Insumo': 'INSUMO',
    'Embalagem': 'EMBALAGEM',
    'Produto Acabado': 'PRODUTO_ACABADO',
    'Peça': 'PECA',
    'Uso e Consumo': 'USO_E_CONSUMO',
}


def _columns():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return None
    return {column['name']: column for column in inspector.get_columns(TABLE)}


def _has_unique(columns):
    inspector = sa.inspect(op.get_bind())
    expected = list(columns)
    constraints = inspector.get_unique_constraints(TABLE)
    indexes = [index for index in inspector.get_indexes(TABLE) if index.get('unique')]
    return any(list(item.get('column_names') or []) == expected
               for item in constraints + indexes)


def _code(description, row_id, used):
    base = CODES.get(description)
    if not base:
        ascii_name = unicodedata.normalize('NFKD', description or '').encode('ascii', 'ignore').decode('ascii')
        base = re.sub(r'[^A-Z0-9]+', '_', ascii_name.upper()).strip('_')[:20] or f'TIPO_{row_id}'
    code = base[:20]
    suffix = 2
    while code in used:
        ending = f'_{suffix}'
        code = base[:20 - len(ending)] + ending
        suffix += 1
    return code


def upgrade():
    columns = _columns()
    if columns is None:
        return
    bind = op.get_bind()
    sqlite = bind.dialect.name == 'sqlite'
    if 'descricao' not in columns:
        if 'nome' not in columns:
            raise RuntimeError(f'{TABLE}: nem nome nem descricao existem; revise o esquema')
        if sqlite:
            # RENAME COLUMN nao recria a tabela referenciada por Categoria.
            op.execute(sa.text(f'ALTER TABLE {TABLE} RENAME COLUMN nome TO descricao'))
        else:
            with op.batch_alter_table(TABLE) as batch:
                batch.alter_column('nome', new_column_name='descricao',
                                   existing_type=columns['nome']['type'],
                                   existing_nullable=columns['nome']['nullable'])
        columns = _columns()
    elif 'nome' in columns:
        # Cobre uma tentativa anterior parcialmente aplicada sem descartar dados.
        if sqlite:
            raise RuntimeError(f'{TABLE}: nome e descricao coexistem; revise a tabela antes de remover nome')
        bind.execute(sa.text(f'UPDATE {TABLE} SET descricao = nome '
                             "WHERE (descricao IS NULL OR descricao = '') AND nome IS NOT NULL"))
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column('nome')
        columns = _columns()

    if 'codigo' not in columns:
        op.add_column(TABLE, sa.Column('codigo', sa.String(20), nullable=True))
        columns = _columns()

    rows = bind.execute(sa.text(f'SELECT id, descricao, codigo FROM {TABLE} ORDER BY id')).fetchall()
    if any(not row[1] for row in rows):
        raise RuntimeError(f'{TABLE}: existem registros sem descricao; corrija antes de prosseguir')
    descriptions = [row[1] for row in rows]
    if len(descriptions) != len(set(descriptions)):
        raise RuntimeError(f'{TABLE}: existem descricoes duplicadas; consolide antes de prosseguir')
    used = [row[2] for row in rows if row[2]]
    if len(used) != len(set(used)):
        raise RuntimeError(f'{TABLE}: existem codigos duplicados; consolide antes de prosseguir')
    occupied = set(used)
    for row_id, description, code in rows:
        if code:
            continue
        new_code = _code(description, row_id, occupied)
        bind.execute(sa.text(f'UPDATE {TABLE} SET codigo = :code WHERE id = :id'),
                     {'code': new_code, 'id': row_id})
        occupied.add(new_code)

    columns = _columns()
    if columns['descricao']['nullable'] or columns['codigo']['nullable']:
        if sqlite:
            # ALTER COLUMN NOT NULL exigiria recriar a tabela pai de Categoria.
            # Triggers conservam a mesma regra para escritas futuras.
            for action in ('INSERT', 'UPDATE'):
                for column in ('descricao', 'codigo'):
                    if columns[column]['nullable']:
                        op.execute(sa.text(
                            f'CREATE TRIGGER IF NOT EXISTS tr_tipo_produto_{column}_nn_{action.lower()} '
                            f'BEFORE {action} ON {TABLE} '
                            f"WHEN NEW.{column} IS NULL OR NEW.{column} = '' "
                            'BEGIN SELECT RAISE(ABORT, '
                            f"'{TABLE}.{column} obrigatorio'); END"
                        ))
        else:
            with op.batch_alter_table(TABLE) as batch:
                for column in ('descricao', 'codigo'):
                    if columns[column]['nullable']:
                        batch.alter_column(column, existing_type=columns[column]['type'], nullable=False)
    for column in ('descricao', 'codigo'):
        if not _has_unique([column]):
            if sqlite:
                op.create_index(f'uq_tipo_produto_{column}', TABLE, [column], unique=True)
            else:
                with op.batch_alter_table(TABLE) as batch:
                    batch.create_unique_constraint(f'uq_tipo_produto_{column}', [column])


def downgrade():
    # Os IDs e valores sao preservados; nao volta ao schema legado, pois
    # codigo pode ser usado por outros fluxos e a reversao perderia dados.
    pass
