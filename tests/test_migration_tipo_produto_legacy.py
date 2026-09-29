"""Migração de TipoProduto com categorias que referenciam IDs legados."""
import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


migration = importlib.import_module(
    'migrations.versions.ee29a41c68f2_normaliza_tipo_produto_estoque'
)


def test_upgrade_preserva_tipos_ids_e_categorias(monkeypatch):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        conn.exec_driver_sql('''CREATE TABLE tesseract_estoque_tipo_produto (
            id INTEGER PRIMARY KEY, nome VARCHAR(100) UNIQUE NOT NULL
        )''')
        conn.exec_driver_sql('''CREATE TABLE tesseract_estoque_categoria (
            id INTEGER PRIMARY KEY, tipo_produto_id INTEGER NOT NULL
            REFERENCES tesseract_estoque_tipo_produto(id)
        )''')
        conn.exec_driver_sql("INSERT INTO tesseract_estoque_tipo_produto VALUES (3, 'Insumo')")
        conn.exec_driver_sql("INSERT INTO tesseract_estoque_tipo_produto VALUES (9, 'Malte Especial')")
        conn.exec_driver_sql('INSERT INTO tesseract_estoque_categoria VALUES (7, 3)')
        conn.commit()

        context = MigrationContext.configure(conn)
        monkeypatch.setattr(migration, 'op', Operations(context))
        migration.upgrade()
        migration.upgrade()  # repeticao apos uma tentativa parcialmente aplicada
        conn.commit()

        assert conn.execute(sa.text(
            'SELECT id, descricao, codigo FROM tesseract_estoque_tipo_produto ORDER BY id'
        )).all() == [(3, 'Insumo', 'INSUMO'), (9, 'Malte Especial', 'MALTE_ESPECIAL')]
        assert conn.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        with pytest.raises(sa.exc.IntegrityError):
            conn.exec_driver_sql(
                "INSERT INTO tesseract_estoque_tipo_produto (descricao) VALUES ('sem codigo')"
            )
        conn.rollback()
