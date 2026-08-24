"""remove 5 campos vestigiais do yeast_bank (BACKLOG Fase 18)

Auditoria de uso real (grep no codigo) encontrou 5 colunas sem
nenhum consumidor alem do proprio CRUD: o nome de cada uma sugeria
uma funcionalidade que nunca foi implementada. Decisao do Christopher
(2026-08-21): remover as 5.

- strain.viability_model (modelo exponencial nunca funcionou -
  viability_model removido inteiro, so linear a partir de agora)
- starter_log.action_on_bank_item
- cell_count_history.calc_method_id
- cell_count_history.raw_inputs
- bank_event.metadata_json
- storage_device.virtual_address

Ver docs/technical/04-modelo-de-dados.md (feature_yeast_bank) para o
levantamento completo de uso por campo.

Revision ID: fe43a3c39159
Revises: 411e8426f997
Create Date: 2026-08-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe43a3c39159'
down_revision = '411e8426f997'
branch_labels = None
depends_on = None

_DROPS = [
    ('tesseract_brewstation_yeastbank_strain', 'viability_model'),
    ('tesseract_brewstation_yeastbank_starter_log', 'action_on_bank_item'),
    ('tesseract_brewstation_yeastbank_cell_count_history', 'calc_method_id'),
    ('tesseract_brewstation_yeastbank_cell_count_history', 'raw_inputs'),
    ('tesseract_brewstation_yeastbank_bank_event', 'metadata_json'),
    ('tesseract_brewstation_yeastbank_storage_device', 'virtual_address'),
]


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    for table_name, column_name in _DROPS:
        if _column_exists(table_name, column_name):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column(column_name)


def downgrade():
    # Best-effort: volta a coluna nullable e vazia — o dado original
    # (se algum dia foi preenchido) não é recuperável a partir daqui.
    restores = {
        'viability_model': sa.String(50),
        'action_on_bank_item': sa.String(30),
        'calc_method_id': sa.String(80),
        'raw_inputs': sa.Text(),
        'metadata_json': sa.Text(),
        'virtual_address': sa.String(180),
    }
    for table_name, column_name in _DROPS:
        if not _column_exists(table_name, column_name):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column(column_name, restores[column_name], nullable=True))
