"""Catálogo de blocos; preserva tabela compatível criada no boot."""
from alembic import op
import sqlalchemy as sa
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

revision = 'e59f6ab8d704'
down_revision = 'b48d5e09a673'
branch_labels = depends_on = None


def table():
    metadata=sa.MetaData()
    sa.Table('tesseract_user',metadata,sa.Column('id',sa.Integer,primary_key=True))
    return sa.Table('tesseract_reports_report_block',metadata,
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('key',sa.String(100),unique=True,nullable=False),
        sa.Column('name',sa.String(120),nullable=False),
        sa.Column('node_json',sa.JSON,nullable=False),
        sa.Column('source_json',sa.JSON,nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('lock_version',sa.Integer,nullable=False),
        sa.Column('is_deleted',sa.Boolean,nullable=False),
        sa.Column('created_by_user_id',sa.Integer,sa.ForeignKey('tesseract_user.id')),
        sa.Column('created_at',sa.DateTime,nullable=False),
        sa.Column('deleted_at',sa.DateTime))


def upgrade():
    bind=op.get_bind();definition=table();inspector=sa.inspect(bind)
    if definition.name in inspector.get_table_names():
        spec=spec_from_file_location('reports_catalog_migration',Path(__file__).with_name('c93e0f54b128_reports_catalog.py'))
        module=module_from_spec(spec);spec.loader.exec_module(module)
        module.validate_existing(inspector,definition)
    else:definition.create(bind)


def downgrade():
    definition=table()
    if definition.name in sa.inspect(op.get_bind()).get_table_names():definition.drop(op.get_bind())
