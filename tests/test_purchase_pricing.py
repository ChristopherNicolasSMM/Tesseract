"""Preços exatos desde a confirmação monetária e transporte até o saldo."""
import importlib
import json
from decimal import Decimal
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_addon_estoque import (app, client, _login_admin, _criar_material, _criar_unidade,
    _criar_processo_cotacao, _criar_cotacao, _criar_item_processo_cotacao, _criar_item_cotacao,
    _criar_fornecedor)
from tests.test_purchase_integrity import purchase
from tests.test_organization_stock import finance, PLAN
from core.db import db
from addons.addon_estoque.root.model.purchase_pricing import PurchasePricing
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
from addons.addon_estoque.root.model.organization_stock import OrganizationBalance, OrderValuation
from addons.addon_estoque.root.services.purchase_context_service import bind_context
from addons.addon_estoque.root.services.purchase_pricing_service import freeze, get_pricing, comparison
from addons.addon_estoque.root.services.order_valuation_service import prepare_valuation
from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService
from addons.addon_estoque.root.services.item_cotacao_service import ItemCotacaoService
from addons.addon_financeiro.root.services.monetary_service import create_currency
from addons.addon_estoque.root.services import estoque_service as stock


def pricing(item, currency='BRL', quantity='2', price='0.123456789012', freight='0'):
    return {'currency_code': currency, 'freight': freight,
            'items': [{'id': item.id, 'quantity': quantity, 'unit_price': price}]}


def order():
    finance()
    pedido, item, unit = purchase()
    assert bind_context('order', pedido.id, {'organization_code': 'A'}, actor='admin').success
    return pedido, item, unit


def quotation():
    finance()
    process = _criar_processo_cotacao()
    assert bind_context('process', process.id, {'organization_code': 'A'}, actor='admin').success
    material = _criar_material()
    unit = _criar_unidade(material, 'PCT', 25)
    requested = _criar_item_processo_cotacao(process, material, unit)
    quote = _criar_cotacao(process)
    item = _criar_item_cotacao(quote, requested)
    return process, quote, item, requested, unit


def test_large_exact_quantity_price_freight_survive_reload_and_receipt(app):
    with app.app_context():
        pedido, item, unit = order()
        quantity = '12345678901234567.123456789012'
        # fator 25 excederia os limites de precisão da quantidade-base; use a unidade-base explicitamente
        base = _criar_unidade(item.material, 'UN', 1)
        assert ItemPedidoCompraService().update(item.id, {'material_unidade_id': base.id}).success
        data = pricing(item, quantity=quantity, price='0', freight='12345678901234567.123456789012')
        result = freeze('order', pedido.id, data, actor='admin')
        assert result.success, result.error
        ident, material_id = pedido.id, item.material_id
        db.session.remove()
        exact = get_pricing('order', ident).to_dict()['snapshot']
        assert exact['items'][0]['quantity'] == exact['freight'] == quantity
        assert PedidoCompraService().update(ident, {'status': 'confirmado'}).success
        plan = prepare_valuation(ident, PLAN, actor='admin')
        assert plan.success, plan.error
        assert plan.data['snapshot']['freight_original'] == quantity
        stock.receber_pedido_compra(ident, actor='admin')
        assert stock.consultar_saldo(material_id, organization_code='A')['quantidade_atual'] == quantity
        assert OrganizationBalance.query.one().stock_value == 0


