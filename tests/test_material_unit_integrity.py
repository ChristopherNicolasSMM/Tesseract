"""Unidades: fatores finitos, base histórica e referências preservadas."""
import pytest
from tests.test_addon_estoque import (app, client, _login_admin, _criar_material,
    _criar_pedido_compra, _criar_item_pedido_compra)
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
from addons.addon_estoque.root.services.material_unidade_service import MaterialUnidadeService
from addons.addon_estoque.root.services import estoque_service
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao, obter_fator
from addons.addon_estoque.root.services.material_service import MaterialService


def units():
    # Fixtures usam create_all; o catálogo de produção é populado por migration.
    for code in ('KG', 'G', 'PCT', 'UN', 'CX', 'L'):
        if not UnidadeCatalogo.query.filter_by(codigo=code).first():
            db.session.add(UnidadeCatalogo(codigo=code, descricao=code, dimensao='teste'))
    db.session.commit()
    material = _criar_material(nome='Material unidade protegida')
    service = MaterialUnidadeService()
    result = service.create({'material_id': material.id, 'unidade': 'KG',
        'fator_para_base': 1, 'is_unidade_base': True})
    assert result.success, result.error
    base = result.data
    result = service.create({'material_id': material.id, 'unidade': 'PCT', 'fator_para_base': 25})
    assert result.success, result.error
    return material, base, result.data


def test_nonfinite_factor_rejected_before_persistence(app):
    with app.app_context():
        material, base, alternative = units()
        result = MaterialUnidadeService().update(alternative.id, {'fator_para_base': 'inf'})
        assert not result.success
        assert db.session.get(MaterialUnidade, alternative.id).fator_para_base == 25


def test_base_change_cannot_relabel_existing_stock(app):
    with app.app_context():
        material, base, alternative = units()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        result = MaterialUnidadeService().update(base.id, {'unidade': 'G'})
        assert not result.success
        assert db.session.get(Material, material.id).unidade_medida == 'KG'


def test_referenced_conversion_cannot_move_to_other_material(app):
    with app.app_context():
        material, base, alternative = units()
        pedido = _criar_pedido_compra()
        _criar_item_pedido_compra(pedido, material, alternative)
        other = _criar_material(nome='Outro material unidade protegida')
        result = MaterialUnidadeService().update(alternative.id, {'material_id': other.id})
        assert not result.success
        assert db.session.get(MaterialUnidade, alternative.id).material_id == material.id


def test_referenced_conversion_cannot_be_trashed(app):
    with app.app_context():
        material, base, alternative = units()
        pedido = _criar_pedido_compra()
        _criar_item_pedido_compra(pedido, material, alternative)
        result = MaterialUnidadeService().trash(alternative.id)
        assert not result.success
        assert not db.session.get(MaterialUnidade, alternative.id).is_deleted


def test_duplicate_conversion_code_is_rejected(app):
    with app.app_context():
        material, base, alternative = units()
        result = MaterialUnidadeService().create({'material_id': material.id,
            'unidade': 'PCT', 'fator_para_base': 30})
        assert not result.success
        assert MaterialUnidade.query.filter_by(material_id=material.id, unidade='PCT').count() == 1


def test_base_deactivation_cannot_remove_historical_conversion(app):
    with app.app_context():
        material, base, alternative = units()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        result = MaterialUnidadeService().update(base.id, {'ativo': False})
        assert not result.success
        assert db.session.get(MaterialUnidade, base.id).ativo


@pytest.mark.parametrize('factor', [0, -1, 'nan', '-inf', True, None])
def test_invalid_factors_preserve_unused_conversion(app, factor):
    with app.app_context():
        material, base, alternative = units()
        result = MaterialUnidadeService().update(alternative.id, {'fator_para_base': factor})
        assert not result.success
        assert db.session.get(MaterialUnidade, alternative.id).fator_para_base == 25


def test_unused_factor_can_change_without_changing_base_or_stock(app):
    with app.app_context():
        material, base, alternative = units()
        result = MaterialUnidadeService().update(alternative.id, {'fator_para_base': '30'})
        assert result.success, result.error
        assert alternative.fator_para_base == 30
        assert material.unidade_medida == 'KG'
        assert obter_fator(material.id, 'PCT', 'KG') == 30
        assert Movimentacao.query.count() == Saldo.query.count() == 0


