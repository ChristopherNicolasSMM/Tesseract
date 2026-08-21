"""skill 19 (2/6) - cria Container "[Dispositivo] - Geral" para cada
YeastStorageDevice ja existente

Passo de dados puro — nenhuma coluna muda de shape aqui. Prepara o
destino do backfill de tesseract_brewstation_yeastbank_bank_item.container_id
que o passo 4 vai fazer. Idempotente: só cria o Container "Geral" de um
device se ainda não existir um (permite rodar upgrade de novo sem
duplicar em caso de retomada após falha parcial).

Ver docs/skills/19-proposta-reestruturacao-yeast-bank-container.md.

Revision ID: 77ebb453fa4c
Revises: 9bf9a32dfd5d
Create Date: 2026-08-20 00:00:00.000001

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77ebb453fa4c'
down_revision = '9bf9a32dfd5d'
branch_labels = None
depends_on = None

_DEVICE_TABLE = 'tesseract_brewstation_yeastbank_storage_device'
_CONTAINER_TABLE = 'tesseract_brewstation_yeastbank_container'
_DEFAULT_SUFFIX = ' — Geral'


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    if not (_table_exists(_DEVICE_TABLE) and _table_exists(_CONTAINER_TABLE)):
        return

    bind = op.get_bind()
    now = datetime.now(timezone.utc).isoformat(sep=' ', timespec='microseconds')

    devices = bind.execute(
        sa.text(f"SELECT id, name FROM {_DEVICE_TABLE} WHERE is_deleted = 0")
    ).fetchall()

    for device_id, device_name in devices:
        default_name = f"{device_name}{_DEFAULT_SUFFIX}"

        already_has_default = bind.execute(
            sa.text(
                f"SELECT id FROM {_CONTAINER_TABLE} "
                f"WHERE device_id = :device_id AND name = :name"
            ),
            {"device_id": device_id, "name": default_name},
        ).first()

        if already_has_default:
            continue

        bind.execute(
            sa.text(
                f"INSERT INTO {_CONTAINER_TABLE} "
                f"(name, container_type, device_id, description, is_deleted, created_at, updated_at) "
                f"VALUES (:name, 'Outro', :device_id, :description, 0, :now, :now)"
            ),
            {
                "name": default_name,
                "device_id": device_id,
                "description": (
                    "Container criado automaticamente pela migration da skill 19 "
                    "para preservar os itens já cadastrados neste dispositivo."
                ),
                "now": now,
            },
        )


def downgrade():
    # Remove só os Containers "Geral" criados por este passo — nunca
    # containers reais que o usuário tenha criado/renomeado depois.
    if not (_table_exists(_DEVICE_TABLE) and _table_exists(_CONTAINER_TABLE)):
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"DELETE FROM {_CONTAINER_TABLE} "
            f"WHERE name LIKE '%{_DEFAULT_SUFFIX}' "
            f"AND description LIKE 'Container criado automaticamente%'"
        )
    )