def test_quote_exact_price_and_frozen_factor_are_inherited_atomically(app):
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        data = pricing(item)
        assert freeze('quotation', quote.id, data, actor='admin').success
        unit.fator_para_base = 40
        unit.unidade = 'CX'
        db.session.commit()
        stock.selecionar_item_cotacao_vencedor(item.id)
        result = stock.gerar_pedidos_de_cotacao(process.id, actor='admin')
        ident = result['pedidos_gerados'][0]['id']
        exact = get_pricing('order', ident).to_dict()['snapshot']['items'][0]
        assert exact['unit_price'] == '0.123456789012'
        assert exact['factor'] == '25' and exact['quantity_base'] == '50'
        assert exact['unit'] == 'PCT'
        assert exact['subtotal'] == '0.246913578024'
        assert PedidoCompraService().update(ident, {'status': 'confirmado'}).success
        plan = prepare_valuation(ident, PLAN, actor='admin')
        assert plan.success, plan.error
        assert plan.data['snapshot']['items'][0]['conversion']['original_amount'] == '0.246913578024'
        stock.receber_pedido_compra(ident, actor='admin')
        assert OrganizationBalance.query.one().quantity == 50
        assert OrganizationBalance.query.one().stock_value == Decimal('0.25')
        assert len(result['pedidos_gerados']) == 1
        with pytest.raises(ValueError, match='Nenhum item'): stock.gerar_pedidos_de_cotacao(process.id, actor='admin')


@pytest.mark.parametrize('field,value', [('quantity', True), ('quantity', 1.2), ('quantity', 'NaN'),
    ('quantity', '0'), ('quantity', '-1'), ('quantity', '1e2'), ('unit_price', 1.2),
    ('unit_price', '-1'), ('unit_price', 'Infinity'), ('unit_price', '1,23')])
def test_invalid_values_roll_back_without_pricing_or_compatibility_edits(app, field, value):
    with app.app_context():
        pedido, item, unit = order()
        data = pricing(item)
        data['items'][0][field] = value
        result = freeze('order', pedido.id, data, actor='admin')
        assert not result.success
        assert PurchasePricing.query.count() == 0
        db.session.refresh(item)
        assert item.preco_unitario == 100 and item.quantidade == 2


def test_idempotency_immutability_currency_mismatch_and_no_retroactive_valuation(app):
    with app.app_context():
        pedido, item, unit = order()
        first = freeze('order', pedido.id, pricing(item), actor='admin')
        assert first.success, first.error
        repeat = pricing(item, price='0.123456789012', quantity='2.000')
        assert freeze('order', pedido.id, repeat, actor='admin').data == first.data
        assert freeze('order', pedido.id, pricing(item, price='9'), actor='admin').code == 409
        row = PurchasePricing.query.one()
        row.currency_code = 'USD'
        with pytest.raises(ValueError, match='imutável'): db.session.commit()
        db.session.rollback()
        db.session.delete(row)
        with pytest.raises(ValueError, match='imutável'): db.session.commit()
        db.session.rollback()
        assert PedidoCompraService().update(pedido.id, {'status': 'confirmado'}).success
        assert not prepare_valuation(pedido.id, PLAN | {'source_currency': 'USD'}, actor='admin').success
        assert prepare_valuation(pedido.id, PLAN, actor='admin').success
        assert freeze('order', pedido.id, pricing(item), actor='admin').code == 200
        assert PurchasePricing.query.count() == OrderValuation.query.count() == 1


@pytest.mark.parametrize('field,value', [('quantidade', 9), ('preco_unitario', 9), ('material_unidade_id', 999)])
def test_generic_order_item_edits_do_not_change_frozen_prices(app, field, value):
    with app.app_context():
        pedido, item, unit = order()
        assert freeze('order', pedido.id, pricing(item), actor='admin').success
        assert not ItemPedidoCompraService().update(item.id, {field: value}).success
        assert not ItemPedidoCompraService().trash(item.id).success
        assert not PedidoCompraService().update(pedido.id, {'valor_frete': 9}).success
        assert get_pricing('order', pedido.id).currency_code == 'BRL'


