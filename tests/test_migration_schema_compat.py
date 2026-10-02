"""Downgrade SQLite com nomes históricos e nomes/ausência de nome dos models."""
import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from migrations.schema_compat import drop_columns_with_references

migration = importlib.import_module('migrations.versions.0d7080cf1fe8_skill24_correcao_item_processo_cotacao')


@pytest.mark.parametrize('named', [False, True])
def test_drop_columns_preserva_referencias_e_indices_nao_removidos(named):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE parent (id INTEGER PRIMARY KEY)')
        name = 'CONSTRAINT historico ' if named else ''
        conn.exec_driver_sql(f'CREATE TABLE child (id INTEGER PRIMARY KEY, removed_id INTEGER, kept_id INTEGER, {name}FOREIGN KEY(removed_id) REFERENCES parent(id), FOREIGN KEY(kept_id) REFERENCES parent(id))')
        conn.exec_driver_sql('CREATE INDEX nome_real_removed ON child(removed_id)')
        conn.exec_driver_sql('CREATE INDEX nome_real_kept ON child(kept_id)')
        conn.exec_driver_sql('INSERT INTO parent VALUES(1)')
        conn.exec_driver_sql('INSERT INTO child VALUES(7,1,1)')
        operations = Operations(MigrationContext.configure(conn))
        drop_columns_with_references(operations, 'child', ['removed_id'])
        assert conn.exec_driver_sql('SELECT * FROM child').all() == [(7, 1)]
        assert [fk['constrained_columns'] for fk in sa.inspect(conn).get_foreign_keys('child')] == [['kept_id']]
        assert {i['name'] for i in sa.inspect(conn).get_indexes('child')} == {'nome_real_kept'}
        assert conn.exec_driver_sql('PRAGMA foreign_key_check').all() == []


@pytest.mark.parametrize('named', [False, True])
def test_downgrade_item_cotacao_recupera_dados_e_preserva_pedido(monkeypatch, named):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        for table in ['material', 'material_unidade', 'item_pedido_compra']:
            conn.exec_driver_sql(f'CREATE TABLE tesseract_estoque_{table} (id INTEGER PRIMARY KEY)')
            conn.exec_driver_sql(f'INSERT INTO tesseract_estoque_{table} VALUES(1)')
        conn.exec_driver_sql('CREATE TABLE tesseract_estoque_item_processo_cotacao (id INTEGER PRIMARY KEY, material_id INTEGER, material_unidade_id INTEGER, quantidade_desejada FLOAT NOT NULL)')
        conn.exec_driver_sql('INSERT INTO tesseract_estoque_item_processo_cotacao VALUES(1,1,1,12)')
        name = 'CONSTRAINT fk_item_cotacao_item_processo_cotacao_id ' if named else ''
        conn.exec_driver_sql(f'CREATE TABLE tesseract_estoque_item_cotacao (id INTEGER PRIMARY KEY, item_processo_cotacao_id INTEGER NOT NULL, quantidade_ofertada FLOAT, pedido_compra_item_id INTEGER, {name}FOREIGN KEY(item_processo_cotacao_id) REFERENCES tesseract_estoque_item_processo_cotacao(id), FOREIGN KEY(pedido_compra_item_id) REFERENCES tesseract_estoque_item_pedido_compra(id))')
        index = 'ix_item_cotacao_item_processo_cotacao_id' if named else 'ix_tesseract_estoque_item_cotacao_item_processo_cotacao_id'
        conn.exec_driver_sql(f'CREATE INDEX {index} ON tesseract_estoque_item_cotacao(item_processo_cotacao_id)')
        conn.exec_driver_sql('INSERT INTO tesseract_estoque_item_cotacao VALUES(1,1,NULL,1),(2,1,8,1),(3,1,0,1)')
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.downgrade()
        assert conn.exec_driver_sql('SELECT id,material_id,material_unidade_id,quantidade,pedido_compra_item_id FROM tesseract_estoque_item_cotacao ORDER BY id').all() == [(1,1,1,12,1),(2,1,1,8,1),(3,1,1,0,1)]
        assert 'tesseract_estoque_item_processo_cotacao' not in sa.inspect(conn).get_table_names()
        assert {tuple(fk['constrained_columns']) for fk in sa.inspect(conn).get_foreign_keys('tesseract_estoque_item_cotacao')} == {('material_id',), ('material_unidade_id',), ('pedido_compra_item_id',)}
        assert conn.exec_driver_sql('PRAGMA foreign_key_check').all() == []


@pytest.mark.parametrize('named', [False, True])
def test_downgrade_categoria_preserva_descricao_como_nome(monkeypatch, named):
    category = importlib.import_module('migrations.versions.7faf3d2c92ca_inicio_ajustes_estoque_categoria')
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        names = ('CONSTRAINT uq_categoria_descricao ', 'CONSTRAINT uq_categoria_codigo ') if named else ('', '')
        conn.exec_driver_sql(f'CREATE TABLE tesseract_estoque_categoria (id INTEGER PRIMARY KEY, descricao VARCHAR(100) NOT NULL, codigo VARCHAR(20) NOT NULL, {names[0]}UNIQUE(descricao), {names[1]}UNIQUE(codigo))')
        conn.exec_driver_sql("INSERT INTO tesseract_estoque_categoria VALUES(1,'Maltes','MAL')")
        monkeypatch.setattr(category, 'op', Operations(MigrationContext.configure(conn)))
        category.downgrade()
        assert conn.exec_driver_sql('SELECT id,nome FROM tesseract_estoque_categoria').all() == [(1,'Maltes')]
        assert not sa.inspect(conn).get_columns('tesseract_estoque_categoria')[1]['nullable']


def test_downgrade_item_orfao_interrompe_antes_de_alterar_schema(monkeypatch):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE tesseract_estoque_item_processo_cotacao (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE tesseract_estoque_item_cotacao (id INTEGER PRIMARY KEY, item_processo_cotacao_id INTEGER)')
        conn.exec_driver_sql('INSERT INTO tesseract_estoque_item_cotacao VALUES(1,999)')
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        with pytest.raises(RuntimeError, match='sem item de processo'):
            migration.downgrade()
        assert conn.exec_driver_sql('SELECT * FROM tesseract_estoque_item_cotacao').all() == [(1,999)]
        assert len(sa.inspect(conn).get_columns('tesseract_estoque_item_cotacao')) == 2
