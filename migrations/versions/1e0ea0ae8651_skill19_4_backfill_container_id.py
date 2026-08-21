"""skill 19 (4/6) - backfill de tesseract_brewstation_yeastbank_bank_item.container_id
a partir do antigo storage_device_id, usando o Container "Geral" criado no
passo 2 para cada dispositivo

Passo de dados puro. Item cujo storage_device_id já estava NULL (dado
legado sem dispositivo) fica com container_id também NULL aqui — o
passo 5 verifica e recusa avançar se sobrar algum, em vez de assumir
um destino arbitrário para dado incompleto.

Ver docs/skills/19-proposta-reestruturacao-yeast-bank-container.md.

Revision ID: 1e0ea0ae8651
Revises: 8b36e1f30843
Create Date: 2026-08-20 00:00:00.000003

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e0ea0ae8651'
down_revision = '8b36e1f30843'
branch_labels = None
depends_on = None

_ITEM_TABLE = 'tesseract_brewstation_yeastbank_bank_item'
_CONTAINER_TABLE = 'tesseract_brewstation_yeastbank_container'
_DEFAULT_SUFFIX = ' — Geral'


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


def upgrade():
    # storage_device_id só existe até o passo 6 remover — se esta
    # migration for reaplicada depois disso (não deveria, mas a
    # checagem custa nada), não há mais o que fazer aqui.
    if not (_table_exists(_ITEM_TABLE) and _column_exists(_ITEM_TABLE, 'storage_device_id')):
        return

    bind = op.get_bind()

    bind.execute(
        sa.text(
            f"""
            UPDATE {_ITEM_TABLE}
            SET container_id = (
                SELECT c.id FROM {_CONTAINER_TABLE} c
                WHERE c.device_id = {_ITEM_TABLE}.storage_device_id
                  AND c.name LIKE '%{_DEFAULT_SUFFIX}'
                ORDER BY c.id ASC
                LIMIT 1
            )
            WHERE storage_device_id IS NOT NULL
              AND container_id IS NULL
            """
        )
    )

    pendentes = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {_ITEM_TABLE} "
            f"WHERE container_id IS NULL AND storage_device_id IS NULL"
        )
    ).scalar()

    if pendentes:
        print(
            f"[skill19 4/6] AVISO: {pendentes} item(ns) de bank_item já estavam "
            f"sem storage_device_id (dado legado incompleto) e continuam sem "
            f"container_id. O passo 5 vai recusar tornar a coluna obrigatória "
            f"enquanto isso não for resolvido manualmente."
        )


def downgrade():
    # Best-effort: zera de volta só os container_id que este passo
    # preencheu (identificáveis pelo nome "— Geral"), sem tentar
    # adivinhar edição manual feita pelo usuário depois do upgrade.
    if not (_table_exists(_ITEM_TABLE) and _column_exists(_ITEM_TABLE, 'container_id')):
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"""
            UPDATE {_ITEM_TABLE}
            SET container_id = NULL
            WHERE container_id IN (
                SELECT id FROM {_CONTAINER_TABLE} WHERE name LIKE '%{_DEFAULT_SUFFIX}'
            )
            """
        )
    )
