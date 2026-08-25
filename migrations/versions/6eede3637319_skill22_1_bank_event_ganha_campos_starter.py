"""skill 22 (1/3) - bank_event ganha campos do Starter fundido, migra
dado existente de starter_log, remove starter_id

YeastStarterLog deixa de existir como tabela própria (decisão do
Christopher: fusão total, opção B entre as duas apresentadas). Antes
de dropar a tabela (passo 3/3), este passo migra o dado real: para
todo bank_event que tinha starter_id preenchido, copia os campos do
starter_log correspondente pra dentro do próprio evento.

Ver docs/skills/22-fusao-starter-bankevent-neubauer.md.

Revision ID: 6eede3637319
Revises: 0c96b4872b54
Create Date: 2026-08-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6eede3637319'
down_revision = '0c96b4872b54'
branch_labels = None
depends_on = None

_EVENT_TABLE = 'tesseract_brewstation_yeastbank_bank_event'
_STARTER_TABLE = 'tesseract_brewstation_yeastbank_starter_log'

_NEW_COLUMNS = {
    'brew_date': sa.Date(),
    'start_date': sa.Date(),
    'target_volume_l': sa.Float(),
    'objective': sa.String(30),
    'starter_status': sa.String(30),
    'result_viability_percent': sa.Float(),
    'estimated_cells_per_ml': sa.Float(),
}


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
    if not _table_exists(_EVENT_TABLE):
        return

    # 1. Adiciona as colunas novas (nullable — nenhuma é obrigatória,
    #    só fazem sentido quando event_type="Starter").
    for col_name, col_type in _NEW_COLUMNS.items():
        if not _column_exists(_EVENT_TABLE, col_name):
            with op.batch_alter_table(_EVENT_TABLE) as batch_op:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # contamination_detected já existe em bank_event desde a skill 21
    # (usado por outra coisa)? Confirma antes de assumir — cria só se
    # realmente não existir.
    if not _column_exists(_EVENT_TABLE, 'contamination_detected'):
        with op.batch_alter_table(_EVENT_TABLE) as batch_op:
            batch_op.add_column(
                sa.Column('contamination_detected', sa.Boolean(), nullable=False, server_default=sa.false())
            )

    # 2. Migra dado real: para todo bank_event com starter_id
    #    preenchido, copia os campos do starter_log correspondente.
    if _column_exists(_EVENT_TABLE, 'starter_id') and _table_exists(_STARTER_TABLE):
        bind = op.get_bind()
        eventos_com_starter = bind.execute(
            sa.text(f"SELECT id, starter_id FROM {_EVENT_TABLE} WHERE starter_id IS NOT NULL")
        ).fetchall()

        migrados = 0
        for event_id, starter_id in eventos_com_starter:
            starter = bind.execute(
                sa.text(
                    f"SELECT brew_date, start_date, target_volume_l, objective, status, "
                    f"result_viability_percent, contamination_detected FROM {_STARTER_TABLE} "
                    f"WHERE id = :sid"
                ),
                {"sid": starter_id},
            ).fetchone()
            if starter is None:
                continue
            bind.execute(
                sa.text(
                    f"UPDATE {_EVENT_TABLE} SET brew_date = :brew_date, start_date = :start_date, "
                    f"target_volume_l = :target_volume_l, objective = :objective, "
                    f"starter_status = :starter_status, "
                    f"result_viability_percent = :result_viability_percent, "
                    f"contamination_detected = :contamination_detected "
                    f"WHERE id = :event_id"
                ),
                {
                    "brew_date": starter[0], "start_date": starter[1],
                    "target_volume_l": starter[2], "objective": starter[3],
                    "starter_status": starter[4],
                    "result_viability_percent": starter[5],
                    "contamination_detected": starter[6],
                    "event_id": event_id,
                },
            )
            migrados += 1

        if migrados:
            print(f"[skill22 1/3] {migrados} evento(s) tipo Starter migrado(s) de starter_log pra bank_event.")

    # 3. Remove starter_id — não é mais usado, os campos já foram
    #    copiados pro próprio evento no passo anterior.
    if _column_exists(_EVENT_TABLE, 'starter_id'):
        with op.batch_alter_table(_EVENT_TABLE) as batch_op:
            fk_name = None
            bind = op.get_bind()
            inspector = sa.inspect(bind)
            for fk in inspector.get_foreign_keys(_EVENT_TABLE):
                if 'starter_id' in fk.get('constrained_columns', []):
                    fk_name = fk.get('name')
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.drop_column('starter_id')


def downgrade():
    # Best-effort: recria starter_id vazio — o dado migrado pra dentro
    # do evento não é "des-migrado" automaticamente (ficaria duplicado
    # sem um jeito seguro de saber se deve virar um novo starter_log
    # ou não). Recomendado revisar manualmente após o downgrade se
    # for realmente necessário reverter em produção.
    if not _table_exists(_EVENT_TABLE):
        return

    if not _column_exists(_EVENT_TABLE, 'starter_id'):
        with op.batch_alter_table(_EVENT_TABLE) as batch_op:
            batch_op.add_column(sa.Column('starter_id', sa.Integer(), nullable=True))

    for col_name in _NEW_COLUMNS:
        if _column_exists(_EVENT_TABLE, col_name):
            with op.batch_alter_table(_EVENT_TABLE) as batch_op:
                batch_op.drop_column(col_name)
