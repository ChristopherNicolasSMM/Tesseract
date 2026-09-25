"""Remove a antiga regra de quantidade positiva da UI de movimentações.

Revision ID: b493ea0c61d4
Revises: 91b7deae6201
"""
from alembic import op
import sqlalchemy as sa

revision = "b493ea0c61d4"
down_revision = "91b7deae6201"
branch_labels = None
depends_on = None


def upgrade():
    # Ajustes negativos são válidos; entradas e saídas negativas continuam
    # bloqueadas pelo serviço central. A FieldRule antiga impedia usar
    # esse caso na tela mesmo após retirar @min_value do model.
    op.execute(sa.text("""
        UPDATE tesseract_field_rule SET is_active = 0
        WHERE entity_key = 'movimentacaos'
          AND field_name = 'quantidade'
          AND rule_id = 'min_valor'
    """))


def downgrade():
    # Não reativa uma regra que um administrador também pode ter desligado.
    pass
