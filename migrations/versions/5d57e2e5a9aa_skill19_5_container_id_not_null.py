"""skill 19 (5/6) - torna tesseract_brewstation_yeastbank_bank_item.container_id
obrigatorio (NOT NULL)

Recusa avançar (RuntimeError, upgrade inteiro faz rollback) se sobrar
algum bank_item com container_id NULL — nunca força um valor
arbitrário em dado incompleto. Se isso acontecer, resolva manualmente
(atribua um Container a cada item pendente) e rode `flask db upgrade`
de novo.

Ver docs/skills/19-proposta-reestruturacao-yeast-bank-container.md.

Revision ID: 5d57e2e5a9aa
Revises: 1e0ea0ae8651
Create Date: 2026-08-20 00:00:00.000004

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d57e2e5a9aa'
down_revision = '1e0ea0ae8651'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_item'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


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

    if _column_is_nullable(_TABLE, 'container_id') is False:
        return  # já está NOT NULL — reaplicação segura, nada a fazer

    bind = op.get_bind()
    pendentes = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {_TABLE} WHERE container_id IS NULL")
    ).scalar()

    if pendentes:
        raise RuntimeError(
            f"skill19 5/6: {pendentes} item(ns) de bank_item ainda sem "
            f"container_id — não é seguro tornar a coluna obrigatória. "
            f"Atribua um Container a cada item pendente (ver passo 4, "
            f"docs/skills/19-proposta-reestruturacao-yeast-bank-container.md) "
            f"e rode 'flask db upgrade' de novo."
        )

    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.alter_column('container_id', nullable=False)


def downgrade():
    if _table_exists(_TABLE) and _column_is_nullable(_TABLE, 'container_id') is False:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.alter_column('container_id', nullable=True)
