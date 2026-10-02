"""Detecta esquema ja criado pelos models atuais antes de revisoes historicas.

O baseline 091f87025ce4 nao cria tabelas. Em instalacoes novas, o boot
chama db.create_all() e o Alembic ainda precisa registrar as revisoes.
Nunca usar apenas a presenca de uma tabela como sinal de schema completo:
num banco antigo, create_all pode criar tabelas novas sem alterar as velhas.
"""
from alembic import op
import sqlalchemy as sa


def current_model_schema():
    metadata = op.get_context().opts.get('target_metadata')
    if metadata is None or not hasattr(metadata, 'tables'):
        return False
    expected = metadata.tables
    required = {
        'tesseract_estoque_categoria',
        'tesseract_estoque_material_unidade',
        'tesseract_estoque_item_processo_cotacao',
        'tesseract_estoque_unidade_catalogo',
        'tesseract_brewstation_brewfather_inventory_link',
    }
    if not required <= set(expected):
        return False
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if not set(expected) <= existing:
        return False
    for table in expected.values():
        actual = {column['name']: column for column in inspector.get_columns(table.name)}
        if set(actual) != set(table.columns.keys()):
            return False
        for column in table.columns:
            if bool(actual[column.name]['nullable']) != bool(column.nullable):
                return False
    return True


def drop_columns_with_references(operations, table_name, column_names):
    """Remove as referências reais das colunas, também em SQLite/create_all.

    Nomes de FK e índices dos models podem diferir dos históricos. A
    convenção só nomeia FKs sem nome durante a reflexão do modo batch.
    As demais referências/índices da tabela permanecem intactos.
    """
    inspector = sa.inspect(operations.get_bind())
    columns = set(column_names)
    foreign_keys = [fk for fk in inspector.get_foreign_keys(table_name)
                    if columns.intersection(fk["constrained_columns"])]
    indexes = [index for index in inspector.get_indexes(table_name)
               if columns.intersection(index["column_names"])]
    uniques = [constraint for constraint in inspector.get_unique_constraints(table_name)
               if columns.intersection(constraint["column_names"])]
    convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
    }
    with operations.batch_alter_table(table_name, naming_convention=convention) as batch:
        for fk in foreign_keys:
            name = fk["name"] or (
                f"fk_{table_name}_{fk['constrained_columns'][0]}_{fk['referred_table']}"
            )
            batch.drop_constraint(name, type_="foreignkey")
        for constraint in uniques:
            name = constraint["name"] or f"uq_{table_name}_{constraint['column_names'][0]}"
            batch.drop_constraint(name, type_="unique")
        for index in indexes:
            batch.drop_index(index["name"])
        for column in column_names:
            batch.drop_column(column)
