import importlib
from decimal import Decimal
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_admin_users_pages import app, client, _login_admin
from tests.test_financeiro_foundation import setup_policy
from core.db import db
from addons.addon_financeiro.root.model.exchange import ExchangeRate, MonetaryConversion
from addons.addon_financeiro.root.services.monetary_service import create_currency
from addons.addon_financeiro.root.services.exchange_service import create_rate, preview_conversion, confirm_conversion

RATE = dict(organization_code='A', source_currency='USD', target_currency='BRL', rate='5.25', valid_on='2026-10-08', source='Contrato de teste', rate_type='MANUAL')
CONVERSION = dict(organization_code='A', source_currency='USD', amount='10.01', operation_date='2026-10-08', rate_id=1)

def setup():
    setup_policy()
    create_currency(dict(code='USD', name='Dólar', decimal_places=2))
    result = create_rate(RATE, actor='admin')
    assert result.success
    return result.data['id']


def test_precision_snapshot_idempotence_and_no_preview_write(app):
    with app.app_context():
        rid = setup()
        data = CONVERSION | {'rate_id': rid}
        preview = preview_conversion(data)
        assert preview['converted_amount'] == '52.55'
        assert preview['unrounded_amount'] == '52.5525'
        assert MonetaryConversion.query.count() == 0
        data |= dict(idempotency_key='one', reference='Compra')
        first = confirm_conversion(data, actor='admin')
        assert first.code == 201
        assert confirm_conversion(data, actor='another').data == first.data
        assert confirm_conversion(data | {'amount': '11'}, actor='admin').code == 409
        assert MonetaryConversion.query.count() == 1
        assert first.data['snapshot']['rate']['rate'] == '5.25'
        assert first.data['snapshot']['policy']['currency_code'] == 'BRL'
        newer = create_rate(RATE | {'rate': '6'}, actor='admin')
        assert newer.success and MonetaryConversion.query.one().to_dict() == first.data


@pytest.mark.parametrize('field,value', [('rate', '0'), ('rate', '-1'), ('rate', True), ('rate', 1.5), ('rate', 'NaN'), ('rate', '1e2'), ('rate', '0.0000000000001'), ('rate', '1000000000000000000'), ('valid_on','2026-02-30'), ('valid_on','2026-1-1'), ('source', ''), ('rate_type', 'AUTO'), ('source_currency','BRL'), ('target_currency','USD'), ('source_currency','ZZZ')])
def test_invalid_rates_no_write(app, field, value):
    with app.app_context():
        setup_policy(); create_currency(dict(code='USD', name='Dólar', decimal_places=2))
        assert create_rate(RATE | {field:value}, actor='admin').code == 422
        assert ExchangeRate.query.count() == 0


@pytest.mark.parametrize('change', [{'rate_id':None}, {'rate_id':True}, {'rate_id':999}, {'operation_date':'2026-10-09'}, {'source_currency':'BRL'}, {'amount':1.5}, {'amount':'NaN'}, {'amount':'1,2'}, {'amount':'999999999999999999'}, {'organization_code':'B'}])
def test_invalid_conversion_never_confirmed(app, change):
    with app.app_context():
        setup(); setup_policy('B')
        with pytest.raises(ValueError): preview_conversion(CONVERSION | change)
        result = confirm_conversion(CONVERSION | change | dict(idempotency_key='x',reference='x'), actor='admin')
        assert result.code == 422 and MonetaryConversion.query.count() == 0


@pytest.mark.parametrize('amount,expected', [('1.005','1.01'), ('-1.005','-1.01'), ('-0.001','0.00')])
def test_base_currency_no_rate(app,amount,expected):
    with app.app_context():
        setup_policy()
        result = preview_conversion(CONVERSION | dict(source_currency='BRL',amount=amount,rate_id=None))
        assert result['converted_amount'] == expected and result['rate'] is None


def test_product_precision_and_even_rounding(app):
    with app.app_context():
        setup_policy('A','HALF_EVEN'); create_currency(dict(code='USD',name='USD',decimal_places=2))
        rid = create_rate(RATE | dict(rate='1.000000000001'),actor='admin').data['id']
        result = preview_conversion(CONVERSION | dict(amount='1.005',rate_id=rid))
        assert result['unrounded_amount'] == '1.005000000001005' and result['converted_amount'] == '1.01'
        result = preview_conversion(CONVERSION | dict(source_currency='BRL',amount='1.005',rate_id=None))
        assert result['converted_amount'] == '1.00'


@pytest.mark.parametrize('model', [ExchangeRate, MonetaryConversion])
@pytest.mark.parametrize('operation', ['update','delete'])
def test_immutable_history(app, model, operation):
    with app.app_context():
        setup(); confirm_conversion(CONVERSION | dict(idempotency_key='x',reference='x'),actor='admin')
        obj = model.query.one()
        if operation == 'delete': db.session.delete(obj)
        elif model is ExchangeRate: obj.rate = '9'
        else: obj.reference = 'changed'
        with pytest.raises(ValueError): db.session.commit()
        db.session.rollback()
        assert model.query.count() == 1


