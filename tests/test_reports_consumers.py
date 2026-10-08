"""Contratos de domínio reais: leitura, escopo e custos registrados."""
import json
import uuid
from pathlib import Path
import pytest
from flask_login import login_user
from werkzeug.exceptions import HTTPException
from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.model.origem import Origem
from addons.addon_estoque.root.model.tipo_produto import TipoProduto
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.services.report_data_service import build_stock_report_data
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.services.report_data_service import build_session_report_data


@pytest.fixture(scope='module')
def app():
    return create_app(env='testing')


@pytest.fixture
def context(app):
    with app.test_request_context():
        suffix = uuid.uuid4().hex
        user = User(username=suffix, email=suffix+'@test.local', nome='Teste',
                    nome_completo='Teste', celular='11999999999', is_admin=True, is_active=True)
        user.set_password('test-only-password')
        db.session.add(user); db.session.commit(); login_user(user)
        yield
        db.session.rollback()


def test_stock_preserves_recorded_values_and_pending_changes(context):
    suffix = uuid.uuid4().hex
    category = Categoria(descricao=suffix, codigo=suffix[:20])
    db.session.add(category); db.session.flush()
    material = Material(nome=suffix, sku=suffix, origem_id=Origem.query.first().id,
                        tipo_produto_id=TipoProduto.query.first().id, categoria_id=category.id)
    db.session.add(material); db.session.flush()
    saldo = Saldo(material_id=material.id, quantidade_atual=0, custo_medio=None,
                  valor_total_estoque=123.45, estoque_minimo=1)
    db.session.add(saldo); db.session.commit()
    material_id = material.id
    material.nome = 'Alteração pendente'
    data = build_stock_report_data()
    item = next(item for item in data['items'] if item['material_id'] == material_id)
    assert item['nome'] == suffix  # A leitura não causa autoflush no consumidor.
    assert item['quantidade_atual'] == '0.0'
    assert item['custo_medio'] is None
    assert item['valor_total_estoque'] == '123.45'  # Não recalcular como zero!
    assert item['status'] == 'abaixo_minimo'
    assert material in db.session.dirty
    json.dumps(data, allow_nan=False)
    db.session.rollback()
    saldo.is_deleted = True; db.session.commit()
    assert not any(item['material_id'] == material.id for item in build_stock_report_data()['items'])


def test_session_scope_cost_and_steps(context):
    plant = BrewPlant(name='Relatório '+uuid.uuid4().hex)
    db.session.add(plant); db.session.flush()
    session = BrewSession(name='Lote', plant_id=plant.id, custo_total_insumos=42.13, volume_real_litros=0)
    db.session.add(session); db.session.flush()
    db.session.add_all([
        BrewSessionStep(session_id=session.id, step_index=2, name='Segundo', actual_duration_s=123),
        BrewSessionStep(session_id=session.id, step_index=1, name='Primeiro'),
        BrewSessionStep(session_id=session.id, step_index=0, name='Excluído', is_deleted=True),
    ]); db.session.commit()
    data = build_session_report_data(session.id, plant_id=plant.id)
    assert data['session']['custo_total_insumos'] == '42.13'
    assert data['session']['volume_real_litros'] == '0.0'
    assert [s['name'] for s in data['steps']] == ['Primeiro', 'Segundo']
    assert data['steps'][1]['actual_duration_s'] == 123
    assert not db.session.new and not db.session.dirty and not db.session.deleted
    json.dumps(data, allow_nan=False)
    with pytest.raises(HTTPException) as error:
        build_session_report_data(session.id, plant_id=plant.id+99999)
    assert error.value.code == 404
    plant.is_deleted = True; db.session.commit()
    with pytest.raises(HTTPException) as error:
        build_session_report_data(session.id, plant_id=plant.id)
    assert error.value.code == 404


@pytest.mark.parametrize('builder,args', [(build_stock_report_data, {}), (build_session_report_data, {'session_id':1,'plant_id':1})])
def test_consumer_auth_required(app, builder, args):
    with app.test_request_context():
        with pytest.raises(HTTPException) as error:
            builder(**args)
        assert error.value.code == 401


def test_domain_permission_required(context):
    from flask_login import current_user
    current_user.is_admin = False
    with pytest.raises(HTTPException) as error:
        build_stock_report_data()
    assert error.value.code == 403
    with pytest.raises(HTTPException) as error:
        build_session_report_data(1, plant_id=1)
    assert error.value.code == 403


@pytest.mark.parametrize('name', ['estoque-saldos', 'brewstation-session'])
def test_examples_use_production_schema_and_compositor(name):
    from addons.addon_reports.root.services.report_layout_service import validate_schema, validate_data, ReportLayoutService
    path = Path(__file__).resolve().parents[1] / 'addons/addon_reports/examples' / (name+'.json')
    example = json.loads(path.read_text(encoding='utf-8'))
    validate_schema(example['data_schema'])
    validate_data(example['data_schema'], example['sample_data'])
    html = ReportLayoutService.render(example['layout'], example['sample_data'], {})
    assert '<table' in html
    assert ('Malte Pilsen' if name == 'estoque-saldos' else 'Sacarificação') in html


def test_session_consumer_emits_published_html(context):
    from addons.addon_reports.root.services import report_template_service as reports
    from addons.addon_brewstation.features.feature_mash_control.services.report_data_service import generate_session_report
    example_path = Path(__file__).resolve().parents[1] / 'addons/addon_reports/examples/brewstation-session.json'
    example = json.loads(example_path.read_text(encoding='utf-8'))
    template = reports.create_template({'key':'pilot.'+uuid.uuid4().hex, 'name':'Piloto'})
    revision = reports.read_version(template['id'], 1)
    reports.save_version(template['id'], 1, {**example, 'lock_version':revision['lock_version']})
    revision = reports.read_version(template['id'], 1)
    reports.publish(template['id'], 1, revision['lock_version'], {})
    plant = BrewPlant(name='PDF '+uuid.uuid4().hex)
    db.session.add(plant); db.session.flush()
    session = BrewSession(name='Lote PDF', plant_id=plant.id, custo_total_insumos=123.45)
    db.session.add(session); db.session.commit()
    html = generate_session_report(template['key'], session.id, plant_id=plant.id, version=1)
    assert html.startswith('<!doctype html>')
    assert 'Lote PDF' in html and '123.45' in html
