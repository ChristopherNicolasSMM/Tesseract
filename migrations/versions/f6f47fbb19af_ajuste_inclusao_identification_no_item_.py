"""Ajuste inclusao identification no item do banco de leveduras

Revision ID: f6f47fbb19af
Revises: b7e4d19a63c5
Create Date: 2026-08-20 10:39:56.785465
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6f47fbb19af'
down_revision = 'b7e4d19a63c5'
branch_labels = None
depends_on = None

_STEP = 'tesseract_brewstation_mashctrl_recipe_step'
_ITEM = 'tesseract_brewstation_yeastbank_bank_item'
_STRAIN = 'tesseract_brewstation_yeastbank_strain'
_ACTION = 'tesseract_designer_data_action'
_FIELD = 'tesseract_model_field_definition'
_OLD_STEP_INDEX = 'ix_tesseract_brewstation_mashctrl_recipe_step_recipe_id'
_NEW_STEP_INDEX = 'ix_recipe_step_recipe_id'
_FIELD_INDEX = 'ix_tesseract_model_field_definition_model_definition_id'


def _table_exists(table):
    return table in sa.inspect(op.get_bind()).get_table_names()


def _columns(table):
    return {col['name']: col for col in sa.inspect(op.get_bind()).get_columns(table)}


def _index_exists(table, name):
    return name in {idx['name'] for idx in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    # Estas tabelas podem ainda nao existir: f7a4c916e830 e c2a7e5f19b04
    # as criam em revisoes posteriores. Bancos criados pelo model podem te-las.
    if _table_exists(_STEP):
        if _index_exists(_STEP, _OLD_STEP_INDEX):
            op.drop_index(_OLD_STEP_INDEX, table_name=_STEP)
        if not _index_exists(_STEP, _NEW_STEP_INDEX):
            op.create_index(_NEW_STEP_INDEX, _STEP, ['recipe_id'])

    if _table_exists(_ITEM) and 'identification' not in _columns(_ITEM):
        with op.batch_alter_table(_ITEM) as batch_op:
            batch_op.add_column(sa.Column('identification', sa.String(255), nullable=True))

    if _table_exists(_STRAIN) and _columns(_STRAIN).get('family', {}).get('nullable'):
        # SQLite recria a tabela no batch; linhas antigas nao podem ter NULL.
        op.execute(sa.text(f"UPDATE {_STRAIN} SET family = 'Ale' WHERE family IS NULL"))
        with op.batch_alter_table(_STRAIN) as batch_op:
            batch_op.alter_column('family', existing_type=sa.VARCHAR(50), nullable=False)

    if _table_exists(_ACTION):
        columns = _columns(_ACTION)
        nullable_dates = [name for name in ('created_at', 'updated_at')
                          if name in columns and not columns[name]['nullable']]
        if nullable_dates:
            with op.batch_alter_table(_ACTION) as batch_op:
                for name in nullable_dates:
                    batch_op.alter_column(name, existing_type=sa.DATETIME(), nullable=True)

    if _table_exists(_FIELD) and _index_exists(_FIELD, _FIELD_INDEX):
        op.drop_index(_FIELD_INDEX, table_name=_FIELD)


def downgrade():
    if _table_exists(_FIELD) and not _index_exists(_FIELD, _FIELD_INDEX):
        op.create_index(_FIELD_INDEX, _FIELD, ['model_definition_id'])

    if _table_exists(_ACTION):
        columns = _columns(_ACTION)
        required_dates = [name for name in ('updated_at', 'created_at')
                          if name in columns and columns[name]['nullable']]
        if required_dates:
            with op.batch_alter_table(_ACTION) as batch_op:
                for name in required_dates:
                    batch_op.alter_column(name, existing_type=sa.DATETIME(), nullable=False)

    if _table_exists(_STRAIN) and not _columns(_STRAIN).get('family', {}).get('nullable', True):
        with op.batch_alter_table(_STRAIN) as batch_op:
            batch_op.alter_column('family', existing_type=sa.VARCHAR(50), nullable=True)

    if _table_exists(_ITEM) and 'identification' in _columns(_ITEM):
        with op.batch_alter_table(_ITEM) as batch_op:
            batch_op.drop_column('identification')

    if _table_exists(_STEP):
        if _index_exists(_STEP, _NEW_STEP_INDEX):
            op.drop_index(_NEW_STEP_INDEX, table_name=_STEP)
        if not _index_exists(_STEP, _OLD_STEP_INDEX):
            op.create_index(_OLD_STEP_INDEX, _STEP, ['recipe_id'])
