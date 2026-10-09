from decimal import Decimal
import pytest
from tests.test_organization_stock import app, client, finance, move, _criar_material, _login_admin
from core.db import db
from model.core.user import User
from addons.addon_estoque.root.model.organization_stock import OrganizationMovement
from addons.addon_estoque.root.services import estoque_service as stock, material_lookup
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.services.organization_recipe_preview import preview


def setup():
    finance(); finance('B', 'USD')
    material = _criar_material()
    recipe = MashRecipe(name='Prévia organizacional', versao=1, origem_receita='Manual')
    plant = BrewPlant(name='Planta prévia')
    db.session.add_all([recipe, plant]); db.session.flush()
    for quantity in (2, 3):
        db.session.add(RecipeIngredient(recipe_id=recipe.id, descricao_origem='Malte',
            material_id=material.id, quantidade=quantity, unidade_medida='kg', status_resolucao='resolvido'))
    db.session.commit()
    return recipe, material, plant


def test_aggregate_shortage_and_exact_cost_are_scoped_and_pure(app, monkeypatch):
    with app.app_context():
        recipe, material, _ = setup()
        move(material, quantity='4', cost='0.333333333333')
        stock.registrar_movimentacao(material.id, 'entrada', 99, custo_unitario=99)
        monkeypatch.setattr(material_lookup, 'get_saldo', lambda *_: pytest.fail('Consultou saldo global'))
        before = OrganizationMovement.query.count()
        result = preview(recipe.id, ' a ')
        line = result['detalhes'][0]
        assert len(result['detalhes']) == 1 and len(line['ingredient_ids']) == 2
        assert line['quantidade'] == '5.0' and Decimal(line['quantidade_faltante']) == 1
        assert Decimal(line['custo_estimado']) == Decimal('1.6625')
        assert result['custo_completo'] and not result['estoque_suficiente']
        other = preview(recipe.id, 'B')
        assert other['currency_code'] == 'USD' and not other['custo_completo']
        assert Decimal(other['detalhes'][0]['saldo_disponivel']) == 0
        assert OrganizationMovement.query.count() == before and not db.session.dirty and not db.session.new


@pytest.mark.parametrize('code', [None, '', 'MISSING', True])
def test_explicit_existing_organization_required(app, code):
    with app.app_context():
        recipe, _, _ = setup()
        with pytest.raises(ValueError): preview(recipe.id, code)


def test_pending_ignored_zero_cost_and_removed_recipe(app):
    with app.app_context():
        recipe, material, _ = setup()
        move(material, quantity='6', cost='0')
        pending = RecipeIngredient(recipe_id=recipe.id, descricao_origem='Pendente', quantidade=1, status_resolucao='pendente')
        ignored = RecipeIngredient(recipe_id=recipe.id, descricao_origem='Ignorado', quantidade=1, status_resolucao='ignorado')
        db.session.add_all([pending, ignored]); db.session.commit()
        result = preview(recipe.id, 'A')
        assert len(result['pendencias']) == len(result['ignorados']) == 1
        assert not result['custo_completo'] and not result['estoque_suficiente']
        assert Decimal(result['custo_total_estimado']) == 0
        recipe.is_deleted = True; db.session.commit()
        with pytest.raises(ValueError, match='removida'): preview(recipe.id, 'A')


def test_route_selector_errors_json_and_auth(app, client, monkeypatch):
    with app.app_context():
        recipe, _, plant = setup(); rid, pid = recipe.id, plant.id
    url = f'/brewstation/plant-workspace/{pid}/receitas/{rid}/estoque-organizacional'
    assert client.get(url).status_code in (302, 401)
    _login_admin(app, client)
    response = client.get(url)
    assert response.status_code == 200 and b'name="organization_code"' in response.data
    assert client.get(url+'?format=json').status_code == 422
    assert client.get(url+'?organization_code=MISSING').status_code == 422
    response = client.get(url+'?organization_code=A&format=json')
    assert response.status_code == 200 and response.json['data']['organization_code'] == 'A'
    assert client.get(url.replace(f'/receitas/{rid}', '/receitas/999999')).status_code == 404
    original = User.has_permission
    monkeypatch.setattr(User, 'has_permission', lambda self, perm: False if perm == 'saldos.list' else original(self, perm))
    assert client.get(url).status_code == 403


def test_inactive_or_unconfigured_organization_is_rejected(app):
    from services.core.organization_service import save_organization, resolve_organization_by_code
    with app.app_context():
        recipe, _, _ = setup()
        org = resolve_organization_by_code('A')
        assert save_organization({'is_active': False}, org['id']).success
        with pytest.raises(ValueError, match='inativa'): preview(recipe.id, 'A')
        assert save_organization({'code': 'C', 'name': 'Sem política'}).success
        with pytest.raises(ValueError, match='política'): preview(recipe.id, 'C')


def test_full_quantity_estimate_preserves_stock_value_and_json_strings(app, client):
    with app.app_context():
        recipe, material, plant = setup()
        move(material, quantity='5', cost='0.2')
        rid, pid = recipe.id, plant.id
        result = preview(rid, 'A')
        assert Decimal(result['custo_total_estimado']) == 1
        assert result['estoque_suficiente'] and result['custo_completo']
    _login_admin(app, client)
    url = f'/brewstation/plant-workspace/{pid}/receitas/{rid}/estoque-organizacional'
    data = client.get(url+'?organization_code=A&format=json').json['data']
    assert isinstance(data['detalhes'][0]['quantidade'], str)
    assert client.get(url+'?organization_code=A').status_code == 200
    detail = client.get(f'/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}')
    assert detail.status_code == 200 and url.encode() in detail.data
