"""Destaca workspace e oculta atalhos de visualização repetidos.

Revision ID: bca705a2e6f0
Revises: ee29a41c68f2
"""
from alembic import op
import sqlalchemy as sa

revision = "bca705a2e6f0"
down_revision = "ee29a41c68f2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "tesseract_transaction" not in sa.inspect(bind).get_table_names():
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("tesseract_transaction")}
    if not {"code", "is_active", "is_workspace"}.issubset(columns):
        raise RuntimeError("tesseract_transaction sem colunas de visibilidade esperadas")
    bind.execute(sa.text(
        "UPDATE tesseract_transaction SET is_active = :active, is_workspace = :workspace "
        "WHERE code = :code"
    ), {"active": True, "workspace": True, "code": "TX_PLANT_WORKSPACE"})
    for code in ("TX_RECIPE_TIMELINE", "TX_DASHBOARD_VIEW", "TX_DASHBOARD_WIDGETS"):
        bind.execute(sa.text(
            "UPDATE tesseract_transaction SET is_active = :active WHERE code = :code"
        ), {"active": False, "code": code})


def downgrade():
    # A configuração de menu pode ter sido modificada pelo administrador.
    # Não reativar entradas automaticamente ao voltar a revisão.
    pass
