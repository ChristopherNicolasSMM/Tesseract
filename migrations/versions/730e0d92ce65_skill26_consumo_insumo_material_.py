"""skill26 consumo insumo brassagem e material resultante envase

Revision ID: 730e0d92ce65
Revises: 0d7080cf1fe8
Create Date: 2026-09-01 12:45:00.000000

Duas colunas novas, ambas nullable, sem migração de dado necessária
(skill 26 — docs/skills/26-proposta-envase-consumo-insumo-custo-industrializacao.md):

1. BrewSession.insumos_baixados_em/custo_total_insumos — controla
   idempotência da baixa de insumo da receita na brassagem.
2. Envase.material_resultante_id — referência fraca (SEM FK,
   addon_estoque) pro Material acabado que o Envase representa.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '730e0d92ce65'
down_revision = '0d7080cf1fe8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tesseract_brewstation_mashctrl_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('insumos_baixados_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('custo_total_insumos', sa.Float(), nullable=True))

    with op.batch_alter_table('tesseract_brewstation_env_envase', schema=None) as batch_op:
        batch_op.add_column(sa.Column('material_resultante_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_envase_material_resultante_id'), ['material_resultante_id'], unique=False,
        )


def downgrade():
    with op.batch_alter_table('tesseract_brewstation_env_envase', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_envase_material_resultante_id'))
        batch_op.drop_column('material_resultante_id')

    with op.batch_alter_table('tesseract_brewstation_mashctrl_session', schema=None) as batch_op:
        batch_op.drop_column('custo_total_insumos')
        batch_op.drop_column('insumos_baixados_em')