def test_commit_failure_rolls_back(app,monkeypatch):
    with app.app_context():
        setup()
        def fail(): raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            assert confirm_conversion(CONVERSION | dict(idempotency_key='x',reference='x'),actor='admin').code == 409
            assert create_rate(RATE,actor='admin').code == 409
        assert MonetaryConversion.query.count() == 0 and ExchangeRate.query.count() == 1


def test_routes_forms_api_and_automatic_menu(app,client):
    assert client.get('/api/financeiro/rates').status_code == 401
    _login_admin(app,client)
    with app.app_context(): setup()
    for path in ['/financeiro/exchange-rates/', '/financeiro/conversions/']:
        assert client.get(path).status_code == 200
    response = client.post('/financeiro/exchange-rates/',data=RATE | {'rate':'0'})
    assert response.status_code == 422 and b'Contrato de teste' in response.data
    assert client.post('/api/financeiro/conversions/preview',json=CONVERSION).get_json()['item']['converted_amount'] == '52.55'
    assert client.post('/api/financeiro/conversions',json=CONVERSION | dict(idempotency_key='x',reference='Compra')).status_code == 201
    assert client.get('/api/financeiro/conversions').get_json()['total'] == 1
    assert client.post('/financeiro/conversions/',data=CONVERSION | dict(action='preview',idempotency_key='y',reference='Nova')).status_code == 200
    assert client.put('/api/financeiro/rates',json={}).status_code == 405
    with app.app_context():
        from model.core.transaction import Transaction
        for code in ['TX_AUTO_EXCHANGE_RATES','TX_AUTO_MONETARY_CONVERSIONS']:
            tx = Transaction.query.filter_by(code=code).one()
            assert tx.source_module == 'financeiro' and tx.parent_id is not None
        assert MonetaryConversion.query.count() == 1


def test_regular_user_denied(app,client):
    from model.core.user import User
    with app.app_context():
        user=User(username='regular',email='regular@test.local',nome='Regular',nome_completo='Regular',celular='11999999999',is_admin=False,is_active=True)
        user.set_password('senha123'); db.session.add(user); db.session.commit()
    client.post('/api/auth/login',json=dict(username='regular',password='senha123'))
    for path in ['/api/financeiro/rates','/api/financeiro/conversions','/api/financeiro/conversions/preview','/financeiro/exchange-rates/','/financeiro/conversions/']:
        assert client.post(path,json={}).status_code == 403


migration = importlib.import_module('migrations.versions.d04f1a65c239_financeiro_cambio')

def test_migration_existing_schema_and_guard(app,monkeypatch):
    with app.app_context(), db.engine.begin() as conn:
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        migration.upgrade(); migration.upgrade()
        conn.exec_driver_sql("INSERT INTO tesseract_financeiro_conversion(organization_code,idempotency_key,reference,snapshot,created_by,created_at) VALUES('A','x','x','{}','admin','2026-10-08')")
        with pytest.raises(RuntimeError,match='preservado'): migration.downgrade()
        assert sa.inspect(conn).has_table('tesseract_financeiro_exchange_rate')


def test_migration_empty_up_down_and_reject_partial_schema(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_monetary_policy(id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_currency(code VARCHAR(3) PRIMARY KEY)')
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        migration.upgrade(); migration.upgrade(); migration.downgrade(); migration.downgrade()
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_exchange_rate(id INTEGER PRIMARY KEY)')
        with pytest.raises(RuntimeError,match='incompatível'): migration.upgrade()
        assert not sa.inspect(conn).has_table('tesseract_financeiro_conversion')


def test_unique_collision_reuses_concurrent_winner(app,monkeypatch):
    """Simula leitura anterior ao vencedor; colisão real no UNIQUE do SQLite."""
    from sqlalchemy.orm import Query
    with app.app_context():
        setup()
        data = CONVERSION | dict(idempotency_key='concurrent',reference='Compra')
        first = confirm_conversion(data,actor='admin')
        original_first = Query.first
        stale = [True]
        def stale_first(query):
            if query.column_descriptions[0].get('entity') is MonetaryConversion and stale[0]:
                stale[0] = False
                return None
            return original_first(query)
        with monkeypatch.context() as ctx:
            ctx.setattr(Query,'first',stale_first)
            retry = confirm_conversion(data,actor='other')
        assert retry.code == 200 and retry.data == first.data
        assert MonetaryConversion.query.count() == 1


def test_inactive_organization_blocks_new_calculations_preserves_history(app):
    from services.core.organization_service import save_organization, resolve_organization_by_code
    with app.app_context():
        setup()
        result = confirm_conversion(CONVERSION | dict(idempotency_key='x',reference='Compra'),actor='admin')
        ident = resolve_organization_by_code('A')['id']
        assert save_organization({'is_active':False},ident).success
        assert create_rate(RATE,actor='admin').code == 422
        with pytest.raises(ValueError): preview_conversion(CONVERSION)
        assert MonetaryConversion.query.one().to_dict() == result.data


@pytest.mark.parametrize('value',[[],{},'NaN','Inf','1e2',True,1.5,Decimal('NaN'),Decimal('Infinity'),Decimal('0E1000000'),Decimal('1E-13')])
def test_decimal_contract_rejects_unsafe_values_without_database(value):
    from addons.addon_financeiro.root.services.exchange_service import decimal_text
    with pytest.raises(ValueError): decimal_text(value)
