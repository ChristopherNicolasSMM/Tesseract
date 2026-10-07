import importlib
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_admin_users_pages import app, client, _login_admin
from core.db import db
from model.core.organization import Organization
from model.core.user import User
from model.core.transaction import Transaction
from services.core.organization_service import save_organization, resolve_organization


def test_identity_lifecycle_is_explicit_and_stable(app):
    with app.app_context():
        assert Organization.query.count() == 0
        result = save_organization({'code': ' fábrica_1 ', 'name': 'Fábrica'})
        assert not result.success
        result = save_organization({'code': ' brew_1 ', 'name': '  Cervejaria  '})
        assert result.success and result.code == 201
        ident = result.data['id']
        assert result.data['code'] == 'BREW_1'
        assert resolve_organization(ident)['name'] == 'Cervejaria'
        assert save_organization({'name': 'Nome atualizado', 'is_active': False}, ident).success
        with pytest.raises(ValueError):
            resolve_organization(ident)
        assert resolve_organization(ident, require_active=False)['id'] == ident
        assert save_organization({'is_active': True}, ident).success
        assert resolve_organization(ident)['code'] == 'BREW_1'


@pytest.mark.parametrize('data', [None, [], {}, {'code': True, 'name': 'A'},
    {'code': 'A', 'name': ''}, {'code': 'A', 'name': 1}, {'code': 'A', 'name': 'x'*121},
    {'code': 'x'*41, 'name': 'A'}, {'code': 'A B', 'name': 'A'},
    {'code': 'A', 'name': 'A', 'is_active': 1}, {'code': 'A', 'name': 'A', 'is_active': 'false'},
    {'code': 'A', 'name': 'A', 'currency': 'BRL'}, {'code': 'A', 'name': 'A', 'id': 2}])
def test_invalid_input_has_no_writes(app, data):
    with app.app_context():
        assert save_organization(data).code == 422
        assert Organization.query.count() == 0


def test_code_is_immutable_and_duplicate_rolls_back(app):
    with app.app_context():
        first = save_organization({'code': 'A', 'name': 'Primeira'}).data
        assert save_organization({'code': ' a ', 'name': 'Duplicada'}).code == 409
        assert save_organization({'code': 'B', 'name': 'Mudança'}, first['id']).code == 409
        assert resolve_organization(first['id'])['name'] == 'Primeira'
        assert save_organization({'code': 'B', 'name': 'Segunda'}).success
        assert save_organization({'name': 'X'}, 999999).code == 404


def test_commit_failure_preserves_name_and_active_state(app, monkeypatch):
    with app.app_context():
        ident = save_organization({'code': 'A', 'name': 'Original'}).data['id']
        def fail():
            raise sa.exc.OperationalError('commit', {}, Exception('falha induzida'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session, 'commit', fail)
            assert not save_organization({'name': 'Outra', 'is_active': False}, ident).success
        assert resolve_organization(ident)['name'] == 'Original'
        assert save_organization({'name': 'Agora'}, ident).success


@pytest.mark.parametrize('ident', [None, True, 0, -1, '1', 1.5, 999999])
def test_public_resolution_rejects_missing_identity(app, ident):
    with app.app_context(), pytest.raises(ValueError):
        resolve_organization(ident)


def test_admin_api_form_menu_and_no_delete(app, client):
    _login_admin(app, client)
    assert client.get('/admin/organizations/').status_code == 200
    response = client.post('/api/admin/organizations/', json={'code': 'BREW', 'name': '<Cervejaria>'})
    assert response.status_code == 201
    ident = response.get_json()['item']['id']
    assert client.get(f'/api/admin/organizations/{ident}').get_json()['item']['code'] == 'BREW'
    assert client.delete(f'/api/admin/organizations/{ident}').status_code == 405
    assert client.put(f'/api/admin/organizations/{ident}', json={'code': 'OUTRA'}).status_code == 409
    assert client.post(f'/admin/organizations/{ident}', data={'name': '<Novo>', 'is_active': 'on'}).status_code == 302
    page = client.get('/admin/organizations/?q=Novo').data
    assert b'&lt;Novo&gt;' in page and b'<Novo>' not in page
    assert client.get('/api/admin/organizations/?q=Novo').get_json()['items'][0]['id'] == ident
    assert client.put(f'/api/admin/organizations/{ident}', json={'is_active': False}).status_code == 200
    assert client.get(f'/api/admin/organizations/{ident}').get_json()['item']['is_active'] is False
    assert client.post('/api/admin/organizations/', json=[]).status_code == 422
    assert client.get('/api/admin/organizations/999999').status_code == 404
    with app.app_context():
        tx = Transaction.query.filter_by(code='TX_ADMIN_ORGANIZATIONS').one()
        assert tx.permission_required == 'admin' and tx.route == '/admin/organizations'


def test_regular_user_cannot_manage_organizations(app, client):
    with app.app_context():
        user = User(username='comum', email='comum@test.local', nome='Comum', nome_completo='Comum',
                    celular='11999999999', is_admin=False, is_active=True)
        user.set_password('senha123')
        db.session.add(user)
        db.session.commit()
    assert client.get('/api/admin/organizations/').status_code == 401
    client.post('/api/auth/login', json={'username': 'comum', 'password': 'senha123'})
    assert client.get('/admin/organizations/').status_code == 403
    assert client.post('/api/admin/organizations/', json={'code': 'A', 'name': 'A'}).status_code == 403
    assert client.put('/api/admin/organizations/1', json={'name': 'A'}).status_code == 403


migration = importlib.import_module('migrations.versions.a71c8d32f906_core_organizations')


def test_migration_idempotence_and_protection_of_existing_rows(monkeypatch):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        migration.upgrade()
        conn.exec_driver_sql("INSERT INTO tesseract_organization VALUES (1,'A','Org',1,'2026-10-07','2026-10-07')")
        migration.upgrade()
        with pytest.raises(RuntimeError, match='preservadas'):
            migration.downgrade()
        assert conn.exec_driver_sql('SELECT code FROM tesseract_organization').scalar() == 'A'
        conn.exec_driver_sql('DELETE FROM tesseract_organization')  # banco temporário exclusivo do teste
        migration.downgrade()
        migration.downgrade()


def test_migration_rejects_incompatible_table_without_altering_it(monkeypatch):
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE tesseract_organization(id INTEGER PRIMARY KEY, code TEXT)')
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        with pytest.raises(RuntimeError, match='incompatível'):
            migration.upgrade()
        assert len(sa.inspect(conn).get_columns('tesseract_organization')) == 2


def test_public_business_key_resolution_tracks_inactivation(app):
    from services.core.organization_service import resolve_organization_by_code
    with app.app_context():
        ident = save_organization({'code': 'BREW', 'name': 'Org'}).data['id']
        assert resolve_organization_by_code(' brew ')['id'] == ident
        assert save_organization({'is_active': False}, ident).success
        with pytest.raises(ValueError):
            resolve_organization_by_code('BREW')
        assert resolve_organization_by_code('BREW', require_active=False)['code'] == 'BREW'
        with pytest.raises(ValueError):
            resolve_organization_by_code('AUSENTE')


@pytest.mark.parametrize('ident', [True, 0, -1, '1', 1.5])
def test_save_rejects_invalid_identity_without_creating_record(app, ident):
    with app.app_context():
        assert save_organization({'code': 'A', 'name': 'A'}, ident).code == 422
        assert Organization.query.count() == 0
