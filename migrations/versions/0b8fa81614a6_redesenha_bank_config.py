"""redesenha bank_config: decaimento + validade + alerta por storage_type

Decisao do Christopher (2026-08-21, BACKLOG Fase 18): os 4 campos de
validade antigos (expiry_master_days/expiry_work_days/expiry_plate_days/
expiry_saline_days) nunca tiveram consumidor e nao faziam sentido numa
linha ja especifica de 1 storage_type. Substituidos por:
- daily_viability_loss_pct: decaimento que SUBSTITUI o da YeastStrain
  quando presente (viability_engine.recalculate_all())
- expiry_days: unico campo de validade, usado pra auto-preencher
  YeastBankItem.expiry_date (yeast_bank_item_service_hooks.py)
- alert_days_before_expiry / alert_min_viability_pct: limites de
  alerta (logica de disparo fica pra fase propria, so os limites
  entram aqui)

storage_type passa a ser UNIQUE — 1 config por tipo, nao mais N
livres. Migration verifica duplicata existente antes de tentar criar
a constraint e recusa avancar com instrucao clara, em vez de escolher
uma linha arbitrariamente e apagar as outras.

Ver docs/technical/04-modelo-de-dados.md (feature_yeast_bank).

Revision ID: 0b8fa81614a6
Revises: fe43a3c39159
Create Date: 2026-08-21 00:00:00.000001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b8fa81614a6'
down_revision = 'fe43a3c39159'
branch_labels = None
depends_on = None

_TABLE = 'tesseract_brewstation_yeastbank_bank_config'

_OLD_COLUMNS = ['expiry_master_days', 'expiry_work_days', 'expiry_plate_days', 'expiry_saline_days']
_NEW_COLUMNS = {
    'daily_viability_loss_pct': sa.Float(),
    'expiry_days': sa.Integer(),
    'alert_days_before_expiry': sa.Integer(),
    'alert_min_viability_pct': sa.Float(),
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


def _has_unique_index_ativo(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for ix in inspector.get_indexes(table_name):
        if ix.get("name") == "uq_bank_config_storage_type_ativo":
            return True
    return False


def upgrade():
    if not _table_exists(_TABLE):
        return

    # 1. Adiciona as colunas novas (nullable — sem valor obrigatório
    #    pra não quebrar linhas já existentes).
    for col_name, col_type in _NEW_COLUMNS.items():
        if not _column_exists(_TABLE, col_name):
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # 2. Remove as colunas antigas.
    for col_name in _OLD_COLUMNS:
        if _column_exists(_TABLE, col_name):
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(col_name)

    # 3. Recusa avançar se existir storage_type ATIVO duplicado —
    #    nunca escolhe uma linha arbitrariamente e apaga as outras.
    #    Índice parcial (só is_deleted=0), não UNIQUE de coluna cheia:
    #    achado real ao validar esta migration — uma constraint UNIQUE
    #    simples colide até com linha JÁ NA LIXEIRA (SQLite não sabe
    #    que is_deleted=1 não deveria contar), o que travaria a
    #    lixeira de ter mais de um "Seca" descartado ao longo do
    #    tempo. Índice parcial resolve isso de vez.
    if not _has_unique_index_ativo(_TABLE):
        bind = op.get_bind()
        duplicados = bind.execute(
            sa.text(
                f"SELECT storage_type, COUNT(*) as total FROM {_TABLE} "
                f"WHERE is_deleted = 0 GROUP BY storage_type HAVING COUNT(*) > 1"
            )
        ).fetchall()

        if duplicados:
            tipos = ", ".join(f"'{row[0]}' ({row[1]}x)" for row in duplicados)
            raise RuntimeError(
                f"bank_config redesign: existe mais de uma config ATIVA para o(s) "
                f"tipo(s) de armazenamento: {tipos}. Cada storage_type só pode ter "
                f"1 config ativa a partir de agora (linhas na lixeira não contam). "
                f"Mova o(s) registro(s) extra(s) pra lixeira (is_deleted=1) ou "
                f"consolide manualmente, e rode 'flask db upgrade' de novo."
            )

        op.create_index(
            'uq_bank_config_storage_type_ativo',
            _TABLE,
            ['storage_type'],
            unique=True,
            sqlite_where=sa.text('is_deleted = 0'),
        )


def downgrade():
    if not _table_exists(_TABLE):
        return

    if _has_unique_index_ativo(_TABLE):
        op.drop_index('uq_bank_config_storage_type_ativo', table_name=_TABLE)

    for col_name in _OLD_COLUMNS:
        if not _column_exists(_TABLE, col_name):
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(sa.Column(col_name, sa.Integer(), nullable=True))

    for col_name in _NEW_COLUMNS:
        if _column_exists(_TABLE, col_name):
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(col_name)