@pytest.mark.parametrize('change', [{'unidade': 'G'}, {'is_unidade_base': False}, {'fator_para_base': 2}])
def test_base_cannot_reinterpret_other_unused_conversions(app, change):
    with app.app_context():
        material, base, alternative = units()
        assert not MaterialUnidadeService().update(base.id, change).success
        assert material.unidade_medida == 'KG'
        assert alternative.fator_para_base == 25


def test_standalone_unused_base_can_change_and_commit_failure_rolls_back_mirror(app, monkeypatch):
    with app.app_context():
        material, base, alternative = units()
        service = MaterialUnidadeService()
        assert service.trash(alternative.id).success
        assert service.delete_permanent(alternative.id).success
        def fail():
            db.session.flush()
            raise RuntimeError('falha depois de gravar base e espelho')
        with monkeypatch.context() as patch:
            patch.setattr(db.session, 'commit', fail)
            result = service.update(base.id, {'unidade': 'G'})
        assert not result.success
        assert db.session.get(Material, material.id).unidade_medida == 'KG'
        assert db.session.get(MaterialUnidade, base.id).unidade == 'KG'
        result = service.update(base.id, {'unidade': 'G'})
        assert result.success, result.error
        assert material.unidade_medida == 'G'
        assert Movimentacao.query.count() == 0


def test_known_legacy_base_can_be_attached_after_stock_without_conversion(app):
    with app.app_context():
        material = _criar_material(nome='Base legada conhecida')
        db.session.add(UnidadeCatalogo(codigo='KG', descricao='Quilograma', dimensao='massa'))
        db.session.commit()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        before = estoque_service.consultar_saldo(material.id)
        result = MaterialUnidadeService().create({'material_id': material.id, 'unidade': 'KG',
            'fator_para_base': 1, 'is_unidade_base': True})
        assert result.success, result.error
        assert estoque_service.consultar_saldo(material.id) == before
        assert Movimentacao.query.count() == 1


def test_unknown_legacy_base_with_stock_cannot_be_assumed(app):
    with app.app_context():
        material = _criar_material(nome='Base legada desconhecida')
        material.unidade_medida = None
        db.session.add(UnidadeCatalogo(codigo='KG', descricao='Quilograma', dimensao='massa'))
        db.session.commit()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        result = MaterialUnidadeService().create({'material_id': material.id, 'unidade': 'KG',
            'fator_para_base': 1, 'is_unidade_base': True})
        assert not result.success
        assert db.session.get(Material, material.id).unidade_medida is None
        assert estoque_service.consultar_saldo(material.id)['quantidade_atual'] == 10


@pytest.mark.parametrize('archived', [False, True])
def test_recipe_weak_reference_freezes_conversion_even_in_archive(app, archived):
    from tests.test_mash_control_ingredient_resolution import _criar_receita, _linha_saneamento
    with app.app_context():
        material, base, alternative = units()
        recipe = _criar_receita()
        ingredient = _linha_saneamento(recipe, material_id=material.id, unidade_medida='PCT', quantidade=2)
        recipe.is_deleted = ingredient.is_deleted = archived
        db.session.commit()
        svc = MaterialUnidadeService()
        assert not svc.update(alternative.id, {'fator_para_base': 30}).success
        assert not svc.trash(alternative.id).success
        assert alternative.fator_para_base == 25
        assert ingredient.quantidade == 2


def test_archived_purchase_reference_and_zero_balance_still_freeze_units(app):
    with app.app_context():
        material, base, alternative = units()
        pedido = _criar_pedido_compra()
        item = _criar_item_pedido_compra(pedido, material, alternative)
        pedido.is_deleted = item.is_deleted = True
        db.session.commit()
        assert not MaterialUnidadeService().update(alternative.id, {'fator_para_base': 30}).success
        assert item.fator_conversao_aplicado == 25
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        estoque_service.registrar_movimentacao(material.id, 'saida', 10)
        assert estoque_service.consultar_saldo(material.id)['quantidade_atual'] == 0
        assert not MaterialUnidadeService().trash(base.id).success


