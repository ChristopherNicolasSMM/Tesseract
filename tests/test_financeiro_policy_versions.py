"""Casos funcionais de evolução monetária sem reinterpretação dos snapshots."""
import importlib
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Query
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_admin_users_pages import app, client, _login_admin
from tests.test_financeiro_foundation import setup_policy
from core.db import db
from addons.addon_financeiro.root.model.monetary import MonetaryPolicy
from addons.addon_financeiro.root.model.policy_version import MonetaryPolicyVersion
from addons.addon_financeiro.root.model.exchange import MonetaryConversion
from addons.addon_financeiro.root.services.monetary_service import quantize_amount, resolve_policy
from addons.addon_financeiro.root.services.policy_version_service import create_policy_version, resolve_selected_policy
from addons.addon_financeiro.root.services.exchange_service import preview_conversion, confirm_conversion

VERSION = dict(organization_code='A', expected_version=1, decimal_places=2,
               rounding='HALF_EVEN', valid_from='2026-10-09', reason='Revisão aprovada')
CALC = dict(organization_code='A', source_currency='BRL', amount='1.005',
            operation_date='2026-10-09', rate_id=None)


def create(data=None):
    result = create_policy_version(data or VERSION, actor='admin')
    assert result.success, result.error
    return result.data


def test_explicit_version_initial_contract_and_frozen_history(app):
    with app.app_context():
        setup_policy()
        initial = resolve_policy('A')
        payload = CALC | dict(idempotency_key='initial', reference='Anterior')
        old = confirm_conversion(payload, actor='admin')
        assert old.data['snapshot']['converted_amount'] == '1.01'
        version = create()
        assert version['version_number'] == 2 and version['currency_code'] == 'BRL'
        assert resolve_policy('A') == initial
        assert quantize_amount('1.005', 'A')['amount'] == '1.01'
        assert preview_conversion(CALC)['policy'] == initial
        revised = CALC | {'policy_version_id': version['id']}
        preview = preview_conversion(revised)
        assert preview['converted_amount'] == '1.00'
        assert preview['policy']['version_number'] == 2
        assert preview['policy']['version_id'] == version['id']
        assert quantize_amount('1.005', 'A', policy_version_id=version['id'], operation_date='2026-10-09')['amount'] == '1.00'
        assert confirm_conversion(payload, actor='another').data == old.data
        assert confirm_conversion(payload | {'policy_version_id': None}, actor='another').data == old.data
        assert confirm_conversion(payload | {'policy_version_id': version['id']}, actor='admin').code == 409
        confirmed = confirm_conversion(revised | dict(idempotency_key='revised', reference='Nova'), actor='admin')
        assert confirmed.code == 201 and confirmed.data['snapshot'] == preview
        create(VERSION | dict(expected_version=2, decimal_places=3, valid_from='2026-10-10', reason='Mais precisão'))
        assert MonetaryConversion.query.order_by(MonetaryConversion.id).first().to_dict() == old.data
        assert confirm_conversion(revised | dict(idempotency_key='revised', reference='Nova'), actor='admin').data == confirmed.data


def test_invalid_creation_inputs_have_no_write(app):
    with app.app_context():
        setup_policy()
        invalid = [None, [], {}, VERSION | {'currency_code':'USD'}, VERSION | {'extra':1}]
        invalid += [VERSION | {field:value} for field,value in [
            ('expected_version',True), ('expected_version',0), ('expected_version','1'),
            ('decimal_places',True), ('decimal_places',-1), ('decimal_places',7),
            ('rounding','AUTO'), ('rounding',[]), ('valid_from','2026-02-30'),
            ('valid_from','2026-1-1'), ('reason',''), ('reason','x'*201),
            ('organization_code','MISSING')]]
        for payload in invalid:
            result = create_policy_version(payload, actor='admin')
            assert result.code == 422, (payload, result.error)
            assert MonetaryPolicyVersion.query.count() == 0
        assert create_policy_version(VERSION, actor='').code == 422
        assert create_policy_version(VERSION | {'rounding':'HALF_UP'}, actor='admin').code == 422
        assert MonetaryPolicy.query.one().rounding == 'HALF_UP'


def test_sequence_conflict_and_non_decreasing_effective_dates(app):
    with app.app_context():
        setup_policy()
        create()
        assert create_policy_version(VERSION, actor='admin').code == 409
        earlier = VERSION | dict(expected_version=2, decimal_places=3, valid_from='2026-10-08')
        assert create_policy_version(earlier, actor='admin').code == 422
        later = create(earlier | {'valid_from':'2026-10-09'})
        assert later['version_number'] == 3
        assert [item.version_number for item in MonetaryPolicyVersion.query.order_by(MonetaryPolicyVersion.version_number)] == [2,3]


