"""skill24 correcao item processo cotacao

Revision ID: 0d7080cf1fe8
Revises: fd143ed5695c
Create Date: 2026-08-27 17:30:22.713844

REESCRITA MANUAL COMPLETA (achado do Christopher, sessão pós-Fase
6.3): o autogenerate detectou o schema certo, mas com os mesmos bugs
sistemáticos já documentados (FK sem prefixo tri-nível em
create_table, constraint sem nome em batch_alter_table). Além disso,
esta migration precisa de um passo real de MIGRAÇÃO DE DADO: qualquer
ItemCotacao já cadastrado tinha material_id/material_unidade_id/
quantidade próprios — esses viram um ItemProcessoCotacao (criado ou
reaproveitado se já existir um igual no mesmo processo) antes das
colunas antigas serem removidas. Sem isso, qualquer dado real do
Christopher seria perdido.
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d7080cf1fe8'
down_revision = 'fd143ed5695c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1. Tabela nova - ItemProcessoCotacao (o item pedido, uma vez por processo)
    op.create_table('tesseract_estoque_item_processo_cotacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('processo_cotacao_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('material_unidade_id', sa.Integer(), nullable=False),
        sa.Column('quantidade_desejada', sa.Float(), nullable=False),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['material_id'], ['tesseract_estoque_material.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['material_unidade_id'], ['tesseract_estoque_material_unidade.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['processo_cotacao_id'], ['tesseract_estoque_processo_cotacao.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tesseract_estoque_item_processo_cotacao', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_item_processo_cotacao_material_id'), ['material_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_item_processo_cotacao_material_unidade_id'), ['material_unidade_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_item_processo_cotacao_processo_cotacao_id'), ['processo_cotacao_id'], unique=False)

    # 2. Colunas novas em item_cotacao - NULLABLE por enquanto (a
    # migração de dado abaixo preenche antes de travar NOT NULL). O
    # índice de item_processo_cotacao_id já entra aqui (não no passo 4
    # junto com alter_column) - achado real: criar índice no mesmo
    # batch que faz alter_column(nullable=False) duplica a criação,
    # porque o batch recria a tabela duas vezes nesse caso.
    with op.batch_alter_table('tesseract_estoque_item_cotacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item_processo_cotacao_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quantidade_ofertada', sa.Float(), nullable=True))

    with op.batch_alter_table('tesseract_estoque_item_cotacao', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_item_cotacao_item_processo_cotacao_id'), ['item_processo_cotacao_id'], unique=False)

    # 3. Migração de dado - qualquer ItemCotacao já cadastrado vira um
    # ItemProcessoCotacao (criado ou reaproveitado por
    # processo+material+unidade, evita duplicar o item pedido se dois
    # fornecedores já tinham cotado o mesmo Material).
    #
    # sa.Table completo (não sa.table() leve) - precisa da PK marcada
    # pra inserted_primary_key funcionar no insert abaixo (achado real
    # ao validar esta migration: sa.table() sem primary_key=True
    # devolve tupla vazia em inserted_primary_key).
    metadata = sa.MetaData()
    item_cotacao_t = sa.Table(
        'tesseract_estoque_item_cotacao', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('cotacao_id', sa.Integer),
        sa.Column('material_id', sa.Integer), sa.Column('material_unidade_id', sa.Integer),
        sa.Column('quantidade', sa.Float), sa.Column('item_processo_cotacao_id', sa.Integer),
    )
    cotacao_t = sa.Table(
        'tesseract_estoque_cotacao', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('processo_cotacao_id', sa.Integer),
    )
    item_processo_t = sa.Table(
        'tesseract_estoque_item_processo_cotacao', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('processo_cotacao_id', sa.Integer),
        sa.Column('material_id', sa.Integer), sa.Column('material_unidade_id', sa.Integer),
        sa.Column('quantidade_desejada', sa.Float), sa.Column('is_deleted', sa.Boolean),
        sa.Column('created_at', sa.DateTime), sa.Column('updated_at', sa.DateTime),
    )

    now = datetime.now(timezone.utc)
    linhas = bind.execute(sa.select(
        item_cotacao_t.c.id, item_cotacao_t.c.cotacao_id, item_cotacao_t.c.material_id,
        item_cotacao_t.c.material_unidade_id, item_cotacao_t.c.quantidade,
    )).fetchall()

    processo_por_cotacao = {}
    item_processo_por_chave = {}

    for item_id, cotacao_id, material_id, unidade_id, quantidade in linhas:
        if cotacao_id not in processo_por_cotacao:
            linha_proc = bind.execute(
                sa.select(cotacao_t.c.processo_cotacao_id).where(cotacao_t.c.id == cotacao_id)
            ).fetchone()
            processo_por_cotacao[cotacao_id] = linha_proc[0] if linha_proc else None
        processo_id = processo_por_cotacao[cotacao_id]
        if processo_id is None:
            continue  # linha orfa (cotacao removida sem cascade em algum teste) - ignora

        chave = (processo_id, material_id, unidade_id)
        if chave not in item_processo_por_chave:
            resultado = bind.execute(item_processo_t.insert().values(
                processo_cotacao_id=processo_id, material_id=material_id,
                material_unidade_id=unidade_id, quantidade_desejada=quantidade,
                is_deleted=False, created_at=now, updated_at=now,
            ))
            item_processo_por_chave[chave] = resultado.inserted_primary_key[0]

        bind.execute(
            item_cotacao_t.update()
            .where(item_cotacao_t.c.id == item_id)
            .values(item_processo_cotacao_id=item_processo_por_chave[chave])
        )

    # 4. Trava NOT NULL, corrige índices/FK, remove as colunas antigas
    # (a FK antiga cai junto com a coluna no modo batch do SQLite - não
    # precisa de drop_constraint separado pras duas antigas).
    with op.batch_alter_table('tesseract_estoque_item_cotacao', schema=None) as batch_op:
        batch_op.alter_column('item_processo_cotacao_id', nullable=False)
        batch_op.drop_index(batch_op.f('ix_item_cotacao_material_id'))
        batch_op.drop_index(batch_op.f('ix_item_cotacao_material_unidade_id'))
        batch_op.create_foreign_key(
            'fk_item_cotacao_item_processo_cotacao_id', 'tesseract_estoque_item_processo_cotacao',
            ['item_processo_cotacao_id'], ['id'], ondelete='CASCADE',
        )
        batch_op.drop_column('material_id')
        batch_op.drop_column('material_unidade_id')
        batch_op.drop_column('quantidade')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tesseract_estoque_item_cotacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantidade', sa.FLOAT(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('material_unidade_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('material_id', sa.INTEGER(), nullable=True))
        batch_op.drop_constraint('fk_item_cotacao_item_processo_cotacao_id', type_='foreignkey')
        batch_op.create_foreign_key('fk_item_cotacao_material_unidade_id', 'tesseract_estoque_material_unidade', ['material_unidade_id'], ['id'], ondelete='RESTRICT')
        batch_op.create_foreign_key('fk_item_cotacao_material_id', 'tesseract_estoque_material', ['material_id'], ['id'], ondelete='RESTRICT')
        batch_op.drop_index(batch_op.f('ix_item_cotacao_item_processo_cotacao_id'))
        batch_op.create_index(batch_op.f('ix_item_cotacao_material_unidade_id'), ['material_unidade_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_item_cotacao_material_id'), ['material_id'], unique=False)
        batch_op.drop_column('quantidade_ofertada')
        batch_op.drop_column('item_processo_cotacao_id')

    with op.batch_alter_table('tesseract_estoque_item_processo_cotacao', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_item_processo_cotacao_processo_cotacao_id'))
        batch_op.drop_index(batch_op.f('ix_item_processo_cotacao_material_unidade_id'))
        batch_op.drop_index(batch_op.f('ix_item_processo_cotacao_material_id'))

    op.drop_table('tesseract_estoque_item_processo_cotacao')
    # ### end Alembic commands ###
    # NOTA: o downgrade NÃO reconstrói material_id/material_unidade_id
    # a partir do ItemProcessoCotacao vinculado (dado ficaria com
    # material_id/material_unidade_id nulos) - downgrade aqui existe só
    # pra reverter o schema, não preserva o dado migrado no upgrade.
    # Se precisar reverter com dado, restaurar backup antes.