def test_restore_conflict_is_friendly_and_next_write_succeeds(app):
    with app.app_context():
        material, base, alternative = units()
        svc = MaterialUnidadeService()
        assert svc.trash(alternative.id).success
        result = svc.create({'material_id': material.id, 'unidade': 'PCT', 'fator_para_base': 30})
        assert result.success, result.error
        new = result.data
        result = svc.restore(alternative.id)
        assert not result.success and result.code == 409
        assert alternative.is_deleted
        assert svc.update(new.id, {'fator_para_base': 35}).success
        assert svc.trash(new.id).success
        assert svc.restore(alternative.id).success
        assert alternative.fator_para_base == 25


def test_base_archive_restore_and_replacement_respect_other_rows(app):
    with app.app_context():
        material, base, alternative = units()
        svc = MaterialUnidadeService()
        assert not svc.trash(base.id).success
        assert svc.trash(alternative.id).success
        assert not svc.trash(base.id).success  # conversão arquivada também guarda fator antigo
        assert svc.delete_permanent(alternative.id).success
        assert svc.trash(base.id).success
        assert db.session.get(Material, material.id).unidade_medida is None
        assert svc.restore(base.id).success
        assert material.unidade_medida == 'KG'


@pytest.mark.parametrize('case', ['missing', 'deleted', 'inactive'])
def test_units_require_available_parent(app, case):
    with app.app_context():
        material, base, alternative = units()
        mid = material.id
        if case == 'missing':
            mid = 999999
        elif case == 'deleted':
            material.is_deleted = True
        else:
            material.ativo = False
        db.session.commit()
        result = MaterialUnidadeService().create({'material_id': mid, 'unidade': 'CX', 'fator_para_base': 50})
        assert not result.success
        assert MaterialUnidade.query.count() == 2


def test_bulk_inactivation_uses_same_protection_as_single_update(app):
    with app.app_context():
        material, base, alternative = units()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 1, custo_unitario=2)
        result = MaterialUnidadeService().inactivate_many([base.id, alternative.id])
        assert all(not row['sucesso'] for row in result['resultados'])
        assert base.ativo and alternative.ativo


def test_new_explicit_conversion_on_used_material_preserves_old_factor_and_ledger(app):
    with app.app_context():
        material, base, alternative = units()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        before = estoque_service.consultar_saldo(material.id)
        row = cadastrar_conversao(material.id, 'CX', 50, unidade_base_esperada='KG')
        assert row['fator_para_base'] == 50
        assert alternative.fator_para_base == 25
        assert estoque_service.consultar_saldo(material.id) == before
        assert Movimentacao.query.count() == 1


def test_reading_conversion_rejects_corrupt_base_factor(app):
    with app.app_context():
        material, base, alternative = units()
        base.fator_para_base = 2  # legado inválido sem passar pelo service
        db.session.commit()
        assert obter_fator(material.id, 'PCT', 'KG') is None


