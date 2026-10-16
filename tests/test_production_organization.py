"""Contrato integrado: organização, custo, reconciliação e rollback."""
from decimal import Decimal
from uuid import uuid4
import pytest
from tests.test_organization_recipe_preview import app, client, setup, move, _login_admin
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.production_organization import ProductionOrganization, ProductionConsumption
from addons.addon_brewstation.features.feature_mash_control.services.production_organization_service import bind, consume
from addons.addon_brewstation.features.feature_envase.services.envase_estoque_service import registrar_envase, estornar_envase
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_estoque.root.services import estoque_service as stock
from addons.addon_estoque.root.model.organization_stock import OrganizationMovement, OrganizationBalance
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from tests.test_addon_estoque import _criar_material

DATE = '2026-10-16'


def lot():
    recipe, material, plant = setup()
    row = BrewSession(name='Lote organizacional', recipe_id=recipe.id, plant_id=plant.id, volume_real_litros=10)
    db.session.add(row); db.session.commit()
    return row, material


def link(row, code='A'):
    return bind(row.id, {'organization_code': code, 'operation_date': DATE, 'policy_version_id': None}, actor='admin')


def reconciliation(material):
    return dict(organization_code='A', material_id=material.id, quantity='2', source_currency='BRL',
        source_amount='7.21', operation_date=DATE, rate_id=None, policy_version_id=None,
        idempotency_key='MIGRAR-1', reason='Inventário conferido e avaliação documental')


def test_consumption_scoped_aggregated_exact_and_replayed(app):
    with app.app_context():
        row, material = lot(); link(row)
        move(material, quantity='5', cost='0.333333333333')
        stock._registrar_movimentacao_legada(material.id, 'entrada', 100, custo_unitario=99)
        result = consume(row.id, actor='admin')
        assert result['custo_total_insumos'] == '1.67' and len(result['resultados']) == 1
        assert stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual'] == '0.0'
        assert stock.consultar_saldo(material.id)['quantidade_atual'] == 100
        count = OrganizationMovement.query.count()
        assert consume(row.id, actor='admin')['ja_confirmado']
        assert OrganizationMovement.query.count() == count


def test_no_implicit_org_no_global_fallback_and_rollback(app):
    with app.app_context():
        row, material = lot()
        with pytest.raises(ValueError, match='Vincule'): consume(row.id, actor='admin')
        link(row); move(material, quantity='4', cost='2')
        stock._registrar_movimentacao_legada(material.id, 'entrada', 100, custo_unitario=99)
        with pytest.raises(ValueError, match='insuficiente'): consume(row.id, actor='admin')
        assert ProductionConsumption.query.count() == 0
        assert db.session.get(BrewSession, row.id).insumos_baixados_em is None
        assert stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual'] == '4'


def test_binding_immutable_idempotent_and_historical_not_reattributed(app):
    with app.app_context():
        row, _ = lot(); original = link(row)
        assert link(row) == original
        with pytest.raises(ValueError, match='outros dados'): link(row, 'B')
        record = db.session.get(ProductionOrganization, row.id); record.organization_code = 'B'
        with pytest.raises(ValueError, match='imutáveis'): db.session.commit()
        db.session.rollback()
        from datetime import datetime
        other = BrewSession(name='Antigo', recipe_id=row.recipe_id, insumos_baixados_em=datetime.now())
        db.session.add(other); db.session.commit()
        with pytest.raises(ValueError, match='histórico'): link(other)


def test_reconciliation_preview_pure_commit_conserves_quantity_and_replay(app):
    with app.app_context():
        _, material = lot()
        stock._registrar_movimentacao_legada(material.id, 'entrada', 5, custo_unitario=2)
        data = reconciliation(material)
        plan = stock.previa_reconciliacao_legado(data)
        assert OrganizationMovement.query.count() == 0 and Movimentacao.query.count() == 1
        result = stock.reconciliar_legado(data, plan['preview_token'], actor='admin')
        assert result['saldo']['valor_total_estoque'] == '7.21'
        assert stock.consultar_saldo(material.id)['quantidade_atual'] == 3
        assert result['movimentacao']['snapshot']['reconciliation']['legacy_movement_id']
        assert stock.reconciliar_legado(data, plan['preview_token'], actor='admin')['replayed']
        assert Movimentacao.query.count() == 2
        with pytest.raises(ValueError, match='outros dados'):
            stock.reconciliar_legado({**data, 'quantity': '1'}, plan['preview_token'], actor='admin')


