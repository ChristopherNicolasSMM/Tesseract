"""Regressão dos achados de integridade do YeastBank."""
import datetime
import pytest
from tests.test_viability_engine import app, client, _make_strain_and_item, _login_admin
from core.db import db
from addons.addon_brewstation.features.feature_yeast_bank.services.viability_engine import best_viability_reference_for_item, recalculate_all
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_container_service import YeastContainerService
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_cell_count_history_service_hooks import _calcular_neubauer
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_event_service import YeastBankEventService
from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_bank_events_hooks import post_create_redirect

def test_deleted_reference_is_not_used(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        db.session.add(YeastCellCountHistory(bank_item_id=item.id, viability_percent=99, is_deleted=True))
        db.session.commit()
        assert best_viability_reference_for_item(item)['type'] == 'strain_default'

def test_deleted_item_is_not_recalculated(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        item.is_deleted = True
        db.session.commit()
        recalculate_all()
        assert item.estimated_viability_pct is None

@pytest.mark.parametrize('status', ['planned', 'discarded'])
def test_unfinished_or_discarded_starter_is_not_reference(app, status):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        db.session.add(YeastBankEvent(bank_item_id=item.id, event_type='Starter', starter_status=status, result_viability_percent=99))
        db.session.commit()
        assert best_viability_reference_for_item(item)['type'] == 'strain_default'

def test_container_with_live_item_cannot_be_trashed(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        result = YeastContainerService().trash(item.container_id)
        assert not result.success

def test_negative_dead_count_does_not_produce_viability_above_100():
    obj = YeastCellCountHistory(cells_counted_live=120, cells_counted_dead=-20, squares_counted=5, dilution_factor=1)
    try:
        _calcular_neubauer(obj)
    except ValueError:
        return
    assert obj.viability_percent is None or 0 <= obj.viability_percent <= 100

def test_failed_count_creation_does_not_leave_committed_event(app, monkeypatch):
    from addons.addon_brewstation.features.feature_yeast_bank.services import yeast_integrity_service as integrity
    with app.app_context():
        _, item = _make_strain_and_item(app)
        original = integrity._create_event_effects
        def fail(event):
            original(event)
            raise RuntimeError('audit injected failure after count creation')
        monkeypatch.setattr(integrity, '_create_event_effects', fail)
        result = YeastBankEventService().create({'bank_item_id': item.id, 'event_type': 'Contagem de Células'})
        assert not result.success
        assert YeastBankEvent.query.count() == 0
        assert YeastCellCountHistory.query.count() == 0


def test_event_item_edit_keeps_count_consistent(app, client):
    _login_admin(app, client)
    with app.app_context():
        _, first = _make_strain_and_item(app)
        _, second = _make_strain_and_item(app)
        first_id, second_id = first.id, second.id
    created = client.post('/api/brewstation/yeast-bank-events/', json={'bank_item_id': first_id, 'event_type':'Contagem de Células'}).get_json()['item']
    response = client.put('/api/brewstation/yeast-bank-events/' + str(created['id']), json={'bank_item_id': second_id})
    if response.status_code >= 400:
        return
    with app.app_context():
        event = db.session.get(YeastBankEvent, created['id'])
        assert event.bank_item_id == event.cell_count.bank_item_id

def test_panel_requires_read_permission(app, client):
    from model.core.user import User
    with app.app_context():
        user = User(username='limited', email='limited@test.local', nome='Limited', nome_completo='Limited', celular='11999999999', is_admin=False, is_active=True)
        user.set_password('senha123')
        db.session.add(user)
        db.session.commit()
    client.post('/api/auth/login', json={'username':'limited', 'password':'senha123'})
    assert client.get('/brewstation/yeast-bank/painel').status_code == 403

def test_deleted_container_is_not_accepted_for_new_item(app, client):
    _login_admin(app, client)
    with app.app_context():
        strain, item = _make_strain_and_item(app)
        strain_id, container_id = strain.id, item.container_id
        item.container.is_deleted = True
        db.session.commit()
    response = client.post('/api/brewstation/yeast-bank-items/', json={'strain_id':strain_id, 'container_id':container_id, 'storage_type':'Lama'})
    assert response.status_code >= 400

def test_api_rejects_invalid_viability(app, client):
    _login_admin(app, client)
    with app.app_context():
        _, item = _make_strain_and_item(app)
        item_id = item.id
    response = client.post('/api/brewstation/yeast-cell-count-histories/', json={'bank_item_id':item_id, 'viability_percent':150})
    assert response.status_code >= 400


def _limited_login(app, client, permissions):
    from model.core.user import User
    from model.core.role import Role
    from model.core.permission import Permission
    with app.app_context():
        role = Role(name='yeast-limited')
        role.permissions = Permission.query.filter(Permission.name.in_(permissions)).all()
        assert len(role.permissions) == len(permissions)
        user = User(username='yeast-limited', email='yeast-limited@test.local', nome='Limited', nome_completo='Limited', celular='11999999999', is_admin=False, is_active=True)
        user.set_password('senha123')
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
    assert client.post('/api/auth/login', json={'username':'yeast-limited', 'password':'senha123'}).status_code == 200


def test_compound_count_creation_requires_permission_and_rolls_back(app, client):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        ident = item.id
    _limited_login(app, client, ['yeast_bank_events.create'])
    response = client.post('/api/brewstation/yeast-bank-events/', json={'bank_item_id':ident, 'event_type':'Contagem de Células'})
    assert response.status_code == 403
    with app.app_context():
        assert YeastBankEvent.query.count() == 0
        assert YeastCellCountHistory.query.count() == 0


def test_panel_only_renders_allowed_tabs_and_actions(app, client):
    _limited_login(app, client, ['yeast_bank_items.list', 'yeast_bank_events.list'])
    response = client.get('/brewstation/yeast-bank/painel')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="aba-eventos"' in html
    assert 'id="aba-cepas"' not in html
    assert 'Novo Evento do Banco' not in html
    assert 'href="/brewstation/yeast-storage-devices/"' not in html
    assert '"counts": false' in html


def test_hook_navigation_repetition_does_not_duplicate_count(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        result = YeastBankEventService().create({'bank_item_id':item.id, 'event_type':'Contagem de Células'})
        assert result.success
        event_id, count_id = result.data.id, result.data.cell_count_id
        with app.test_request_context():
            post_create_redirect(result.data)
            post_create_redirect(result.data)
        assert YeastBankEvent.query.count() == 1
        assert YeastCellCountHistory.query.count() == 1
        assert db.session.get(YeastBankEvent, event_id).cell_count_id == count_id


def test_discard_rollback_keeps_item_status_and_no_event(app, monkeypatch):
    from addons.addon_brewstation.features.feature_yeast_bank.services import yeast_integrity_service as integrity
    with app.app_context():
        _, item = _make_strain_and_item(app)
        ident = item.id
        original = integrity._create_event_effects
        def fail(event):
            original(event)
            db.session.flush()
            raise RuntimeError('injected failure after discard effect')
        monkeypatch.setattr(integrity, '_create_event_effects', fail)
        result = YeastBankEventService().create({'bank_item_id':ident, 'event_type':'Descarte'})
        assert not result.success
        assert db.session.get(type(item), ident).status == 'active'
        assert db.session.get(type(item), ident).discarded_at is None
        assert YeastBankEvent.query.count() == 0


def test_discard_history_changes_never_reactivate_item(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        service = YeastBankEventService()
        created = service.create({'bank_item_id':item.id,'event_type':'Descarte','notes':'Original'})
        assert created.success and item.status == 'discarded'
        event_id = created.data.id
        assert not service.update(event_id, {'status_after':'active'}).success
        assert service.update(event_id, {'notes':'Observação posterior'}).success
        assert item.discard_reason == 'Original'
        assert service.trash(event_id).success
        assert item.status == 'discarded'
        assert service.restore(event_id).success
        assert item.status == 'discarded'


def test_count_item_edit_blocked_by_origin_event(app):
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_cell_count_history_service import YeastCellCountHistoryService
    with app.app_context():
        _, item = _make_strain_and_item(app)
        event = YeastBankEventService().create({'bank_item_id':item.id,'event_type':'Contagem de Células'}).data
        count_id, item_id = event.cell_count_id, item.id
        _, other = _make_strain_and_item(app)
        result = YeastCellCountHistoryService().update(count_id, {'bank_item_id':other.id})
        assert not result.success
        assert db.session.get(YeastCellCountHistory,count_id).bank_item_id == item_id


def test_count_raw_edit_requires_explicit_results_revision(app):
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_cell_count_history_service import YeastCellCountHistoryService
    with app.app_context():
        _, item = _make_strain_and_item(app)
        service = YeastCellCountHistoryService()
        result = service.create({'bank_item_id':item.id,'cells_counted_live':80,'cells_counted_dead':20})
        assert result.success
        count_id = result.data.id
        assert not service.update(count_id, {'cells_counted_live':160,'cells_counted_dead':40}).success
        assert db.session.get(YeastCellCountHistory,count_id).cells_counted_live == 80
        result = service.update(count_id, {'cells_counted_live':160,'cells_counted_dead':40,'cells_per_ml':None,'viability_percent':None,'viable_cells_per_ml':None})
        assert result.success
        assert result.data.cells_per_ml == 10_000_000
        assert result.data.viability_percent == 80


def test_invalid_lab_numbers_rejected_without_saving(app, client):
    _login_admin(app, client)
    with app.app_context():
        _, item = _make_strain_and_item(app)
        ident = item.id
    for fields in [{'viability_percent':-1}, {'viability_percent':float('inf')}, {'estimated_viability_percent':float('nan')}, {'cells_counted_live':-1}, {'cells_counted_live':1.5}, {'squares_counted':0}, {'dilution_factor':0}, {'cells_per_ml':-1}]:
        response = client.post('/api/brewstation/yeast-cell-count-histories/', json={'bank_item_id':ident, **fields})
        assert response.status_code == 422, fields
    with app.app_context():
        assert YeastCellCountHistory.query.count() == 0


def test_config_restore_conflict_rolls_back_and_session_remains_usable(app):
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_config_service import YeastBankConfigService
    with app.app_context():
        service = YeastBankConfigService()
        first = service.create({'storage_type':'Lama','expiry_days':1})
        ident = first.data.id
        assert first.success and service.trash(ident).success
        assert service.create({'storage_type':'Lama','expiry_days':2}).success
        assert not service.restore(ident).success
        assert db.session.get(type(first.data), ident).is_deleted
        assert service.create({'storage_type':'Seca','expiry_days':3}).success


def test_hierarchy_restore_parent_order_and_permanent_history_guard(app):
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_item_service import YeastBankItemService
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_storage_device_service import YeastStorageDeviceService
    with app.app_context():
        _, item = _make_strain_and_item(app)
        item_id, container_id, device_id = item.id, item.container_id, item.container.device_id
        assert YeastBankItemService().trash(item_id).success
        assert YeastContainerService().trash(container_id).success
        assert YeastStorageDeviceService().trash(device_id).success
        assert not YeastBankItemService().restore(item_id).success
        assert not YeastContainerService().restore(container_id).success
        assert not YeastContainerService().delete_permanent(container_id).success
        assert YeastStorageDeviceService().restore(device_id).success
        assert YeastContainerService().restore(container_id).success
        assert YeastBankItemService().restore(item_id).success


def test_deleted_origin_event_and_deleted_starter_not_used(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        event = YeastBankEventService().create({'bank_item_id':item.id,'event_type':'Contagem de Células'}).data
        event.cell_count.viability_percent = 99
        event.is_deleted = True
        db.session.add(YeastBankEvent(bank_item_id=item.id, event_type='Starter', starter_status='completed', result_viability_percent=98, is_deleted=True))
        db.session.commit()
        assert best_viability_reference_for_item(item)['type'] == 'strain_default'
        event.is_deleted = False
        db.session.commit()
        assert best_viability_reference_for_item(item)['type'] == 'count_history_real'


def test_new_starter_needs_explicit_completion_and_legacy_is_preserved(app):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        service = YeastBankEventService()
        result = service.create({'bank_item_id':item.id,'event_type':'Starter','result_viability_percent':99})
        assert result.success and result.data.starter_status == 'planned'
        assert best_viability_reference_for_item(item)['type'] == 'strain_default'
        assert service.update(result.data.id, {'starter_status':'completed'}).success
        assert best_viability_reference_for_item(item)['type'] == 'starter'
        result.data.starter_status = None  # referência legada já persistida
        db.session.commit()
        assert best_viability_reference_for_item(item)['type'] == 'starter'


def test_identity_uses_new_reference_ids_on_edit(app):
    from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_item_service import YeastBankItemService
    with app.app_context():
        first_strain, first = _make_strain_and_item(app)
        second_strain, second = _make_strain_and_item(app)
        second_strain.name = 'Outra cepa'
        second.container.name = 'Outra caixa'
        db.session.commit()
        _ = first.strain.name, first.container.name  # força relationships antigas em cache
        result = YeastBankItemService().update(first.id, {'strain_id':second_strain.id,'container_id':second.container_id})
        assert result.success
        assert result.data.identification == 'Outra cepa - Outra caixa'


def test_viability_batch_failure_rolls_back_all_updates(app, monkeypatch):
    from addons.addon_brewstation.features.feature_yeast_bank.services import viability_engine
    with app.app_context():
        _, first = _make_strain_and_item(app)
        _, second = _make_strain_and_item(app)
        first_id, second_id = first.id, second.id
        original = viability_engine.best_viability_reference_for_item
        def fail(item):
            if item.id == second_id:
                raise RuntimeError('injected recalculation error')
            return original(item)
        monkeypatch.setattr(viability_engine, 'best_viability_reference_for_item', fail)
        with pytest.raises(RuntimeError):
            viability_engine.recalculate_all()
        assert db.session.get(type(first), first_id).estimated_viability_pct is None
        assert db.session.get(type(second), second_id).estimated_viability_pct is None


def test_recalculate_route_returns_friendly_error_after_failure(app, client, monkeypatch):
    from addons.addon_brewstation.features.feature_yeast_bank.controller import yeast_bank_viability
    _login_admin(app, client)
    def fail():
        raise RuntimeError('injected recalculation failure')
    monkeypatch.setattr(yeast_bank_viability, 'recalculate_all', fail)
    response = client.post('/brewstation/yeast-bank-tools/recalculate-viability')
    assert response.status_code == 422
    assert response.get_json()['success'] is False
    assert 'injected' not in response.get_json()['error']


def test_count_create_permission_without_detail_does_not_redirect_to_forbidden_page(app, client):
    with app.app_context():
        _, item = _make_strain_and_item(app)
        item_id = item.id
    _limited_login(app, client, ['yeast_bank_events.create','yeast_cell_count_histories.create'])
    response = client.post('/api/brewstation/yeast-bank-events/', json={'bank_item_id':item_id,'event_type':'Contagem de Células'})
    assert response.status_code == 201
    assert response.get_json()['item']['cell_count_id'] is not None
