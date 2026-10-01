"""Coluna/índice de requisição em SQLite antigo e já criado pelos models."""
import importlib
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module("migrations.versions.e6274a913bc0_envase_request_key")


@pytest.mark.parametrize("current", [False, True])
def test_envase_request_key_upgrade_preserva_historico_e_unique(monkeypatch, current):
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        column = ", idempotency_key VARCHAR(32)" if current else ""
        conn.exec_driver_sql("CREATE TABLE tesseract_brewstation_env_envase (id INTEGER PRIMARY KEY, lote_id INTEGER NOT NULL" + column + ")")
        conn.exec_driver_sql("INSERT INTO tesseract_brewstation_env_envase (id, lote_id) VALUES (1, 7), (2, 7)")
        if current:
            conn.exec_driver_sql("CREATE UNIQUE INDEX uq_brewstation_envase_request_key ON tesseract_brewstation_env_envase (idempotency_key)")
        conn.commit()
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        migration.upgrade()
        conn.commit()
        assert conn.exec_driver_sql("SELECT id, lote_id, idempotency_key FROM tesseract_brewstation_env_envase ORDER BY id").all() == [(1, 7, None), (2, 7, None)]
        conn.exec_driver_sql("INSERT INTO tesseract_brewstation_env_envase (lote_id, idempotency_key) VALUES (7, 'chave')")
        conn.commit()
        with pytest.raises(sa.exc.IntegrityError):
            conn.exec_driver_sql("INSERT INTO tesseract_brewstation_env_envase (lote_id, idempotency_key) VALUES (7, 'chave')")
        conn.rollback()
        migration.downgrade()
        conn.commit()
        assert "idempotency_key" not in {c["name"] for c in sa.inspect(conn).get_columns("tesseract_brewstation_env_envase")}
        assert conn.exec_driver_sql("SELECT count(*) FROM tesseract_brewstation_env_envase").scalar() == 3