def test_version_scope_date_and_invalid_ids(app):
    with app.app_context():
        setup_policy(); setup_policy('B')
        version = create()
        for value in [True, 0, -1, '1', [], 9999]:
            with pytest.raises(ValueError): preview_conversion(CALC | {'policy_version_id':value})
        with pytest.raises(ValueError,match='organização'):
            preview_conversion(CALC | dict(organization_code='B',policy_version_id=version['id']))
        with pytest.raises(ValueError,match='ainda não válida'):
            preview_conversion(CALC | dict(operation_date='2026-10-08',policy_version_id=version['id']))
        with pytest.raises(ValueError): resolve_selected_policy('A',policy_version_id=version['id'])
        assert MonetaryConversion.query.count() == 0


def test_inactive_organization_and_immutable_versions(app):
    from services.core.organization_service import save_organization, resolve_organization_by_code
    with app.app_context():
        setup_policy()
        version = create()
        row = db.session.get(MonetaryPolicyVersion,version['id'])
        row.rounding = 'HALF_UP'
        with pytest.raises(ValueError,match='imutável'): db.session.commit()
        db.session.rollback()
        db.session.delete(row)
        with pytest.raises(ValueError,match='imutável'): db.session.commit()
        db.session.rollback()
        assert row.rounding == 'HALF_EVEN'
        ident = resolve_organization_by_code('A')['id']
        assert save_organization({'is_active':False}, ident).success
        assert create_policy_version(VERSION | {'expected_version':2}, actor='admin').code == 422
        with pytest.raises(ValueError): preview_conversion(CALC | {'policy_version_id':version['id']})
        assert MonetaryPolicyVersion.query.count() == 1


def test_rollback_on_commit_failure(app,monkeypatch):
    with app.app_context():
        setup_policy()
        def fail(): raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            assert create_policy_version(VERSION,actor='admin').code == 409
        assert MonetaryPolicyVersion.query.count() == 0
        assert create()['version_number'] == 2


def test_concurrent_number_collision_is_conflict(app,monkeypatch):
    """Leitura desatualizada seguida de violação real da unique composta."""
    with app.app_context():
        setup_policy(); create()
        original_first = Query.first
        stale = [True]
        def stale_first(query):
            if query.column_descriptions[0].get('entity') is MonetaryPolicyVersion and stale[0]:
                stale[0] = False
                return None
            return original_first(query)
        with monkeypatch.context() as ctx:
            ctx.setattr(Query,'first',stale_first)
            assert create_policy_version(VERSION | {'reason':'Concorrente'},actor='other').code == 409
        assert MonetaryPolicyVersion.query.count() == 1
        assert MonetaryPolicyVersion.query.one().reason == VERSION['reason']


def test_ui_api_menu_search_and_form_preservation(app,client):
    assert client.get('/api/financeiro/policy-versions').status_code == 401
    _login_admin(app,client)
    with app.app_context(): setup_policy()
    assert client.get('/financeiro/policy-versions/').status_code == 200
    response = client.post('/api/financeiro/policy-versions',json=VERSION)
    assert response.status_code == 201
    version_id = response.get_json()['item']['id']
    assert client.get('/api/financeiro/policy-versions?organization_code=A').get_json()['total'] == 1
    assert client.get('/api/financeiro/policy-versions?organization_code=B').get_json()['total'] == 0
    assert client.put('/api/financeiro/policy-versions',json={}).status_code == 405
    bad = VERSION | dict(expected_version='1', decimal_places='3', reason='Motivo preservado')
    response = client.post('/financeiro/policy-versions/',data=bad)
    assert response.status_code == 409 and b'Motivo preservado' in response.data
    assert b'value="1"' in response.data
    assert client.get('/financeiro/policy-versions/?q=ausente').status_code == 200
    assert 'Revisão aprovada'.encode() not in client.get('/financeiro/policy-versions/?q=ausente').data
    assert b'name="policy_version_id"' in client.get('/financeiro/conversions/').data
    data = CALC | dict(policy_version_id=str(version_id),action='preview',idempotency_key='form',reference='Form')
    response = client.post('/financeiro/conversions/',data=data)
    assert response.status_code == 200 and b'1.00' in response.data
    with app.app_context():
        from model.core.transaction import Transaction
        tx = Transaction.query.filter_by(code='TX_AUTO_POLICY_VERSIONS').one()
        assert tx.route == '/financeiro/policy-versions/' and tx.source_module == 'financeiro'
        assert MonetaryConversion.query.count() == 0


