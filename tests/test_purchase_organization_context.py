"""Contexto preparatório: nenhum recebimento/atribuição implícita ao saldo global."""
import importlib
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_addon_estoque import (app, client, _login_admin, _criar_processo_cotacao, _criar_cotacao, _criar_material)
from tests.test_purchase_integrity import purchase
from core.db import db
from services.core.organization_service import save_organization
from addons.addon_estoque.root.model.purchase_context import PurchaseContext
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.services.purchase_context_service import bind_context, get_context
from addons.addon_estoque.root.services.cotacao_service import CotacaoService
from addons.addon_estoque.root.services import estoque_service


def organizations():
    assert save_organization({'code':'A', 'name':'Organização A'}).success
    assert save_organization({'code':'B', 'name':'Organização B'}).success


def bind(kind, ident, code='A'):
    return bind_context(kind, ident, {'organization_code':code}, actor='admin')


def test_explicit_binding_idempotency_and_immutable_snapshot(app):
    with app.app_context():
        organizations()
        pedido, _, _ = purchase()
        assert get_context('order', pedido.id) is None
        first = bind('order', pedido.id)
        assert first.code == 201, first.error
        assert bind('order', pedido.id, ' a ').data == first.data
        assert bind('order', pedido.id, 'B').code == 409
        assert PurchaseContext.query.count() == 1
        row = PurchaseContext.query.one()
        row.organization_code = 'B'
        with pytest.raises(ValueError, match='imutável'): db.session.commit()
        db.session.rollback()
        db.session.delete(row)
        with pytest.raises(ValueError, match='imutável'): db.session.commit()
        db.session.rollback()
        org = save_organization({'code':'C','name':'C'}).data
        assert save_organization({'is_active':False}, org['id']).success
        assert bind('order', pedido.id, 'C').code == 409
        assert get_context('order', pedido.id).organization_name == 'Organização A'


@pytest.mark.parametrize('data', [None, [], {}, {'organization_code':True}, {'organization_code':'MISSING'}, {'organization_code':'A','currency_code':'BRL'}])
def test_invalid_binding_has_no_write(app, data):
    with app.app_context():
        organizations(); pedido, _, _ = purchase()
        result = bind_context('order', pedido.id, data, actor='admin')
        assert result.code == 422
        assert PurchaseContext.query.count() == 0
        assert Movimentacao.query.count() == Saldo.query.count() == 0


def test_inactive_missing_non_draft_and_invalid_document_are_rejected(app):
    with app.app_context():
        org = save_organization({'code':'A','name':'A','is_active':False}).data
        pedido, _, _ = purchase()
        assert bind('order', pedido.id).code == 422
        assert save_organization({'is_active':True},org['id']).success
        pedido.status='confirmado';db.session.commit()
        assert bind('order',pedido.id).code == 422
        for kind, ident in [('order',True), ('order',0), ('unknown',1), ('order',99999)]:
            assert bind(kind,ident).code == 422
        assert PurchaseContext.query.count() == 0


def test_scoped_receipt_is_blocked_atomically_and_legacy_receipt_works(app):
    with app.app_context():
        organizations(); pedido, _, _ = purchase()
        assert bind('order',pedido.id).success
        pedido.status='confirmado';db.session.commit()
        with pytest.raises(ValueError,match='saldos e custos por organização'):
            estoque_service.receber_pedido_compra(pedido.id)
        assert db.session.get(PedidoCompra,pedido.id).status == 'confirmado'
        assert Movimentacao.query.count() == Saldo.query.count() == 0
        legacy, _, _ = purchase('confirmado', material=_criar_material(nome='Material legado',sku='LEGADO-02'))
        estoque_service.receber_pedido_compra(legacy.id)
        assert Movimentacao.query.count() == Saldo.query.count() == 1
        assert get_context('order',legacy.id) is None


def test_scoped_process_without_winners_and_quotation_reparenting(app):
    with app.app_context():
        organizations(); process=_criar_processo_cotacao()
        other=_criar_processo_cotacao()
        assert bind('process',process.id).success
        quotation=_criar_cotacao(process)
        with pytest.raises(ValueError,match='Nenhum item vencedor'):
            estoque_service.gerar_pedidos_de_cotacao(process.id,actor='admin')
        assert PedidoCompra.query.count() == 0
        result = CotacaoService().update(quotation.id, {'processo_cotacao_id':other.id})
        assert not result.success
        db.session.refresh(quotation)
        assert quotation.processo_cotacao_id == process.id
        assert process.status == 'aberto'