def test_quote_api_maintenance_and_direct_reparent_are_blocked_but_winner_is_allowed(app, client):
    _login_admin(app, client)
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        assert freeze('quotation', quote.id, pricing(item), actor='admin').success
        quote_id, item_id, requested_id = quote.id, item.id, requested.id
        other = _criar_cotacao(process, _criar_fornecedor(razao_social='Outro'))
        other_id = other.id
        assert not ItemCotacaoService().update(item.id, {'cotacao_id': other.id}).success
    for path, method, data in [
        (f'/api/estoque/item-cotacaos/{item_id}', 'put', {'preco_unitario': 9}),
        (f'/api/estoque/item-cotacaos/{item_id}/trash', 'post', {}),
        (f'/api/estoque/cotacaos/{quote_id}/trash', 'post', {}),
        (f'/api/estoque/item-processo-cotacaos/{requested_id}', 'put', {'material_id': 999}),
        (f'/api/estoque/item-cotacaos/', 'post', {'cotacao_id': quote_id, 'item_processo_cotacao_id': requested_id, 'preco_unitario': 1}),
    ]:
        response = getattr(client, method)(path, json=data)
        assert response.status_code == 422, (path, response.get_data(as_text=True))
    response = client.post(f'/api/estoque/item-cotacaos/{item_id}/selecionar-vencedor', json={})
    assert response.status_code == 200, response.get_data(as_text=True)


def test_comparison_uses_decimal_order_and_blocks_mixed_or_missing_currency(app):
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        second = _criar_cotacao(process, _criar_fornecedor(razao_social='Outro'))
        second_item = _criar_item_cotacao(second, requested)
        assert freeze('quotation', quote.id, pricing(item, price='12345678901234567.123456789012', quantity='1'), actor='admin').success
        with pytest.raises(ValueError, match='todas'): stock.selecionar_item_cotacao_vencedor(item.id)
        assert freeze('quotation', second.id, pricing(second_item, price='12345678901234567.123456789011', quantity='1'), actor='admin').success
        result = comparison(process.id)
        assert [line['id'] for line in result['items']] == [second_item.id, item.id]
        stock.selecionar_item_cotacao_vencedor(second_item.id)
        assert comparison(process.id)['items'][0]['selected']


def test_mixed_currency_selection_and_generation_refuse_without_side_effects(app):
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        assert create_currency({'code': 'USD', 'name': 'Dollar', 'decimal_places': 2}).success
        second = _criar_cotacao(process, _criar_fornecedor(razao_social='Outro'))
        second_item = _criar_item_cotacao(second, requested)
        assert freeze('quotation', quote.id, pricing(item), actor='admin').success
        assert freeze('quotation', second.id, pricing(second_item, currency='USD'), actor='admin').success
        with pytest.raises(ValueError, match='Moedas diferentes'): stock.selecionar_item_cotacao_vencedor(item.id)
        item.selecionado_como_vencedor = True  # escritor interno não pode contornar validação da geração
        db.session.commit()
        with pytest.raises(ValueError, match='Moedas diferentes'): stock.gerar_pedidos_de_cotacao(process.id, actor='admin')
        assert get_pricing('order', 1) is None
        assert ItemPedidoCompra.query.count() == 0


def test_missing_duplicate_unknown_items_and_unsupported_products_are_rejected(app):
    with app.app_context():
        pedido, item, unit = order()
        for data in [pricing(item) | {'currency_code': 'XXX'}, pricing(item) | {'items': []},
                     pricing(item) | {'items': pricing(item)['items'] * 2},
                     pricing(item) | {'items': [{'id': 999, 'quantity': '1', 'unit_price': '1'}]},
                     pricing(item, quantity='0.000000000001', price='0.000000000001')]:
            assert not freeze('order', pedido.id, data, actor='admin').success
        assert PurchasePricing.query.count() == 0


def test_json_form_errors_and_cross_process_quote_lookup(app, client):
    _login_admin(app, client)
    with app.app_context():
        pedido, item, unit = order()
        ident, item_id = pedido.id, item.id
    path = f'/estoque/pedido-compras/{ident}/cadastro-monetario'
    response = client.get(path)
    assert response.status_code == 200 and 'Float' in response.get_data(as_text=True)
    response = client.post(path, data={'currency_code': 'BRL', 'freight': '0', 'item_id': str(item_id),
                                      f'quantity_{item_id}': '2', f'unit_price_{item_id}': '1,234'})
    assert response.status_code == 422 and '1,234' in response.get_data(as_text=True)
    response = client.post(path, json={'currency_code': 'BRL', 'freight': '0',
                                     'items': [{'id': item_id, 'quantity': '2', 'unit_price': '0.123456789012'}]})
    assert response.status_code == 201, response.get_data(as_text=True)
    assert client.get(path, json={}).json['data']['snapshot']['items'][0]['unit_price'] == '0.123456789012'