def test_non_admin_denied(app,client):
    from model.core.user import User
    with app.app_context():
        user = User(username='regular',email='regular@test.local',nome='Regular',nome_completo='Regular',celular='11999999999',is_admin=False,is_active=True)
        user.set_password('senha123');db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json=dict(username='regular',password='senha123'))
    assert client.get('/api/financeiro/policy-versions').status_code == 403
    assert client.post('/api/financeiro/policy-versions',json=VERSION).status_code == 403
    assert client.get('/financeiro/policy-versions/').status_code == 403
    assert client.post('/financeiro/policy-versions/',data=VERSION).status_code == 403


migration = importlib.import_module('migrations.versions.e15a2b76d340_financeiro_policy_versions')

def test_migration_current_schema_and_populated_downgrade_guard(app,monkeypatch):
    with app.app_context():
        setup_policy(); create()
        with db.engine.begin() as conn:
            monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
            migration.upgrade(); migration.upgrade()
            with pytest.raises(RuntimeError,match='preservadas'): migration.downgrade()
            assert sa.inspect(conn).has_table(migration.NAME)
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM tesseract_financeiro_monetary_policy').scalar() == 1


def test_migration_preserves_initial_and_empty_upgrade_downgrade(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_monetary_policy(id INTEGER PRIMARY KEY, organization_code TEXT)')
        conn.exec_driver_sql("INSERT INTO tesseract_financeiro_monetary_policy VALUES(1,'A')")
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        migration.upgrade();migration.upgrade();migration.downgrade();migration.downgrade()
        assert conn.exec_driver_sql('SELECT id,organization_code FROM tesseract_financeiro_monetary_policy').one() == (1,'A')
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_policy_version(id INTEGER PRIMARY KEY)')
        with pytest.raises(RuntimeError,match='incompatível'): migration.upgrade()


def test_list_permission_does_not_grant_write_or_show_form(app,client):
    from model.core.user import User
    from model.core.role import Role
    from model.core.permission import Permission
    with app.app_context():
        setup_policy();create()
        permission = Permission.query.filter_by(name='policy_versions.list').first()
        if permission is None:
            permission = Permission(name='policy_versions.list')
        role = Role(name='finance_reader');role.permissions.append(permission)
        user = User(username='reader',email='reader@test.local',nome='Reader',nome_completo='Reader',celular='11999999999',is_admin=False,is_active=True)
        user.set_password('senha123');user.roles.append(role)
        db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json=dict(username='reader',password='senha123'))
    response = client.get('/financeiro/policy-versions/')
    assert response.status_code == 200 and b'2 / #1' in response.data
    assert b'id="version-org"' not in response.data
    assert client.post('/financeiro/policy-versions/',data=VERSION).status_code == 403
    assert client.get('/api/financeiro/policy-versions').status_code == 403


def test_real_template_js_preserves_conflict_expectation(app,client):
    """Executa o script renderizado, com DOM mínimo, sem alegar teste visual."""
    import re
    import json
    import subprocess
    _login_admin(app,client)
    html = client.get('/financeiro/policy-versions/').get_data(as_text=True)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    script = next(item for item in scripts if "getElementById('version-org')" in item)
    harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const script = JSON.parse(fs.readFileSync(0,'utf8'));
function run(version, oldValue, absent=false) {
  const listeners = {};
  const org = {options:[{dataset: version ? {version,summary:'Última versão '+version} : {}}],selectedIndex:0,addEventListener:(name,fn)=>listeners[name]=fn};
  const expected = {value:oldValue}; const summary = {textContent:''};
  const document = {getElementById:id=>id==='version-org'?(absent?null:org):id==='expected_version'?expected:summary};
  vm.runInNewContext(script,{document},{timeout:1000});
  return {org,expected,summary,listeners};
}
run('', '', true);
assert.equal(run('', '').expected.value,'');
assert.equal(run('1', '').expected.value,'1');
const conflict = run('2','1');
assert.equal(conflict.expected.value,'1');
assert.equal(conflict.summary.textContent,'Última versão 2');
conflict.org.options[0].dataset={version:'3',summary:'Versão 3'};
conflict.listeners.change();assert.equal(conflict.expected.value,'3');
conflict.org.options[0].dataset={};conflict.listeners.change();assert.equal(conflict.expected.value,'');
console.log('6 cenários do script real aprovados');
'''
    result = subprocess.run(['node','-e',harness],input=json.dumps(script),text=True,capture_output=True,timeout=10)
    assert result.returncode == 0, result.stderr
    assert '6 cenários' in result.stdout