def test_bound_documents_cannot_be_destroyed(app):
    with app.app_context():
        organizations(); process=_criar_processo_cotacao()
        assert bind('process',process.id).success
        db.session.delete(process)
        with pytest.raises(ValueError,match='excluído permanentemente'): db.session.commit()
        db.session.rollback()
        assert get_context('process',process.id) is not None


def test_web_form_json_roundtrip_and_permission(app,client):
    _login_admin(app,client)
    with app.app_context():
        organizations(); pedido, _, _ = purchase(); ident=pedido.id
    path=f'/estoque/pedido-compras/{ident}/contexto-organizacional'
    page=client.get(path)
    assert page.status_code == 200
    assert 'Selecione explicitamente' in page.get_data(as_text=True)
    result=client.post(path,json={'organization_code':'A'})
    assert result.status_code == 201 and result.json['success']
    assert client.get(path,json={}).json['data'] == result.json['data']
    assert 'Registrar vínculo definitivo' not in client.get(path).get_data(as_text=True)
    assert client.post(path,json={'organization_code':'B'}).status_code == 409
    client.post('/api/auth/logout')
    assert client.post(path,json={'organization_code':'B'}).status_code in (302,401)


def test_commit_failure_rolls_back_binding(app,monkeypatch):
    with app.app_context():
        organizations(); pedido, _, _ = purchase()
        def fail(): raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            assert bind('order',pedido.id).code == 409
        assert PurchaseContext.query.count() == 0
        assert bind('order',pedido.id).success


migration=importlib.import_module('migrations.versions.f26b3c87e451_purchase_organization_context')


def test_migration_repeat_preserves_legacy_and_protects_nonempty_downgrade(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        for table in ('pedido_compra','processo_cotacao'):
            conn.exec_driver_sql(f'CREATE TABLE tesseract_estoque_{table}(id INTEGER PRIMARY KEY)')
            conn.exec_driver_sql(f'INSERT INTO tesseract_estoque_{table} VALUES(1)')
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        migration.upgrade(); migration.upgrade()
        assert conn.exec_driver_sql(f'SELECT COUNT(*) FROM {migration.NAME}').scalar() == 0
        migration.downgrade();migration.downgrade();migration.upgrade()
        conn.exec_driver_sql(f"INSERT INTO {migration.NAME}(order_id,organization_code,organization_name,created_by,created_at) VALUES(1,'A','A','admin','2026-10-08')")
        migration.upgrade()
        with pytest.raises(RuntimeError,match='preservados'): migration.downgrade()
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM tesseract_estoque_pedido_compra').scalar() == 1


def test_migration_rejects_incompatible_existing_table(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE TABLE {migration.NAME}(id INTEGER PRIMARY KEY)')
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        with pytest.raises(RuntimeError,match='incompatível'): migration.upgrade()


def test_process_with_existing_quotes_remains_legacy(app):
    with app.app_context():
        organizations(); process=_criar_processo_cotacao(); _criar_cotacao(process)
        assert bind('process',process.id).code == 422
        assert get_context('process',process.id) is None


@pytest.mark.parametrize('kind', ['order','process'])
def test_concurrent_bindings_have_one_immutable_winner(app,tmp_path,kind):
    import threading
    from tests.test_purchase_integrity import _file_database
    results, errors = [], []
    barrier=threading.Barrier(2)
    with app.app_context():
        organizations()
        obj = purchase()[0] if kind == 'order' else _criar_processo_cotacao()
        ident=obj.id
        original, engine=_file_database(app,tmp_path)
    def worker(code):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                results.append(bind(kind,ident,code))
        except Exception as exc:
            errors.append(exc)
    threads=[threading.Thread(target=worker,args=(code,)) for code in ('A','B')]
    try:
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors, errors
        assert sorted(result.code for result in results) == [201,409]
        with app.app_context():
            assert PurchaseContext.query.count() == 1
            winner = next(result.data for result in results if result.success)
            assert get_context(kind,ident).to_dict() == winner
    finally:
        for thread in threads: thread.join(timeout=15)
        with app.app_context():
            db.session.remove(); db.engines[None]=original
        engine.dispose()
