"""Reparo real das FKs duplicadas; avisos são erros e dados são preservados."""
import warnings
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from migrations.sqlite_foreign_keys import repair_model_builder_foreign_keys


def test_repair_duplicate_named_unnamed_foreign_keys_preserves_data_and_constraints():
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_user (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE tesseract_model_definition (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, parent_model_definition_id INTEGER,created_by_user_id INTEGER, CONSTRAINT fk_model_definition_parent_id FOREIGN KEY(parent_model_definition_id) REFERENCES tesseract_model_definition(id), FOREIGN KEY(parent_model_definition_id) REFERENCES tesseract_model_definition(id), FOREIGN KEY(created_by_user_id) REFERENCES tesseract_user(id))')
        connection.exec_driver_sql('CREATE TABLE tesseract_model_field_definition (id INTEGER PRIMARY KEY, model_definition_id INTEGER NOT NULL, child_model_definition_id INTEGER, CONSTRAINT fk_model_field_definition_child_id FOREIGN KEY(child_model_definition_id) REFERENCES tesseract_model_definition(id), FOREIGN KEY(child_model_definition_id) REFERENCES tesseract_model_definition(id), FOREIGN KEY(model_definition_id) REFERENCES tesseract_model_definition(id))')
        connection.exec_driver_sql("INSERT INTO tesseract_user VALUES(1)")
        connection.exec_driver_sql("INSERT INTO tesseract_model_definition VALUES(1,'Pai',NULL,1),(2,'Filho',1,1)")
        connection.exec_driver_sql('INSERT INTO tesseract_model_field_definition VALUES(10,1,2)')
        before={name:connection.exec_driver_sql('SELECT * FROM '+name+' ORDER BY id').all() for name in ('tesseract_model_definition','tesseract_model_field_definition')}
        with warnings.catch_warnings():
            warnings.simplefilter('error',sa.exc.SAWarning)
            with Operations.context(MigrationContext.configure(connection)):
                repair_model_builder_foreign_keys(Operations(MigrationContext.configure(connection)))
                repair_model_builder_foreign_keys(Operations(MigrationContext.configure(connection)))
            assert len(sa.inspect(connection).get_foreign_keys('tesseract_model_definition'))==2
            assert len(sa.inspect(connection).get_foreign_keys('tesseract_model_field_definition'))==2
            sa.Table('tesseract_model_definition',sa.MetaData(),autoload_with=connection)
            sa.Table('tesseract_model_field_definition',sa.MetaData(),autoload_with=connection)
        assert before=={name:connection.exec_driver_sql('SELECT * FROM '+name+' ORDER BY id').all() for name in before}
        assert not connection.exec_driver_sql('PRAGMA foreign_key_check').all()
        assert sa.inspect(connection).get_unique_constraints('tesseract_model_definition')[0]['column_names']==['name']
