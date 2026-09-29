"""Oculta listas de edição que agora são acessadas no contexto do fluxo.

Revision ID: d5a81c4e09f2
Revises: bca705a2e6f0
"""
from alembic import op
import sqlalchemy as sa

revision = "d5a81c4e09f2"
down_revision = "bca705a2e6f0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "tesseract_transaction" not in sa.inspect(bind).get_table_names():
        return
    for code in ("TX_RECIPE_INGREDIENTS", "TX_RECIPE_STEPS",
                 "TX_FERMENTATION_STEPS", "TX_BREW_PLANTS"):
        bind.execute(sa.text(
            "UPDATE tesseract_transaction SET is_active = :active WHERE code = :code"
        ), {"active": False, "code": code})


def downgrade():
    # As escolhas posteriores do administrador não devem ser sobrescritas.
    pass
