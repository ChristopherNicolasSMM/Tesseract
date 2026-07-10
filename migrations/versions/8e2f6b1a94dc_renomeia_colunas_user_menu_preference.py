"""renomeia colunas de tesseract_user_menu_preference para o schema de
arvore (skill 10): group_order_json -> order_overrides_json,
collapsed_groups_json -> collapsed_nodes_json

Revision ID: 8e2f6b1a94dc
Revises: 3a91c7de5f42
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e2f6b1a94dc'
down_revision = '3a91c7de5f42'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou a tabela
    # com o nome ATUAL das colunas (order_overrides_json/
    # collapsed_nodes_json — o model não conhece mais o nome antigo),
    # renomear "group_order_json" falharia (coluna não existe). Sem
    # coluna antiga pra renomear, não há nada a fazer aqui.
    if not _column_exists("tesseract_user_menu_preference", "group_order_json"):
        return

    with op.batch_alter_table("tesseract_user_menu_preference") as batch_op:
        batch_op.alter_column("group_order_json", new_column_name="order_overrides_json")
        batch_op.alter_column("collapsed_groups_json", new_column_name="collapsed_nodes_json")

    # Formato do JSON mudou de forma incompatível (lista de nomes de
    # grupo -> dict de overrides por pai / lista de códigos) — dado
    # antigo não é reaproveitável. Reset pra NULL = "herda o padrão
    # global" (skill 07), estado seguro, nunca quebra resolve_menu_state.
    op.execute(
        "UPDATE tesseract_user_menu_preference "
        "SET order_overrides_json = NULL, collapsed_nodes_json = NULL"
    )


def downgrade():
    if not _column_exists("tesseract_user_menu_preference", "order_overrides_json"):
        return
    with op.batch_alter_table("tesseract_user_menu_preference") as batch_op:
        batch_op.alter_column("order_overrides_json", new_column_name="group_order_json")
        batch_op.alter_column("collapsed_nodes_json", new_column_name="collapsed_groups_json")
