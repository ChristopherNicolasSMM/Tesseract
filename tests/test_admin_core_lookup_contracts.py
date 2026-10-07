"""Contratos HTML de ID ausente e permissão após a revisão de lookup Core."""
import pytest
from tests.test_admin_users_pages import app, client, _login_admin
from core.db import db
from model.core.user import User

OPERATIONS = [
    ('GET', '/admin/users/999999'),
    ('POST', '/admin/users/999999'),
    ('POST', '/admin/users/999999/reset-password'),
    ('POST', '/admin/users/999999/deactivate'),
    ('POST', '/admin/users/999999/activate'),
    ('POST', '/admin/users/999999/roles'),
    ('GET', '/admin/roles/999999'),
    ('POST', '/admin/roles/999999'),
    ('POST', '/admin/roles/999999/permissions'),
    ('POST', '/admin/roles/999999/delete'),
    ('POST', '/admin/transactions/999999'),
    ('POST', '/admin/transactions/999999/promote'),
    ('POST', '/admin/transactions/999999/demote'),
    ('POST', '/admin/transactions/999999/toggle'),
    ('POST', '/admin/transactions/999999/delete'),
    ('POST', '/admin/field-rules/999999/toggle'),
    ('POST', '/admin/field-rules/999999/delete'),
]


@pytest.mark.parametrize(('method', 'path'), OPERATIONS)
def test_missing_id_redirects_to_management_without_mutation(app, client, method, path):
    _login_admin(app, client)
    with app.app_context():
        before = {table.name: db.session.execute(table.select()).all()
                  for table in (User.__table__,)}
    response = client.open(path, method=method, data={})
    assert response.status_code == 302
    section = path.split('/')[2]
    assert response.headers['Location'].endswith(f'/admin/{section}/')
    with app.app_context():
        assert db.session.execute(User.__table__.select()).all() == before[User.__table__.name]


@pytest.mark.parametrize(('method', 'path'), [OPERATIONS[i] for i in (0, 6, 10, 15)])
def test_regular_user_cannot_access_admin_lookup(app, client, method, path):
    with app.app_context():
        user = User(username='comum', email='comum@test.local', nome='Comum',
                    nome_completo='Usuário Comum', celular='11999999999',
                    is_admin=False, is_active=True)
        user.set_password('senha123')
        db.session.add(user)
        db.session.commit()
    response = client.post('/api/auth/login', json={'username': 'comum', 'password': 'senha123'})
    assert response.status_code == 200
    assert client.open(path, method=method, data={}).status_code == 403
