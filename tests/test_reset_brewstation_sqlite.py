"""Verifica reset real de SQLite, integridade referencial e backup."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reset_brewstation_sqlite.py'
spec = importlib.util.spec_from_file_location('reset_brewstation_sqlite', SCRIPT)
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


class ResetBrewstationSqliteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / 'tesseract_dev.db'
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE alembic_version (version_num TEXT);
                INSERT INTO alembic_version VALUES ('6abac6de2f17');
                CREATE TABLE tesseract_user (id INTEGER PRIMARY KEY);
                INSERT INTO tesseract_user VALUES (1);
                CREATE TABLE tesseract_brewstation_yeastbank_strain (id INTEGER PRIMARY KEY);
                INSERT INTO tesseract_brewstation_yeastbank_strain VALUES (3);
                CREATE TABLE tesseract_estoque_material (id INTEGER PRIMARY KEY);
                INSERT INTO tesseract_estoque_material VALUES (9);
                CREATE TABLE tesseract_estoque_movimentacao (
                    id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL
                    REFERENCES tesseract_estoque_material(id) ON DELETE RESTRICT
                );
                INSERT INTO tesseract_estoque_movimentacao VALUES (8, 9);
                CREATE TABLE tesseract_brewstation_mashctrl_recipe (id INTEGER PRIMARY KEY);
                INSERT INTO tesseract_brewstation_mashctrl_recipe VALUES (4);
                CREATE TABLE tesseract_brewstation_mashctrl_recipe_ingredient (
                    id INTEGER PRIMARY KEY, recipe_id INTEGER NOT NULL
                    REFERENCES tesseract_brewstation_mashctrl_recipe(id) ON DELETE CASCADE,
                    material_id INTEGER
                );
                INSERT INTO tesseract_brewstation_mashctrl_recipe_ingredient VALUES (5, 4, 9);
                CREATE TABLE tesseract_brewstation_mashctrl_session (
                    id INTEGER PRIMARY KEY, recipe_id INTEGER
                    REFERENCES tesseract_brewstation_mashctrl_recipe(id)
                );
                INSERT INTO tesseract_brewstation_mashctrl_session VALUES (6, 4);
                CREATE TABLE tesseract_brewstation_mashctrl_rule (
                    id INTEGER PRIMARY KEY, session_id INTEGER
                    REFERENCES tesseract_brewstation_mashctrl_session(id)
                );
                INSERT INTO tesseract_brewstation_mashctrl_rule VALUES (7, 6);
            ''')

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_preserves_data_execute_backs_up_and_clears_links(self):
        self.assertIsNone(reset.run(self.db_path))
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM tesseract_estoque_material').fetchone()[0], 1)
        backup = reset.run(self.db_path, execute=True)
        self.assertTrue(backup.is_file())
        with sqlite3.connect(backup) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM tesseract_estoque_movimentacao').fetchone()[0], 1)
        with sqlite3.connect(self.db_path) as conn:
            for table in ('tesseract_estoque_material', 'tesseract_estoque_movimentacao',
                          'tesseract_brewstation_mashctrl_recipe',
                          'tesseract_brewstation_mashctrl_recipe_ingredient',
                          'tesseract_brewstation_mashctrl_session'):
                self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT session_id FROM tesseract_brewstation_mashctrl_rule').fetchone()[0], None)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM tesseract_user').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM tesseract_brewstation_yeastbank_strain').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT version_num FROM alembic_version').fetchone()[0], '6abac6de2f17')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_unmapped_weak_reference_blocks_deletion(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE custom_material_use (id INTEGER PRIMARY KEY, material_id INTEGER);
                INSERT INTO custom_material_use VALUES (1, 9);
            ''')
        with self.assertRaisesRegex(RuntimeError, 'Referencia fraca fora do reset'):
            reset.run(self.db_path, execute=True)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM tesseract_estoque_material').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
