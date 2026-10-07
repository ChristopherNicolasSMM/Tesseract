"""Compras: histórico protegido e concorrência em conexões independentes."""
import pytest
from tests.test_addon_estoque import (
    app, client, _login_admin, _criar_material, _criar_unidade,
    _criar_pedido_compra, _criar_item_pedido_compra,
)
from core.db import db
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService
from addons.addon_estoque.root.services import estoque_service


def purchase(status='rascunho', material=None):
    material = material or _criar_material(nome='Material compra protegida')
    unidade = _criar_unidade(material, 'PCT', 25)
    pedido = _criar_pedido_compra()
    item = _criar_item_pedido_compra(pedido, material, unidade, quantidade=2, preco_unitario=100)
    # Fixture de estado persistido: testar proteção sem depender da transição UI.
    pedido.status = status
    db.session.commit()
    return pedido, item, unidade


def test_confirmed_item_cannot_change_quantity(app):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        result = ItemPedidoCompraService().update(item.id, {'quantidade': 9})
        assert not result.success
        db.session.refresh(item)
        assert item.quantidade == 2
        assert item.quantidade_convertida_base == 50


def test_saving_same_draft_item_preserves_snapshot(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        unidade.fator_para_base = 30
        db.session.commit()
        result = ItemPedidoCompraService().update(item.id, {'quantidade': 2, 'preco_unitario': 100})
        assert result.success, result.error
        assert item.fator_conversao_aplicado == 25
        assert item.quantidade_convertida_base == 50


def test_received_status_cannot_be_assigned_without_receipt(app):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        result = PedidoCompraService().update(pedido.id, {'status': 'recebido'})
        assert not result.success
        db.session.refresh(pedido)
        assert pedido.status == 'confirmado'
        assert Movimentacao.query.count() == 0


def test_received_item_cannot_be_trashed(app):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        estoque_service.receber_pedido_compra(pedido.id)
        result = ItemPedidoCompraService().trash(item.id)
        assert not result.success
        assert not db.session.get(ItemPedidoCompra, item.id).is_deleted


@pytest.mark.parametrize('status', ['enviado', 'confirmado', 'recebido', 'cancelado'])
def test_frozen_order_items_reject_creation_update_and_reparent(app, status):
    with app.app_context():
        pedido, item, unidade = purchase(status)
        svc = ItemPedidoCompraService()
        data = {f: getattr(item, f) for f in ('pedido_compra_id', 'material_id', 'material_unidade_id', 'quantidade', 'preco_unitario')}
        assert not svc.create(data).success
        assert not svc.update(item.id, {'preco_unitario': 500}).success
        other = _criar_pedido_compra()
        assert not svc.update(item.id, {'pedido_compra_id': other.id}).success
        assert ItemPedidoCompra.query.count() == 1


@pytest.mark.parametrize('action', ['trash', 'restore', 'delete_permanent'])
def test_received_order_and_items_protect_maintenance(app, action):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        estoque_service.receber_pedido_compra(pedido.id)
        # Arquivamentos legados também não podem destruir o histórico.
        if action != 'trash':
            pedido.is_deleted = item.is_deleted = True
            db.session.commit()
        assert not getattr(PedidoCompraService(), action)(pedido.id).success
        assert not getattr(ItemPedidoCompraService(), action)(item.id).success
        assert PedidoCompra.query.count() == ItemPedidoCompra.query.count() == 1
        assert Movimentacao.query.count() == 1


@pytest.mark.parametrize('field', ['fornecedor_id', 'numero', 'valor_frete', 'data_pedido', 'status'])
def test_received_order_cannot_rewrite_receipt_context(app, field):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        estoque_service.receber_pedido_compra(pedido.id)
        values = {'fornecedor_id': 99999, 'numero': 'ALTERADO', 'valor_frete': 99,
                  'data_pedido': '2027-01-01', 'status': 'confirmado'}
        result = PedidoCompraService().update(pedido.id, {field: values[field]})
        assert not result.success
        assert db.session.get(PedidoCompra, pedido.id).status == 'recebido'
        assert Movimentacao.query.count() == 1


def test_observations_allowed_after_receipt_and_item_snapshot_unchanged(app):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        estoque_service.receber_pedido_compra(pedido.id)
        unidade.fator_para_base = 40
        db.session.commit()
        assert PedidoCompraService().update(pedido.id, {'observacoes': 'Conferência documental'}).success
        assert item.fator_conversao_aplicado == 25
        assert estoque_service.consultar_saldo(item.material_id)['custo_medio'] == 4


def test_draft_quantity_price_changes_keep_factor_and_unit_change_is_explicit(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        unidade.fator_para_base = 40
        db.session.commit()
        svc = ItemPedidoCompraService()
        assert svc.update(item.id, {'quantidade': 3, 'preco_unitario': 150}).success
        assert item.fator_conversao_aplicado == 25
        assert item.quantidade_convertida_base == 75
        assert item.subtotal == 450
        new_unit = _criar_unidade(item.material, 'UN', 1)
        assert svc.update(item.id, {'material_unidade_id': new_unit.id}).success
        assert item.fator_conversao_aplicado == 1
        assert item.quantidade_convertida_base == 3


@pytest.mark.parametrize('payload', [{'quantidade': 0}, {'quantidade': -1}, {'quantidade': 'nan'},
                                   {'preco_unitario': 'inf'}, {'preco_unitario': -1},
                                   {'quantidade': True}, {'material_id': True},
                                   {'quantidade': 1e308, 'preco_unitario': 1e308}])
def test_invalid_item_update_rolls_back_snapshot(app, payload):
    with app.app_context():
        pedido, item, unidade = purchase()
        result = ItemPedidoCompraService().update(item.id, payload)
        assert not result.success
        db.session.refresh(item)
        assert (item.quantidade, item.preco_unitario, item.fator_conversao_aplicado,
                item.quantidade_convertida_base, item.subtotal) == (2, 100, 25, 50, 200)


def test_draft_rejects_unit_from_other_material_and_relationship_payload(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        other = _criar_material(nome='Outro material compra')
        other_unit = _criar_unidade(other, 'UN', 1)
        assert not ItemPedidoCompraService().update(item.id, {'material_unidade_id': other_unit.id}).success
        assert ItemPedidoCompraService().update(item.id, {'pedido_compra': {'status': 'recebido'}}).success
        assert pedido.status == 'rascunho'


def test_readonly_snapshots_and_parent_filter_remain_authoritative(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        svc = ItemPedidoCompraService()
        assert svc.update(item.id, {'fator_conversao_aplicado': 500,
            'quantidade_convertida_base': 999, 'subtotal': 999}).success
        assert (item.fator_conversao_aplicado, item.quantidade_convertida_base, item.subtotal) == (25, 50, 200)
        other = _criar_pedido_compra()
        _criar_item_pedido_compra(other, item.material, unidade)
        assert [i.id for i in svc.list(pedido_compra_id=pedido.id)] == [item.id]
        assert len(svc.list(pedido_compra_id=None)) == 2
        with pytest.raises(ValueError, match='Filtro'):
            svc.list(quantidade=2)


def test_new_order_cannot_skip_draft(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        data = {'fornecedor_id': pedido.fornecedor_id, 'data_pedido': '2026-10-07', 'status': 'recebido'}
        result = PedidoCompraService().create(data)
        assert not result.success
        assert PedidoCompra.query.count() == 1


def test_draft_trash_restore_and_reference_guard(app):
    with app.app_context():
        pedido, item, unidade = purchase()
        psvc, isvc = PedidoCompraService(), ItemPedidoCompraService()
        assert not psvc.trash(pedido.id).success
        assert isvc.trash(item.id).success
        assert psvc.trash(pedido.id).success
        assert not isvc.restore(item.id).success
        assert psvc.restore(pedido.id).success
        assert not psvc.delete_permanent(pedido.id).success
        assert isvc.restore(item.id).success
        assert item.fator_conversao_aplicado == 25


def test_historical_receipt_blocks_duplicate_even_if_legacy_status_is_wrong(app):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        estoque_service.receber_pedido_compra(pedido.id)
        pid, iid = pedido.id, item.id
        pedido.status = 'confirmado'
        db.session.commit()
        with pytest.raises(estoque_service.PedidoCompraStatusInvalidoError):
            estoque_service.receber_pedido_compra(pid)
        pedido.status = 'rascunho'
        db.session.commit()
        assert not ItemPedidoCompraService().update(iid, {'quantidade': 10}).success
        assert not PedidoCompraService().trash(pid).success
        assert Movimentacao.query.count() == 1
        assert estoque_service.consultar_saldo(item.material_id)['quantidade_atual'] == 50


def test_failed_final_receipt_commit_rolls_back_all_entries_and_status(app, monkeypatch):
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        pid, material_id = pedido.id, item.material_id
        def fail():
            raise RuntimeError('falha injetada no commit final')
        with monkeypatch.context() as patch:
            patch.setattr(db.session, 'commit', fail)
            with pytest.raises(RuntimeError, match='commit final'):
                estoque_service.receber_pedido_compra(pid)
        assert db.session.get(PedidoCompra, pid).status == 'confirmado'
        assert Movimentacao.query.count() == 0
        assert estoque_service.consultar_saldo(material_id) is None


def test_overflow_in_accumulated_cost_rolls_back_central_movement(app):
    with app.app_context():
        material = _criar_material(nome='Saldo custo acumulado finito')
        estoque_service.registrar_movimentacao(material.id, 'entrada', 1, custo_unitario=1e308)
        with pytest.raises(ValueError, match='finito'):
            estoque_service.registrar_movimentacao(material.id, 'entrada', 1, custo_unitario=1e308)
        assert Movimentacao.query.count() == 1
        saldo = estoque_service.consultar_saldo(material.id)
        assert saldo['quantidade_atual'] == 1
        assert saldo['custo_medio'] == 1e308


def test_api_and_form_reject_direct_receipt_and_item_edit(app, client):
    _login_admin(app, client)
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        pid, iid = pedido.id, item.id
    resp = client.put(f'/api/estoque/pedido-compras/{pid}', json={'status': 'recebido'})
    assert resp.status_code == 409
    resp = client.put(f'/api/estoque/item-pedido-compras/{iid}', json={'quantidade': 9})
    assert resp.status_code == 409
    resp = client.post(f'/estoque/pedido-compras/{pid}', data={'status': 'recebido'}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(PedidoCompra, pid).status == 'confirmado'
        assert db.session.get(ItemPedidoCompra, iid).quantidade == 2
        assert Movimentacao.query.count() == 0


def _file_database(app, tmp_path):
    """Clona somente SQLite sintético da fixture, nunca um banco do usuário."""
    import sqlite3
    from sqlalchemy import create_engine
    db.session.remove()
    original = db.engines[None]
    path = tmp_path / 'compras-concorrencia.db'
    raw = original.raw_connection()
    destination = sqlite3.connect(path)
    try:
        raw.driver_connection.backup(destination)
    finally:
        destination.close()
        raw.close()
    engine = create_engine('sqlite:///' + path.as_posix(), connect_args={'timeout': 10})
    db.engines[None] = engine
    return original, engine


@pytest.mark.parametrize('same_order', [True, False])
@pytest.mark.parametrize('existing_balance', [True, False])
def test_concurrent_receipts_serialise_orders_and_material_balance(app, tmp_path, same_order, existing_balance):
    import threading
    barrier = threading.Barrier(2)
    results, errors = [], []
    with app.app_context():
        pedido, item, unidade = purchase('confirmado')
        material_id = item.material_id
        if existing_balance:
            estoque_service.registrar_movimentacao(material_id, 'entrada', 10, custo_unitario=2)
        pids = [pedido.id, pedido.id]
        if not same_order:
            second = _criar_pedido_compra()
            _criar_item_pedido_compra(second, item.material, unidade, quantidade=1, preco_unitario=200)
            second.status = 'confirmado'
            db.session.commit()
            pids[1] = second.id
        initial_count = Movimentacao.query.count()
        original, engine = _file_database(app, tmp_path)
    def worker(pid):
        try:
            with app.app_context():
                # Identity map e coleção deliberadamente aquecidos antes da corrida.
                obj = db.session.get(PedidoCompra, pid)
                assert obj.status == 'confirmado'
                list(obj.itens)
                Saldo.query.filter_by(material_id=material_id).first()
                barrier.wait(timeout=10)
                results.append(estoque_service.receber_pedido_compra(pid))
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(pid,)) for pid in pids]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(t.is_alive() for t in threads)
        if same_order:
            assert len(results) == 1
            assert len(errors) == 1 and isinstance(errors[0], estoque_service.PedidoCompraStatusInvalidoError)
        else:
            assert not errors, errors
            assert len(results) == 2
        with app.app_context():
            expected_qty = (10 if existing_balance else 0) + (50 if same_order else 75)
            expected_value = (20 if existing_balance else 0) + (200 if same_order else 400)
            saldo = estoque_service.consultar_saldo(material_id)
            assert saldo['quantidade_atual'] == expected_qty
            assert saldo['custo_medio'] == pytest.approx(expected_value / expected_qty)
            assert Saldo.query.filter_by(material_id=material_id).count() == 1
            assert Movimentacao.query.count() == initial_count + (1 if same_order else 2)
    finally:
        for thread in threads:
            thread.join(timeout=15)
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
        engine.dispose()


def test_concurrent_confirmation_and_item_edit_use_same_parent_reservation(app, tmp_path):
    import threading
    barrier = threading.Barrier(2)
    results, errors = {}, []
    with app.app_context():
        pedido, item, unidade = purchase()
        pid, iid = pedido.id, item.id
        original, engine = _file_database(app, tmp_path)
    def worker(action):
        try:
            with app.app_context():
                db.session.get(PedidoCompra, pid)
                db.session.get(ItemPedidoCompra, iid)
                barrier.wait(timeout=10)
                if action == 'confirm':
                    results[action] = PedidoCompraService().update(pid, {'status': 'confirmado'})
                else:
                    results[action] = ItemPedidoCompraService().update(iid, {'quantidade': 3})
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(action,)) for action in ('confirm', 'edit')]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not errors, errors
        assert not any(t.is_alive() for t in threads)
        assert results['confirm'].success
        with app.app_context():
            pedido = db.session.get(PedidoCompra, pid)
            item = db.session.get(ItemPedidoCompra, iid)
            expected = 3 if results['edit'].success else 2
            assert pedido.status == 'confirmado'
            assert item.quantidade == expected
            assert item.quantidade_convertida_base == expected * 25
            estoque_service.receber_pedido_compra(pid)
            assert estoque_service.consultar_saldo(item.material_id)['quantidade_atual'] == expected * 25
    finally:
        for thread in threads:
            thread.join(timeout=15)
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
        engine.dispose()
