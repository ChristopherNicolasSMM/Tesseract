"""cria tesseract_user_menu_preference (skill 07 - personalizacao de
menu: ordem de grupos e colapso, override por usuario)

Revision ID: d8b1f4a6c930
Revises: c2a7e5f19b04
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8b1f4a6c930'
down_revision = 'c2a7e5f19b04'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tesseract_user_menu_preference',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('tesseract_user.id'), nullable=False),
        sa.Column('group_order_json', sa.JSON(), nullable=True),
        sa.Column('collapsed_groups_json', sa.JSON(), nullable=True),
        sa.Column('sidebar_collapsed', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint(
        'uq_tesseract_user_menu_preference_user_id',
        'tesseract_user_menu_preference', ['user_id'],
    )


def downgrade():
    op.drop_constraint(
        'uq_tesseract_user_menu_preference_user_id',
        'tesseract_user_menu_preference', type_='unique',
    )
    op.drop_table('tesseract_user_menu_preference')
