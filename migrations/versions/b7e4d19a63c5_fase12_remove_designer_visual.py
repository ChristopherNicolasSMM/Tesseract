"""Fase 12 - remocao do construtor visual do Designer.

A pagina customizada deixa de ser uma arvore de componentes montada por
drag-and-drop e passa a ser HTML escrito a mao:

- tesseract_designer_page ganha content_html
- tesseract_designer_page perde canvas_width/canvas_height/canvas_bg
  (so faziam sentido para o canvas)
- tabela tesseract_designer_component e removida

Ver o docstring de model/core/designer_page.py para a decisao.

Revision ID: b7e4d19a63c5
Revises: 9c2a7d5e41b8
Create Date: 2026-08-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e4d19a63c5'
down_revision = '9c2a7d5e41b8'
branch_labels = None
depends_on = None

_PAGE = "tesseract_designer_page"
_COMPONENT = "tesseract_designer_component"


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    if not _table_exists(table):
        return False
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if _table_exists(_PAGE):
        with op.batch_alter_table(_PAGE) as batch_op:
            if not _column_exists(_PAGE, "content_html"):
                batch_op.add_column(sa.Column("content_html", sa.Text(), nullable=True))
            for legado in ("canvas_width", "canvas_height", "canvas_bg"):
                if _column_exists(_PAGE, legado):
                    batch_op.drop_column(legado)

    if _table_exists(_COMPONENT):
        op.drop_table(_COMPONENT)


def downgrade():
    """Reversao PARCIAL de proposito: recria a tabela de componentes
    vazia e as colunas de canvas, mas o conteudo dos componentes que
    existiam antes do upgrade nao volta - eles foram apagados junto com
    a tabela. Nao ha como reconstruir uma arvore de componentes a
    partir de HTML escrito a mao."""
    if _table_exists(_PAGE):
        with op.batch_alter_table(_PAGE) as batch_op:
            if not _column_exists(_PAGE, "canvas_width"):
                batch_op.add_column(sa.Column("canvas_width", sa.Integer(), nullable=False, server_default="1280"))
            if not _column_exists(_PAGE, "canvas_height"):
                batch_op.add_column(sa.Column("canvas_height", sa.Integer(), nullable=False, server_default="720"))
            if not _column_exists(_PAGE, "canvas_bg"):
                batch_op.add_column(sa.Column("canvas_bg", sa.String(20), nullable=False, server_default="#f6f9ff"))
            if _column_exists(_PAGE, "content_html"):
                batch_op.drop_column("content_html")

    if not _table_exists(_COMPONENT):
        op.create_table(
            _COMPONENT,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_id", sa.Integer(), sa.ForeignKey("tesseract_designer_page.id"), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("name", sa.String(100), nullable=True),
            sa.Column("x", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("y", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("width", sa.Integer(), nullable=False, server_default="150"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="40"),
            sa.Column("z_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("properties", sa.JSON(), nullable=True),
            sa.Column("events", sa.JSON(), nullable=True),
            sa.Column("rules", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
