"""cria tesseract_model_definition e tesseract_model_field_definition
(Model Builder Visual - skill 06, Patch A)

Revision ID: c2a7e5f19b04
Revises: 9c4f1e8a3b27
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2a7e5f19b04'
down_revision = '9c4f1e8a3b27'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {i["name"] for i in inspector.get_indexes(table_name)}


def upgrade():
    # Achado real (BACKLOG.md): se db.create_all() já criou estas
    # tabelas, create_table/create_index falham como "already exists"
    # sem estas checagens.
    if not _table_exists('tesseract_model_definition'):
        op.create_table(
            'tesseract_model_definition',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('target_scope', sa.String(20), nullable=False),
            sa.Column('target_addon_name', sa.String(100), nullable=False),
            sa.Column('target_feature_name', sa.String(100), nullable=True),
            sa.Column('model_name', sa.String(100), nullable=False),
            sa.Column('table_short_name', sa.String(80), nullable=False),
            sa.Column('manifest_draft_json', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('generated_at', sa.DateTime(), nullable=True),
            sa.Column('generation_run_id', sa.String(36), nullable=True),
            sa.Column('migration_revision', sa.String(64), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('tesseract_user.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )

    if not _table_exists('tesseract_model_field_definition'):
        op.create_table(
            'tesseract_model_field_definition',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('model_definition_id', sa.Integer(), sa.ForeignKey('tesseract_model_definition.id'), nullable=False),
            sa.Column('field_name', sa.String(100), nullable=False),
            sa.Column('field_type', sa.String(20), nullable=False),
            sa.Column('nullable', sa.Boolean(), nullable=False),
            sa.Column('unique', sa.Boolean(), nullable=False),
            sa.Column('is_required', sa.Boolean(), nullable=False),
            sa.Column('default_value', sa.String(255), nullable=True),
            sa.Column('max_length', sa.Integer(), nullable=True),
            sa.Column('fk_target_table', sa.String(150), nullable=True),
            sa.Column('label_text', sa.String(200), nullable=False),
            sa.Column('is_listview_column', sa.Boolean(), nullable=False),
            sa.Column('is_form_field', sa.Boolean(), nullable=False),
            sa.Column('order_index', sa.Integer(), nullable=False),
        )

    if not _index_exists('tesseract_model_field_definition', 'ix_tesseract_model_field_definition_model_definition_id'):
        op.create_index(
            'ix_tesseract_model_field_definition_model_definition_id',
            'tesseract_model_field_definition', ['model_definition_id'],
        )


def downgrade():
    if _index_exists('tesseract_model_field_definition', 'ix_tesseract_model_field_definition_model_definition_id'):
        op.drop_index(
            'ix_tesseract_model_field_definition_model_definition_id',
            table_name='tesseract_model_field_definition',
        )
    if _table_exists('tesseract_model_field_definition'):
        op.drop_table('tesseract_model_field_definition')
    if _table_exists('tesseract_model_definition'):
        op.drop_table('tesseract_model_definition')
