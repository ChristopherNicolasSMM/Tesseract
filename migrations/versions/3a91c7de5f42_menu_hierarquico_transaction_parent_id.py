"""adiciona parent_id/order_index em tesseract_transaction, migra
group (string) para nos-pasta reais, remove coluna group (skill 10)

Revision ID: 3a91c7de5f42
Revises: f4c8a2d61b73
Create Date: 2026-07-02 00:00:00.000000

"""
import re
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a91c7de5f42'
down_revision = 'f4c8a2d61b73'
branch_labels = None
depends_on = None


def _slugify(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label or "").strip("_").upper()
    slug = re.sub(r"_+", "_", slug)
    return slug or "GERAL"


def upgrade():
    bind = op.get_bind()

    # ── Passo 1: schema — parent_id/order_index novos, route vira nullable ──
    with op.batch_alter_table("tesseract_transaction") as batch_op:
        batch_op.add_column(
            sa.Column(
                "parent_id", sa.Integer(),
                sa.ForeignKey("tesseract_transaction.id", name="fk_tesseract_transaction_parent_id"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))
        batch_op.alter_column("route", existing_type=sa.String(300), nullable=True)

    # ── Passo 2: dado — cada valor distinto de group vira um nó-pasta novo,
    # toda Transação daquele group recebe parent_id apontando pra ele ──
    distinct_groups = [
        row[0] for row in bind.execute(
            sa.text('SELECT DISTINCT "group" FROM tesseract_transaction WHERE "group" IS NOT NULL')
        ).fetchall()
    ]

    tx_table = sa.table(
        "tesseract_transaction",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("route", sa.String),
        sa.column("icon", sa.String),
        sa.column("parent_id", sa.Integer),
        sa.column("order_index", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_standard", sa.Boolean),
        sa.column("source_module", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    for label in distinct_groups:
        code = f"TX_GROUP_{_slugify(label)}"

        existing = bind.execute(
            sa.text("SELECT id FROM tesseract_transaction WHERE code = :code"), {"code": code}
        ).fetchone()
        if existing:
            folder_id = existing[0]
        else:
            bind.execute(
                tx_table.insert().values(
                    code=code, label=label, route=None, icon="bi-folder2",
                    parent_id=None, order_index=0, is_active=True, is_standard=True,
                    source_module=None, created_at=datetime.now(timezone.utc),
                )
            )
            # sa.table() é um proxy "leve" sem PK declarada — inserted_primary_key
            # não vem populado nele. Busca de volta por code (único), portável
            # entre SQLite/Postgres, sem depender de lastrowid.
            folder_id = bind.execute(
                sa.text("SELECT id FROM tesseract_transaction WHERE code = :code"), {"code": code}
            ).fetchone()[0]

        bind.execute(
            sa.text(
                'UPDATE tesseract_transaction SET parent_id = :folder_id '
                'WHERE "group" = :label AND code != :code AND code NOT LIKE \'TX_GROUP_%\''
            ),
            {"folder_id": folder_id, "label": label, "code": code},
        )

    # ── Passo 3: remove a coluna group — não serve mais pra nada (skill 10) ──
    with op.batch_alter_table("tesseract_transaction") as batch_op:
        batch_op.drop_column("group")


def downgrade():
    with op.batch_alter_table("tesseract_transaction") as batch_op:
        batch_op.add_column(sa.Column("group", sa.String(50), nullable=False, server_default="Core"))

    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE tesseract_transaction
        SET "group" = (
            SELECT parent.label FROM tesseract_transaction AS parent
            WHERE parent.id = tesseract_transaction.parent_id
        )
        WHERE parent_id IS NOT NULL
    """))
    bind.execute(sa.text(
        "DELETE FROM tesseract_transaction WHERE route IS NULL AND code LIKE 'TX_GROUP_%'"
    ))

    with op.batch_alter_table("tesseract_transaction") as batch_op:
        batch_op.alter_column("route", existing_type=sa.String(300), nullable=False)
        batch_op.drop_column("order_index")
        batch_op.drop_column("parent_id")
