"""cria tesseract_scheduled_task, tesseract_task_log,
tesseract_message_queue (sistema de tasks portado do PyTeca - ver
docs/skills/05-proposta-addon-device-manager-e-mqtt.md, decisao de
2026-06-29: portar como infraestrutura geral do Core)

Revision ID: 9c4f1e8a3b27
Revises: 7b3e9c1a2d4f
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c4f1e8a3b27'
down_revision = '7b3e9c1a2d4f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tesseract_scheduled_task',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('target', sa.Text(), nullable=False),
        sa.Column('schedule', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('next_run', sa.DateTime(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('tesseract_user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'tesseract_task_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tesseract_scheduled_task.id'), nullable=True),
        sa.Column('task_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
    )

    op.create_table(
        'tesseract_message_queue',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('retries', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('tesseract_message_queue')
    op.drop_table('tesseract_task_log')
    op.drop_table('tesseract_scheduled_task')
