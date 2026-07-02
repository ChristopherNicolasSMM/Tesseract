"""cria tesseract_playground_request (skill 06 Patch C - API/SQL
Playground)

Revision ID: f4c8a2d61b73
Revises: d8b1f4a6c930
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4c8a2d61b73'
down_revision = 'd8b1f4a6c930'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tesseract_playground_request',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('name', sa.String(150), nullable=True),
        sa.Column('http_method', sa.String(10), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('headers_json', sa.JSON(), nullable=True),
        sa.Column('body_json', sa.JSON(), nullable=True),
        sa.Column('sql_text', sa.Text(), nullable=True),
        sa.Column('last_response_json', sa.JSON(), nullable=True),
        sa.Column('last_status_code', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('tesseract_user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('tesseract_playground_request')
