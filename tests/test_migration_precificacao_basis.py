"""Snapshots novos: schema legado/atual e repetição sem reescrever histórico."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize('already_present', [False, True])
def test_snapshot_migration_idempotente_preserva_historico(already_present):
    path = Path(__file__).resolve().parents[1] / 'migrations/versions/f8c214ab709e_envase_precificacao_base_snapshot.py'
    spec = importlib.util.spec_from_file_location('snapshot_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        for table, field in module._FIELDS:
            extra = f', {field} JSON' if already_present else ''
            conn.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, valor FLOAT{extra})')
            conn.exec_driver_sql(f'INSERT INTO {table} (id, valor) VALUES (1, 12.5)')
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            module.upgrade()
            for table, field in module._FIELDS:
                assert conn.exec_driver_sql(f'SELECT valor, {field} FROM {table}').one() == (12.5, None)
                conn.exec_driver_sql(f'UPDATE {table} SET {field} = ?', ('{"version":1}',))
            module.upgrade()
            for table, field in module._FIELDS:
                assert conn.exec_driver_sql(f'SELECT {field} FROM {table}').scalar() == '{"version":1}'
            module.downgrade()
            module.downgrade()
            for table, field in module._FIELDS:
                assert conn.exec_driver_sql(f'SELECT valor FROM {table}').scalar() == 12.5
                assert field not in {c['name'] for c in sa.inspect(conn).get_columns(table)}
