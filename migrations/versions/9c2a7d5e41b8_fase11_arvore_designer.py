"""Fase 11, Patch 2 - arvore de componentes do Designer.

tesseract_designer_component ganha parent_id (self-FK) e order_index,
transformando a lista plana numa arvore por lista de adjacencia -
mesmo padrao de tesseract_transaction.parent_id/order_index (skill 10).

Revision ID: 9c2a7d5e41b8
Revises: 5f1d8a3c7e92
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c2a7d5e41b8'
down_revision = '5f1d8a3c7e92'
branch_labels = None
depends_on = None

_TABLE = "tesseract_designer_component"


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    """Achado real (test_migrations_idempotent): o downgrade quebrava
    tentando remover um indice que nao existia. Quando o banco nasce
    via db.create_all(), quem cria o indice e o `index=True` do model
    (nome auto-gerado pelo SQLAlchemy); quando nasce via migration, e
    o create_index abaixo. Os dois usam o MESMO nome agora, mas a
    checagem fica como guarda."""
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return index_name in {i["name"] for i in inspector.get_indexes(table_name)}


_INDEX_NAME = "ix_tesseract_designer_component_parent_id"


def upgrade():
    if not _table_exists(_TABLE):
        return

    with op.batch_alter_table(_TABLE) as batch_op:
        if not _column_exists(_TABLE, "parent_id"):
            # Self-FK criada dentro do batch (SQLite nao aceita
            # ADD CONSTRAINT solto - batch_alter_table recria a tabela).
            batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_designer_component_parent", _TABLE, ["parent_id"], ["id"],
            )
            batch_op.create_index(_INDEX_NAME, ["parent_id"])
        if not _column_exists(_TABLE, "order_index"):
            batch_op.add_column(
                sa.Column("order_index", sa.Integer(), nullable=False, server_default="0")
            )


def downgrade():
    if not _table_exists(_TABLE):
        return

    with op.batch_alter_table(_TABLE) as batch_op:
        if _column_exists(_TABLE, "order_index"):
            batch_op.drop_column("order_index")
        if _column_exists(_TABLE, "parent_id"):
            if _index_exists(_TABLE, _INDEX_NAME):
                batch_op.drop_index(_INDEX_NAME)
            batch_op.drop_column("parent_id")
