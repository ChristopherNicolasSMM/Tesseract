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
