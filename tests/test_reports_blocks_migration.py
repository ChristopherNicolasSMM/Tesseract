"""Migration cria, preserva tabela compatível e recusa schema divergente."""
import importlib.util
from pathlib import Path
from datetime import datetime
import sqlalchemy as sa
import pytest
from tests.test_reports_workspace import app


def migration():
    path=Path(__file__).resolve().parents[1]/'migrations/versions/e59f6ab8d704_reports_blocks.py'
    spec=importlib.util.spec_from_file_location('reports_blocks_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_blocks_migration_create_preserve_downgrade(monkeypatch):
    module=migration();engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE tesseract_user (id INTEGER PRIMARY KEY)'))
        monkeypatch.setattr(module.op,'get_bind',lambda:conn)
        module.upgrade();table=module.table()
        conn.execute(table.insert().values(id=1,key='test',name='Teste',node_json={'id':'test'},source_json={},content_hash='a'*64,lock_version=1,is_deleted=False,created_at=datetime.now()))
        module.upgrade()
        assert conn.execute(sa.select(table.c.key)).scalar_one()=='test'
        module.downgrade()
        assert table.name not in sa.inspect(conn).get_table_names()


def test_blocks_migration_rejects_incompatible_schema(monkeypatch):
    module=migration();engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE tesseract_reports_report_block (id INTEGER PRIMARY KEY, name TEXT)'))
        monkeypatch.setattr(module.op,'get_bind',lambda:conn)
        with pytest.raises(RuntimeError):module.upgrade()
        assert len(sa.inspect(conn).get_columns('tesseract_reports_report_block'))==2


def test_blocks_migration_accepts_table_created_by_module_boot(app, monkeypatch):
    from core.db import db
    from addons.addon_reports.root.model.report_block import ReportBlock
    module=migration()
    with app.app_context(), db.engine.begin() as conn:
        assert ReportBlock.__table__.name in sa.inspect(conn).get_table_names()
        monkeypatch.setattr(module.op,'get_bind',lambda:conn)
        module.upgrade()