def test_reconciliation_stale_preview_and_failed_entry_restore_legacy(app, monkeypatch):
    with app.app_context():
        _, material = lot(); stock._registrar_movimentacao_legada(material.id, 'entrada', 5, custo_unitario=2)
        data = reconciliation(material); plan = stock.previa_reconciliacao_legado(data)
        stock._registrar_movimentacao_legada(material.id, 'entrada', 1, custo_unitario=2)
        with pytest.raises(ValueError, match='desatualizada'):
            stock.reconciliar_legado(data, plan['preview_token'], actor='admin')
        plan = stock.previa_reconciliacao_legado(data)
        from addons.addon_estoque.root.services import legacy_reconciliation_service as service
        monkeypatch.setattr(service, '_record', lambda **kwargs: (_ for _ in ()).throw(ValueError('falha de entrada')))
        with pytest.raises(ValueError, match='falha de entrada'):
            stock.reconciliar_legado(data, plan['preview_token'], actor='admin')
        assert stock.consultar_saldo(material.id)['quantidade_atual'] == 6
        assert Movimentacao.query.count() == 2 and OrganizationMovement.query.count() == 0


def product():
    row = _criar_material(nome='Produto acabado', volume_real=1, unidade_medida_volume_real='L')
    row.unidade_medida = 'UN'; db.session.commit()
    return row