def test_migration_matches_orm_is_idempotent_and_preserves_data(app):
    with app.app_context():
        migration = importlib.import_module('migrations.versions.b48d5e09a673_purchase_pricing')
        with db.engine.begin() as connection:
            original = migration.op
            migration.op = Operations(MigrationContext.configure(connection))
            try:
                migration.upgrade(); migration.upgrade()
            finally:
                migration.op = original
        pedido, item, unit = order()
        assert freeze('order', pedido.id, pricing(item), actor='admin').success
        with db.engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            try:
                with pytest.raises(RuntimeError, match='preserve'): migration.downgrade()
            finally:
                migration.op = original
        assert PurchasePricing.query.count() == 1


def test_real_comparison_js_preserves_exact_strings_server_order_and_errors():
    import subprocess
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / 'static/js/estoque/processo_cotacao_detalhe.js').read_text(encoding='utf-8')
    component = script[script.index('  function initAbaComparacao(config)'):script.index('  document.addEventListener("DOMContentLoaded", init);')]
    harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const component = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
async function run(payload, failure=false) {
  const calls=[], listeners={}; const tbody={innerHTML:''};
  const headers=Array.from({length:7},()=>({textContent:''}));
  const table={dataset:{},querySelectorAll:()=>headers};
  const document={querySelector:s=>s.includes('table[data-datatable]')?table:tbody,
    addEventListener:(name,fn)=>listeners[name]=fn};
  const TesseractData={esc:s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;'),
    _json:async url=>{calls.push(url);if(failure)throw new Error('Moedas diferentes');return payload;}};
  const Number=()=>{throw new Error('Valores exatos não podem virar Number');};
  const window={simpleDatatables:{DataTable:()=>{throw new Error('Ordenação exata vem do servidor');}}};
  vm.runInNewContext(component+'\ninitAbaComparacao({processoCotacaoId:7,apiBaseItens:"legacy"});',
    {document,TesseractData,Number,window},{timeout:1000});
  await new Promise(resolve=>setImmediate(resolve));
  return {tbody,headers,calls};
}
(async()=>{
 const payload={exact:true,currency_code:'USD',items:[
  {id:2,material:'<script>',supplier:'B',quantity:'1',unit_price:'12345678901234567.123456789011',subtotal:'12345678901234567.123456789011',selected:false,generated:false},
  {id:1,material:'A',supplier:'A',quantity:'1',unit_price:'12345678901234567.123456789012',subtotal:'12345678901234567.123456789012',selected:true,generated:false}]};
 const exact=await run(payload);
 assert.equal(exact.calls.length,1);
 assert.ok(exact.tbody.innerHTML.indexOf(payload.items[0].unit_price)<exact.tbody.innerHTML.indexOf(payload.items[1].unit_price));
 assert.ok(exact.tbody.innerHTML.includes('&lt;script&gt;'));
 assert.ok(exact.tbody.innerHTML.includes('selecionar-vencedor'));
 assert.ok(exact.tbody.innerHTML.includes('desmarcar-vencedor'));
 assert.equal(exact.headers[3].textContent,'Preço unitário (USD)');
 payload.items[0].generated=true;
 assert.ok((await run(payload)).tbody.innerHTML.includes('Já gerado'));
 const blocked=await run(null,true);
 assert.equal(blocked.calls.length,1);
 assert.ok(blocked.tbody.innerHTML.includes('Moedas diferentes'));
 console.log('Comparação exata do script real aprovada');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    result = subprocess.run(['node', '-e', harness], input=json.dumps(component), text=True,
                            encoding='utf-8', capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'Comparação exata' in result.stdout


def test_concurrent_freezes_choose_one_complete_snapshot(app, tmp_path):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier = threading.Barrier(2)
    results, errors = [], []
    with app.app_context():
        pedido, item, unit = order()
        ident, item_id = pedido.id, item.id
        original, engine = _file_database(app, tmp_path)
    def worker(price):
        try:
            with app.app_context():
                db.session.get(ItemPedidoCompra, item_id)  # aquecer identity map antes da reserva
                barrier.wait(timeout=10)
                results.append(freeze('order', ident, {'currency_code': 'BRL', 'freight': '0',
                    'items': [{'id': item_id, 'quantity': '2', 'unit_price': price}]}, actor='admin'))
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(price,)) for price in ('1.123456789012', '2.123456789012')]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors, errors
        assert sorted(result.code for result in results) == [201, 409]
        with app.app_context():
            assert PurchasePricing.query.count() == 1
            exact = get_pricing('order', ident).to_dict()['snapshot']['items'][0]
            item = db.session.get(ItemPedidoCompra, item_id)
            assert item.preco_unitario == float(exact['unit_price'])
            assert not ItemPedidoCompraService().update(item_id, {'preco_unitario': 9}).success
    finally:
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
            engine.dispose()


def test_quote_deletion_and_requested_item_rewrite_are_guarded_at_orm(app):
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        assert freeze('quotation', quote.id, pricing(item), actor='admin').success
        requested.material_unidade_id = 999
        with pytest.raises(ValueError, match='congelado'): db.session.commit()
        db.session.rollback()
        db.session.delete(item)
        with pytest.raises(ValueError, match='congelado'): db.session.commit()
        db.session.rollback()
        db.session.delete(quote)
        with pytest.raises(ValueError, match='congelado'): db.session.commit()
        db.session.rollback()
        assert ItemCotacao.query.count() == 1


def test_original_valuation_cannot_receive_a_new_pricing_snapshot(app):
    with app.app_context():
        pedido, item, unit = order()
        assert PedidoCompraService().update(pedido.id, {'status': 'confirmado'}).success
        original = prepare_valuation(pedido.id, PLAN, actor='admin')
        assert original.success
        assert not freeze('order', pedido.id, pricing(item), actor='admin').success
        assert OrderValuation.query.one().to_dict() == original.data
        assert PurchasePricing.query.count() == 0


def test_generation_failure_rolls_back_all_new_orders_pricings_and_links(app, monkeypatch):
    from addons.addon_estoque.root.services import purchase_pricing_service as service
    from services.core.organization_service import Result
    from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        second_requested = _criar_item_processo_cotacao(process, requested.material, unit)
        second = _criar_cotacao(process, _criar_fornecedor(razao_social='Outro'))
        second_item = _criar_item_cotacao(second, second_requested)
        assert freeze('quotation', quote.id, pricing(item), actor='admin').success
        assert freeze('quotation', second.id, pricing(second_item), actor='admin').success
        stock.selecionar_item_cotacao_vencedor(item.id)
        stock.selecionar_item_cotacao_vencedor(second_item.id)
        original, calls = service.freeze, []
        def fail_second(*args, **kwargs):
            calls.append(args[1])
            return original(*args, **kwargs) if len(calls) == 1 else Result(False, error='falha monetária injetada', code=409)
        with monkeypatch.context() as patch:
            patch.setattr(service, 'freeze', fail_second)
            with pytest.raises(ValueError, match='falha monetária'): stock.gerar_pedidos_de_cotacao(process.id, actor='admin')
        assert len(calls) == 2
        assert PedidoCompra.query.count() == ItemPedidoCompra.query.count() == 0
        assert PurchasePricing.query.count() == 2  # só respostas originais
        assert all(i.pedido_compra_item_id is None for i in ItemCotacao.query.all())
        assert process.status == 'aberto'


def test_distinct_frozen_factors_cannot_be_ranked_as_equal_purchase_units(app):
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        assert freeze('quotation', quote.id, pricing(item), actor='admin').success
        unit.fator_para_base = 40
        db.session.commit()
        second = _criar_cotacao(process, _criar_fornecedor(razao_social='Outro'))
        second_item = _criar_item_cotacao(second, requested)
        assert freeze('quotation', second.id, pricing(second_item), actor='admin').success
        with pytest.raises(ValueError, match='Fatores'): comparison(process.id)
        with pytest.raises(ValueError, match='Fatores'): stock.selecionar_item_cotacao_vencedor(item.id)


def test_quote_form_is_scoped_to_its_process_and_shows_frozen_prices(app, client):
    _login_admin(app, client)
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        other = _criar_processo_cotacao()
        process_id, quote_id, item_id, other_id = process.id, quote.id, item.id, other.id
    path = f'/estoque/processo-cotacaos/{process_id}/cotacoes/{quote_id}/cadastro-monetario'
    assert client.get(path).status_code == 200
    assert client.get(path.replace(f'/{process_id}/cotacoes/', f'/{other_id}/cotacoes/')).status_code == 404
    response = client.post(path, json={'currency_code': 'BRL', 'freight': '0',
        'items': [{'id': item_id, 'quantity': '2', 'unit_price': '0.123456789012'}]})
    assert response.status_code == 201
    page = client.get(path)
    assert page.status_code == 200 and '0.123456789012' in page.get_data(as_text=True)
    assert 'name="unit_price_' not in page.get_data(as_text=True)
    result = client.get(f'/estoque/processo-cotacaos/{process_id}/comparacao-monetaria').json
    assert result['exact'] and result['currency_code'] == 'BRL'


def test_monetary_endpoints_require_authentication_before_exposing_prices(app, client):
    with app.app_context():
        pedido, item, unit = order()
        assert freeze('order', pedido.id, pricing(item), actor='admin').success
        ident = pedido.id
    assert client.get(f'/estoque/pedido-compras/{ident}/cadastro-monetario', json={}).status_code in (401, 302)


def test_migration_rejects_incompatible_table_before_changes(monkeypatch):
    migration = importlib.import_module('migrations.versions.b48d5e09a673_purchase_pricing')
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_estoque_purchase_pricing (id INTEGER PRIMARY KEY, snapshot_json TEXT)')
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match='Schema incompatível'): migration.upgrade()
        assert {col['name'] for col in sa.inspect(connection).get_columns(migration.NAME)} == {'id', 'snapshot_json'}


