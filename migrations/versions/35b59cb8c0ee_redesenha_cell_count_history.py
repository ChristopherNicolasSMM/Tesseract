"""redesenha cell_count_history (skill 21): bank_item_id obrigatorio,
remove strain_id e starter_id

Decisao do Christopher (2026-08-24): contagem e sempre do item, sem
distinguir se veio de um starter especifico; cepa sempre resolvida
via bank_item.strain.

Ver docs/skills/21-tela-integrada-navegacao-unificacao-evento-starter-contagem.md.

Revision ID: 35b59cb8c0ee
Revises: 7b52062d7430
Create Date: 2026-08-24 00:00:00.000001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '35b59cb8c0ee'
down_revision = '7b52062d7430'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_cell_count_history'


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


def _drop_fk_if_exists(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_name = None
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk.get('constrained_columns', []):
            fk_name = fk.get('name')
    with op.batch_alter_table(table_name) as batch_op:
        if fk_name:
            batch_op.drop_constraint(fk_name, type_='foreignkey')
        batch_op.drop_column(column_name)


def upgrade():
    if not _table_exists(_TABLE):
        return

    for col in ('strain_id', 'starter_id'):
        if _column_exists(_TABLE, col):
            _drop_fk_if_exists(_TABLE, col)

    if _column_is_nullable(_TABLE, 'bank_item_id') is False:
        return  # já está NOT NULL — reaplicação segura

    bind = op.get_bind()
    pendentes = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {_TABLE} WHERE bank_item_id IS NULL")
    ).scalar()

    if pendentes:
        raise RuntimeError(
            f"cell_count_history redesign (skill 21): {pendentes} registro(s) "
            f"ainda sem bank_item_id — não é seguro tornar a coluna "
            f"obrigatória. Vincule um Item do Banco a cada registro pendente "
            f"(ou mova pra lixeira) e rode 'flask db upgrade' de novo."
        )

    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.alter_column('bank_item_id', nullable=False)


def downgrade():
    if not _table_exists(_TABLE):
        return

    if _column_is_nullable(_TABLE, 'bank_item_id') is False:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.alter_column('bank_item_id', nullable=True)

    for col in ('strain_id', 'starter_id'):
        if not _column_exists(_TABLE, col):
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(sa.Column(col, sa.Integer(), nullable=True))