def test_envase_enters_finished_product_frozen_cost_and_reversal(app):
    with app.app_context():
        row, material = lot(); link(row); move(material, quantity='5', cost='2')
        finished = product(); key = str(uuid4())
        result = registrar_envase(row.id, finished.id, 4, idempotency_key=key)
        eid = result['envase']['id']
        balance = stock.consultar_saldo(finished.id, organization_code='A')
        assert Decimal(balance['quantidade_atual']) == 4 and Decimal(balance['valor_total_estoque']) == 4
        assert registrar_envase(row.id, finished.id, 4, idempotency_key=key)['ja_registrado']
        more = registrar_envase(row.id, finished.id, 6)
        assert Decimal(more['envase']['producao_snapshot']['custo_cerveja']) == 6
        assert Decimal(db.session.get(Envase, eid).producao_snapshot['custo_cerveja']) == 4
        with pytest.raises(ValueError, match='excede'): registrar_envase(row.id, finished.id, 1)
        estornar_envase(eid, 'Envase incorreto')
        assert Decimal(stock.consultar_saldo(finished.id, organization_code='A')['quantidade_atual']) == 6
        with pytest.raises(ValueError, match='cancelado'): estornar_envase(eid, 'Repetido')
        assert Decimal(stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual']) == 0


def test_routes_binding_reconciliation_and_permissions(app, client, monkeypatch):
    with app.app_context():
        row, material = lot(); sid = row.id
        stock._registrar_movimentacao_legada(material.id, 'entrada', 5, custo_unitario=2)
        data = reconciliation(material)
    url = '/estoque/saldos/reconciliar-legado'
    assert client.get(url).status_code in (302, 401)
    _login_admin(app, client)
    assert client.get(url).status_code == 200
    response = client.post(url, json={**data, 'action': 'preview'})
    assert response.status_code == 200
    token = response.json['preview']['preview_token']
    assert client.post(url, json={**data, 'action': 'confirm', 'preview_token': token}).status_code == 201
    assert client.post(f'/brewstation/brew-sessions/{sid}/organizacao', json={
        'organization_code': 'A', 'operation_date': DATE, 'policy_version_id': None}).status_code == 200
    from model.core.user import User
    old = User.has_permission
    monkeypatch.setattr(User, 'has_permission', lambda self, permission: False if permission == 'movimentacaos.create' else old(self, permission))
    assert client.get(url).status_code == 403


def test_public_stock_requires_organization_and_preview_token_is_required(app):
    with app.app_context():
        _, material = lot()
        with pytest.raises(ValueError, match='Organização obrigatória'):
            stock.registrar_movimentacao(material.id, 'entrada', 1, custo_unitario=1)
        stock._registrar_movimentacao_legada(material.id, 'entrada', 2, custo_unitario=1)
        with pytest.raises(ValueError):
            stock.reconciliar_legado(reconciliation(material), None, actor='admin')
        assert stock.consultar_saldo(material.id)['quantidade_atual'] == 2


def test_second_material_failure_rolls_back_first_and_batch(app):
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
    with app.app_context():
        row, material = lot(); other = _criar_material(nome='Lúpulo sem saldo')
        db.session.add(RecipeIngredient(recipe_id=row.recipe_id, descricao_origem='Lúpulo', material_id=other.id,
            quantidade=1, unidade_medida='kg', status_resolucao='resolvido')); db.session.commit()
        link(row); move(material, quantity='5', cost='2')
        with pytest.raises(ValueError, match='insuficiente'): consume(row.id, actor='admin')
        assert Decimal(stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual']) == 5
        assert ProductionConsumption.query.count() == 0 and OrganizationMovement.query.count() == 1


def test_envase_packaging_failure_does_not_consume_batch(app):
    from addons.addon_estoque.root.model.composicao import Composicao
    with app.app_context():
        row, material = lot(); link(row); move(material, quantity='5', cost='2')
        finished = product(); package = _criar_material(nome='Embalagem sem saldo')
        db.session.add(Composicao(material_pai_id=finished.id, material_componente_id=package.id, quantidade=1))
        db.session.commit()
        with pytest.raises(ValueError, match='insuficiente'): registrar_envase(row.id, finished.id, 4)
        assert Envase.query.count() == ProductionConsumption.query.count() == 0
        assert Decimal(stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual']) == 5


def test_price_uses_frozen_cost_and_volume_cannot_change(app):
    from addons.addon_brewstation.features.feature_envase.services.precificacao_service import simular
    with app.app_context():
        row, material = lot(); link(row); move(material, quantity='5', cost='2')
        finished = product(); result = registrar_envase(row.id, finished.id, 4)
        eid = result['envase']['id']
        priced = simular(row.id, eid, 10, 0, 0)
        assert Decimal(priced['base_calculo_snapshot']['exact_amounts']['subtotal']) == 4
        assert priced['currency_code'] == 'BRL' and priced['valor_total'] == 4.4
        registrar_envase(row.id, finished.id, 6)
        assert simular(row.id, eid, 10, 0, 0)['subtotal'] == priced['subtotal']
        row.volume_real_litros = 20
        with pytest.raises(ValueError, match='Volume real congelado'): db.session.commit()
        db.session.rollback()


def test_migration_upgrade_existing_and_downgrade_guard(app):
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module = importlib.import_module('migrations.versions.c59f7a23d861_production_organization')
    with app.app_context():
        with db.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
        row, _ = lot(); link(row)
        with db.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                with pytest.raises(RuntimeError, match='Downgrade bloqueado'): module.downgrade()


@pytest.mark.parametrize('operation', ['consume', 'reconcile', 'envase'])
def test_concurrent_confirmation_has_one_effect(app, tmp_path, operation):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier = threading.Barrier(2); results, errors = [], []
    with app.app_context():
        row, material = lot(); link(row); sid = row.id
        move(material, quantity='5', cost='2')
        if operation == 'reconcile':
            stock._registrar_movimentacao_legada(material.id, 'entrada', 2, custo_unitario=1)
            data = reconciliation(material); token = stock.previa_reconciliacao_legado(data)['preview_token']
        if operation == 'envase':
            finished = product(); fid = finished.id; key = str(uuid4())
        original, engine = _file_database(app, tmp_path)
    def worker():
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                if operation == 'consume': results.append(consume(sid, actor='admin')['ja_confirmado'])
                elif operation == 'reconcile': results.append(stock.reconciliar_legado(data, token, actor='admin')['replayed'])
                else: results.append(registrar_envase(sid, fid, 4, idempotency_key=key)['ja_registrado'])
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker) for _ in range(2)]
    try:
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors, errors
        assert sorted(results) == [False, True]
        with app.app_context():
            if operation == 'reconcile':
                assert Movimentacao.query.count() == 2
                assert Decimal(stock.consultar_saldo(material.id, organization_code='A')['quantidade_atual']) == 7
            else:
                assert ProductionConsumption.query.count() == 1
                assert Envase.query.count() == (1 if operation == 'envase' else 0)
    finally:
        with app.app_context():
            db.session.remove(); db.engines[None] = original; engine.dispose()


def test_actual_html_and_price_javascript(app, client, tmp_path):
    import re, subprocess
    _login_admin(app, client)
    with app.app_context():
        row, material = lot(); sid = row.id
        link(row); move(material, quantity='5', cost='2'); finished = product()
        result = registrar_envase(sid, finished.id, 4); eid = result['envase']['id']
    response = client.get(f'/brewstation/brew-sessions/{sid}')
    assert response.status_code == 200 and b'BRL' in response.data
    response = client.get(f'/brewstation/precificacao-envase/?lote_id={sid}&envase_id={eid}')
    assert response.status_code == 200
    for index, script in enumerate(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', response.get_data(as_text=True), re.S)):
        if not script.strip() or script.lstrip().startswith('{'): continue
        path = tmp_path / f'price-{index}.js'; path.write_text(script)
        subprocess.run(['node', '--check', str(path)], check=True, capture_output=True)


def test_legacy_history_is_readonly_and_binding_error_keeps_fields(app, client):
    _login_admin(app, client)
    with app.app_context():
        row, _ = lot(); sid = row.id
    response = client.get('/estoque/movimentacaos', follow_redirects=True)
    assert response.status_code == 200
    assert b'createForm' not in response.data and 'Histórico de movimentações legadas' in response.get_data(as_text=True)
    response = client.post(f'/brewstation/brew-sessions/{sid}/organizacao', data={
        'organization_code': 'A', 'operation_date': '2026-10-16', 'policy_version_id': '999999'})
    assert response.status_code == 422 and b'value="999999"' in response.data
    assert b'value="2026-10-16"' in response.data


def test_packaging_and_product_values_are_conserved_on_reversal(app):
    from addons.addon_estoque.root.model.composicao import Composicao
    with app.app_context():
        row, material = lot(); link(row); move(material, quantity='5', cost='2')
        package = _criar_material(nome='Embalagem com custo')
        move(package, quantity='2', cost='4', key='embalagem')
        finished = product()
        db.session.add(Composicao(material_pai_id=finished.id, material_componente_id=package.id, quantidade=0.25))
        db.session.commit()
        result = registrar_envase(row.id, finished.id, 4)
        snapshot = result['envase']['producao_snapshot']
        assert Decimal(snapshot['custo_embalagens']) == 4 and Decimal(snapshot['custo_produto']) == 8
        assert Decimal(stock.consultar_saldo(package.id, organization_code='A')['quantidade_atual']) == 1
        estornar_envase(result['envase']['id'], 'Conferência de embalagem')
        assert Decimal(stock.consultar_saldo(package.id, organization_code='A')['valor_total_estoque']) == 8
        assert Decimal(stock.consultar_saldo(finished.id, organization_code='A')['valor_total_estoque']) == 0


def test_reconciliation_foreign_currency_freezes_explicit_rate(app):
    from addons.addon_financeiro.root.services.exchange_service import create_rate
    with app.app_context():
        _, material = lot()
        stock._registrar_movimentacao_legada(material.id, 'entrada', 2, custo_unitario=1)
        rate = create_rate({'organization_code': 'A', 'source_currency': 'USD', 'target_currency': 'BRL',
            'rate': '5.25', 'valid_on': DATE, 'source': 'Avaliação documental', 'rate_type': 'MANUAL'}, actor='admin')
        assert rate.success
        data = {**reconciliation(material), 'source_currency': 'USD', 'source_amount': '2', 'rate_id': rate.data['id']}
        plan = stock.previa_reconciliacao_legado(data)
        result = stock.reconciliar_legado(data, plan['preview_token'], actor='admin')
        assert Decimal(result['saldo']['valor_total_estoque']) == Decimal('10.50')
        frozen = result['movimentacao']['snapshot']['conversion']
        assert frozen['rate']['id'] == rate.data['id'] and frozen['source_currency'] == 'USD'