def test_concurrent_quote_transfer_cannot_leave_a_stale_frozen_source(app, tmp_path):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier = threading.Barrier(2)
    results, errors = {}, []
    with app.app_context():
        process, quote, item, requested, unit = quotation()
        other_process = _criar_processo_cotacao()
        assert bind_context('process', other_process.id, {'organization_code': 'A'}, actor='admin').success
        other_requested = _criar_item_processo_cotacao(other_process, requested.material, unit)
        other_quote = _criar_cotacao(other_process)
        quote_id, item_id, requested_id = quote.id, item.id, requested.id
        target_quote_id, target_requested_id = other_quote.id, other_requested.id
        original, engine = _file_database(app, tmp_path)
    def worker(action):
        try:
            with app.app_context():
                db.session.get(ItemCotacao, item_id)
                barrier.wait(timeout=10)
                if action == 'freeze':
                    results[action] = freeze('quotation', quote_id, {'currency_code': 'BRL', 'freight': '0',
                        'items': [{'id': item_id, 'quantity': '2', 'unit_price': '1'}]}, actor='admin')
                else:
                    results[action] = ItemCotacaoService().update(item_id,
                        {'cotacao_id': target_quote_id, 'item_processo_cotacao_id': target_requested_id})
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(action,)) for action in ('freeze', 'transfer')]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors, errors
        assert sum(result.success for result in results.values()) == 1
        with app.app_context():
            item = db.session.get(ItemCotacao, item_id)
            if results['freeze'].success:
                assert item.cotacao_id == quote_id and item.item_processo_cotacao_id == requested_id
                assert get_pricing('quotation', quote_id) is not None
            else:
                assert item.cotacao_id == target_quote_id and item.item_processo_cotacao_id == target_requested_id
                assert PurchasePricing.query.count() == 0
    finally:
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
            engine.dispose()
