"""Migration e integração HTTP dos consumidores na base atual."""
import importlib
import json
from pathlib import Path
from datetime import datetime
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from tests.test_reports_workspace import app, client, post, create, read, save
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession

MIGRATION = 'migrations.versions.c93e0f54b128_reports_catalog'


def test_migration_creates_preserves_and_drops_only_reports():
    migration = importlib.import_module(MIGRATION)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_user (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            table = migration.tables()[0]
            connection.execute(table.insert().values(id=1, key='preserved', name='Preservado',
                is_deleted=False, created_at=datetime.now(), updated_at=datetime.now()))
            migration.upgrade()
            assert connection.execute(sa.select(table.c.name)).scalar() == 'Preservado'
            migration.downgrade()
        assert sa.inspect(connection).get_table_names() == ['tesseract_user']


def test_migration_rejects_incompatible_before_creating_tables():
    migration = importlib.import_module(MIGRATION)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_reports_report_template (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match='Schema incompatível'):
                migration.upgrade()
        assert sa.inspect(connection).get_table_names() == ['tesseract_reports_report_template']


def test_migration_accepts_actual_boot_models(app):
    migration = importlib.import_module(MIGRATION)
    with app.app_context():
        with db.engine.connect() as connection:
            for table in migration.tables():
                migration.validate_existing(sa.inspect(connection), table)


def test_example_endpoint_and_unknown_name(client):
    response = client.get('/api/reports/examples/estoque-saldos')
    assert response.status_code == 200
    assert response.json['item']['sample_data']['contract'] == 'estoque.saldos.v1'
    assert client.get('/api/reports/examples/unknown').status_code == 404


def test_consumer_endpoints_auth_csrf_scope_and_html(client, app):
    obj = create(client)
    value = read(client, obj['id'])
    path = Path(__file__).resolve().parents[1] / 'addons/addon_reports/examples/brewstation-session.json'
    example = json.loads(path.read_text(encoding='utf-8'))
    value.update(example)
    assert save(client, obj['id'], value).status_code == 200
    endpoint = '/api/reports/consumers/session/templates'
    assert obj['key'] not in [i['key'] for i in client.get(endpoint).json['items']]
    assert post(client, f"/templates/{obj['id']}/versions/1/publish", {'lock_version':2}).status_code == 200
    assert obj['key'] in [i['key'] for i in client.get(endpoint).json['items']]
    assert obj['key'] not in [i['key'] for i in client.get('/api/reports/consumers/stock/templates').json['items']]
    with app.app_context():
        plant = BrewPlant(name='HTTP reports')
        db.session.add(plant); db.session.flush()
        session = BrewSession(name='Lote HTTP', plant_id=plant.id, custo_total_insumos=42.13)
        db.session.add(session); db.session.commit()
        plant_id, session_id = plant.id, session.id
    data = {'template':obj['key'], 'session_id':session_id, 'plant_id':plant_id}
    route = '/api/reports/consumers/session/render'
    assert client.post(route, json=data).status_code == 403
    wrong = post(client, '/consumers/session/render', {**data, 'plant_id':plant_id+99999})
    assert wrong.status_code == 404 and wrong.json['error']['code'] == 'reports.error.not_found'
    response = post(client, '/consumers/session/render', data)
    assert response.status_code == 200 and response.data.startswith(b'<!doctype html>') and response.mimetype == 'text/html'
    assert response.headers['Cache-Control'] == 'no-store'
    fragment = client.get(f'/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={session_id}')
    assert fragment.status_code == 200 and b'data-report-consumer="session"' in fragment.data


def test_consumer_addon_unavailable_does_not_import_domain(client, app):
    module = app.module_manager._registered_modules.pop('estoque')
    try:
        response = client.get('/api/reports/consumers/stock/templates')
        assert response.status_code == 503
        assert response.json['error']['code'] == 'reports.error.consumer_unavailable'
    finally:
        app.module_manager._registered_modules['estoque'] = module


def test_consumer_domain_permission_checked(client, monkeypatch):
    from model.core.user import User
    monkeypatch.setattr(User, 'has_permission', lambda self, name: name.startswith('report_templates.'))
    assert client.get('/api/reports/consumers/session/templates').status_code == 403
    assert client.get('/api/reports/consumers/stock/templates').status_code == 403