def test_api_and_form_return_errors_without_changing_used_unit(app, client):
    _login_admin(app, client)
    with app.app_context():
        material, base, alternative = units()
        estoque_service.registrar_movimentacao(material.id, 'entrada', 10, custo_unitario=4)
        uid = alternative.id
    response = client.put(f'/api/estoque/material-unidades/{uid}', json={'fator_para_base': 30})
    assert response.status_code == 409
    response = client.post(f'/estoque/material-unidades/{uid}', data={'fator_para_base': '30'}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(MaterialUnidade, uid).fator_para_base == 25


def test_material_parent_cannot_disappear_while_units_exist(app):
    with app.app_context():
        material, base, alternative = units()
        result = MaterialService().trash(material.id)
        assert not result.success
        assert not db.session.get(Material, material.id).is_deleted


def test_parent_permanent_delete_protects_archived_conversions(app):
    with app.app_context():
        material, base, alternative = units()
        material.is_deleted = base.is_deleted = alternative.is_deleted = True
        db.session.commit()
        assert not MaterialService().delete_permanent(material.id).success
        assert Material.query.count() == 1
        assert MaterialUnidade.query.count() == 2


def test_unreferenced_material_can_be_archived_and_restored(app):
    with app.app_context():
        material = _criar_material(nome='Material sem unidade nem histórico')
        svc = MaterialService()
        assert svc.trash(material.id).success
        assert svc.restore(material.id).success
        assert not material.is_deleted


def test_corrupt_legacy_base_restore_conflict_does_not_break_session(app):
    with app.app_context():
        material, base, alternative = units()
        base.is_deleted = True
        replacement = MaterialUnidade(material_id=material.id, unidade='G',
            fator_para_base=1, is_unidade_base=True, tipo_uso='ambos', ativo=True)
        db.session.add(replacement)
        db.session.commit()
        result = MaterialUnidadeService().restore(base.id)
        assert not result.success and result.code == 409
        assert base.is_deleted
        assert MaterialUnidadeService().update(alternative.id, {'tipo_uso': 'misterioso'}).code == 422
        db.session.commit()  # rollback do conflito deixou sessão utilizável


@pytest.mark.parametrize('public_writer', [False, True])
def test_concurrent_conversion_creation_is_unique_across_public_and_crud(app, tmp_path, public_writer):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier = threading.Barrier(2)
    results, errors = [], []
    with app.app_context():
        material, base, alternative = units()
        mid = material.id
        original, engine = _file_database(app, tmp_path)
    def worker(use_public):
        try:
            with app.app_context():
                db.session.get(Material, mid)
                list(MaterialUnidade.query.filter_by(material_id=mid))
                barrier.wait(timeout=10)
                if use_public:
                    results.append(cadastrar_conversao(mid, 'CX', 50, unidade_base_esperada='KG'))
                else:
                    results.append(MaterialUnidadeService().create({'material_id': mid, 'unidade': 'CX', 'fator_para_base': 50}))
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(flag,)) for flag in (False, public_writer)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(t.is_alive() for t in threads)
        assert not errors, errors
        assert len(results) == 2
        if not public_writer:
            assert sorted(result.success for result in results) == [False, True]
        with app.app_context():
            assert MaterialUnidade.query.filter_by(material_id=mid, unidade='CX').count() == 1
            assert obter_fator(mid, 'CX', 'KG') == 50
            assert Movimentacao.query.count() == Saldo.query.count() == 0
    finally:
        for thread in threads:
            thread.join(timeout=15)
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
        engine.dispose()


def test_first_movement_and_unused_base_change_share_material_reservation(app, tmp_path):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier = threading.Barrier(2)
    results, errors = {}, []
    with app.app_context():
        material, base, alternative = units()
        svc = MaterialUnidadeService()
        assert svc.trash(alternative.id).success
        assert svc.delete_permanent(alternative.id).success
        mid, uid = material.id, base.id
        original, engine = _file_database(app, tmp_path)
    def worker(action):
        try:
            with app.app_context():
                db.session.get(Material, mid)
                db.session.get(MaterialUnidade, uid)
                barrier.wait(timeout=10)
                if action == 'unit':
                    results[action] = MaterialUnidadeService().update(uid, {'unidade': 'G'})
                else:
                    results[action] = estoque_service.registrar_movimentacao(mid, 'entrada', 10, custo_unitario=4)
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=worker, args=(action,)) for action in ('unit', 'stock')]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(t.is_alive() for t in threads)
        assert not errors, errors
        with app.app_context():
            expected_code = 'G' if results['unit'].success else 'KG'
            assert db.session.get(Material, mid).unidade_medida == expected_code
            assert db.session.get(MaterialUnidade, uid).unidade == expected_code
            assert estoque_service.consultar_saldo(mid)['quantidade_atual'] == 10
            assert estoque_service.consultar_saldo(mid)['custo_medio'] == 4
            assert Movimentacao.query.count() == 1
            assert not MaterialUnidadeService().update(uid, {'unidade': 'UN'}).success
    finally:
        for thread in threads:
            thread.join(timeout=15)
        with app.app_context():
            db.session.remove()
            db.engines[None] = original
        engine.dispose()
