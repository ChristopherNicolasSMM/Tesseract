"""redesenha bank_event (skill 21): bank_item_id obrigatorio, remove
strain_id, adiciona cell_count_id

YeastBankEvent vira o ponto de entrada unico da linha do tempo do
Yeast Bank. bank_item_id passa a ser obrigatorio (era opcional);
strain_id removido (cepa sempre resolvida via bank_item.strain);
cell_count_id novo (preenchido so pelo fluxo automatico de criacao,
igual ja acontecia com starter_id).

Ver docs/skills/21-tela-integrada-navegacao-unificacao-evento-starter-contagem.md.

Revision ID: 7b52062d7430
Revises: 0b8fa81614a6
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b52062d7430'
down_revision = '0b8fa81614a6'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_event'
_CELL_COUNT_TABLE = 'tesseract_brewstation_yeastbank_cell_count_history'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _column_is_nullable(table_name: str, column_name: str) -> bool | None:
    if not _table_exists(table_name):
        return None
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return col["nullable"]
    return None


def upgrade():
    if not _table_exists(_TABLE):
        return

    # 1. Adiciona cell_count_id (nullable — só o fluxo automático
    #    preenche, nunca é obrigatório).
    if not _column_exists(_TABLE, 'cell_count_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column('cell_count_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_bank_event_cell_count_id', _CELL_COUNT_TABLE, ['cell_count_id'], ['id'],
            )

    # 2. Remove strain_id.
    if _column_exists(_TABLE, 'strain_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            fk_name = None
            bind = op.get_bind()
            inspector = sa.inspect(bind)
            for fk in inspector.get_foreign_keys(_TABLE):
                if 'strain_id' in fk.get('constrained_columns', []):
                    fk_name = fk.get('name')
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.drop_column('strain_id')

    # 3. bank_item_id vira obrigatório — recusa avançar se sobrar
    #    evento sem item vinculado, nunca assume um valor arbitrário.
    if _column_is_nullable(_TABLE, 'bank_item_id') is False:
        return  # já está NOT NULL — reaplicação segura

    bind = op.get_bind()
    pendentes = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {_TABLE} WHERE bank_item_id IS NULL")
    ).scalar()

    if pendentes:
        raise RuntimeError(
            f"bank_event redesign (skill 21): {pendentes} evento(s) ainda sem "
            f"bank_item_id — não é seguro tornar a coluna obrigatória. Vincule "
            f"um Item do Banco a cada evento pendente (ou mova pra lixeira) e "
            f"rode 'flask db upgrade' de novo."
        )

    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.alter_column('bank_item_id', nullable=False)


def downgrade():
    if not _table_exists(_TABLE):
        return

    if _column_is_nullable(_TABLE, 'bank_item_id') is False:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.alter_column('bank_item_id', nullable=True)

    if not _column_exists(_TABLE, 'strain_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column('strain_id', sa.Integer(), nullable=True))

    if _column_exists(_TABLE, 'cell_count_id'):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_constraint('fk_bank_event_cell_count_id', type_='foreignkey')
            batch_op.drop_column('cell_count_id')
