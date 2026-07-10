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


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return constraint_name in {c["name"] for c in inspector.get_unique_constraints(table_name)}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou esta
    # tabela, create_table/create_unique_constraint falham como
    # "already exists" sem estas checagens.
    if not _table_exists('tesseract_user_menu_preference'):
        op.create_table(
            'tesseract_user_menu_preference',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('tesseract_user.id'), nullable=False),
            sa.Column('group_order_json', sa.JSON(), nullable=True),
            sa.Column('collapsed_groups_json', sa.JSON(), nullable=True),
            sa.Column('sidebar_collapsed', sa.Boolean(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )

    if not _unique_constraint_exists('tesseract_user_menu_preference', 'uq_tesseract_user_menu_preference_user_id'):
        with op.batch_alter_table('tesseract_user_menu_preference') as batch_op:
            batch_op.create_unique_constraint(
                'uq_tesseract_user_menu_preference_user_id', ['user_id'],
            )


def downgrade():
    if _unique_constraint_exists('tesseract_user_menu_preference', 'uq_tesseract_user_menu_preference_user_id'):
        with op.batch_alter_table('tesseract_user_menu_preference') as batch_op:
            batch_op.drop_constraint(
                'uq_tesseract_user_menu_preference_user_id', type_='unique',
            )
    if _table_exists('tesseract_user_menu_preference'):
        op.drop_table('tesseract_user_menu_preference')
