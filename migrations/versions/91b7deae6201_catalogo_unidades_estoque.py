"""Catálogo de unidades usuais para estoque.

Revision ID: 91b7deae6201
Revises: 0825bedaf230
"""
from alembic import op
import sqlalchemy as sa

revision = '91b7deae6201'
down_revision = '0825bedaf230'
branch_labels = None
depends_on = None

TABLE = 'tesseract_estoque_unidade_catalogo'
UNITS = [
    ('KG', 'Quilograma', 'massa', 1), ('G', 'Grama', 'massa', .001),
    ('MG', 'Miligrama', 'massa', .000001), ('T', 'Tonelada', 'massa', 1000),
    ('L', 'Litro', 'volume', 1), ('ML', 'Mililitro', 'volume', .001),
    ('CM3', 'Centímetro cúbico', 'volume', .001), ('M3', 'Metro cúbico', 'volume', 1000),
    ('M', 'Metro', 'comprimento', 1), ('CM', 'Centímetro', 'comprimento', .01),
    ('MM', 'Milímetro', 'comprimento', .001), ('M2', 'Metro quadrado', 'area', 1),
    ('CM2', 'Centímetro quadrado', 'area', .0001), ('UN', 'Unidade', 'contagem', 1),
    ('DZ', 'Dúzia', 'contagem', 12), ('PCT', 'Pacote', 'embalagem', None),
    ('CX', 'Caixa', 'embalagem', None), ('SC', 'Saco', 'embalagem', None),
    ('FD', 'Fardo', 'embalagem', None), ('RL', 'Rolo', 'embalagem', None),
]


def upgrade():
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('codigo', sa.String(20), nullable=False, unique=True),
        sa.Column('descricao', sa.String(100), nullable=False),
        sa.Column('dimensao', sa.String(20), nullable=False),
        sa.Column('fator_referencia', sa.Float, nullable=True),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default=sa.false()),
    )
    catalogo = sa.table(TABLE, sa.column('codigo', sa.String),
                        sa.column('descricao', sa.String), sa.column('dimensao', sa.String),
                        sa.column('fator_referencia', sa.Float), sa.column('is_deleted', sa.Boolean))
    op.bulk_insert(catalogo, [dict(codigo=code, descricao=name, dimensao=dimension,
                                  fator_referencia=factor, is_deleted=False)
                              for code, name, dimension, factor in UNITS])
    with op.batch_alter_table('material_unidade') as batch:
        batch.alter_column('unidade', existing_type=sa.String(20), type_=sa.String(60),
                           existing_nullable=False)


def downgrade():
    with op.batch_alter_table('material_unidade') as batch:
        batch.alter_column('unidade', existing_type=sa.String(60), type_=sa.String(20),
                           existing_nullable=False)
    op.drop_table(TABLE)
