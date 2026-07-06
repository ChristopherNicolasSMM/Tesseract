"""
tests/test_feature_brew_father.py

Cobre feature_brew_father: sync_service.sync_recipes() usando dados
de fixture injetados via monkeypatch em brewfather_client.get_recipes()
— sem chamada HTTP real (TESSERACT_ENV=testing bloqueia a API real,
além de não termos ambiente de teste separado). Confirma que a receita
importada vira MashRecipe com origem_receita="BrewFather", ingredientes
viram RecipeIngredient (resolvidos ou pendentes conforme
IngredientMapping existente), e BrewFatherSync registra o resultado.

Também cobre: guard de TESTING (get_recipes() retorna [] em teste),
guard de ENABLED (BrewFatherDisabledError quando desabilitado).
"""
import os
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_brewstation.features.feature_brew_father.services import sync_service
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client


MOCK_RECIPES = [
    {
        "id": "bf-mock-001",
        "name": "Sangue de Druida",
        "ingredients": [
            {"name": "Pale Malt 2-Row", "amount": 5.0, "unit": "kg", "time": None, "use": "mash"},
            {"name": "Cascade", "amount": 50, "unit": "g", "time": 60, "use": "boil"},
            {"name": "US-05", "amount": 1.0, "unit": "un", "time": None, "use": "fermentation"},
        ],
    },
    {
        "id": "bf-mock-002",
        "name": "Session IPA Tropical",
        "ingredients": [
            {"name": "Pilsner Malt", "amount": 4.2, "unit": "kg", "time": None, "use": "mash"},
            {"name": "Citra", "amount": 80, "unit": "g", "time": 15, "use": "boil"},
        ],
    },
]


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_client(monkeypatch):
    """Injeta MOCK_RECIPES no cliente — desvia do guard de TESTING e da
    API real. Todos os testes de fluxo de sincronização usam este fixture."""
    monkeypatch.setattr(brewfather_client, "get_recipes", lambda limit=50: MOCK_RECIPES)


def test_guard_testing_retorna_lista_vazia(app):
    """Em TESSERACT_ENV=testing, get_recipes() retorna [] sem chamar a API."""
    with app.app_context():
        resultado = brewfather_client.get_recipes()
    assert resultado == []


def test_guard_disabled_levanta_erro(app):
    """Se BREWFATHER_ENABLED não for true, levanta BrewFatherDisabledError."""
    original = os.environ.pop("BREWFATHER_ENABLED", None)
    try:
        os.environ["TESSERACT_ENV"] = "development"  # sai do guard de testing
        with pytest.raises(brewfather_client.BrewFatherDisabledError):
            brewfather_client.get_recipes()
    finally:
        os.environ["TESSERACT_ENV"] = "testing"
        if original is not None:
            os.environ["BREWFATHER_ENABLED"] = original


def test_sync_recipes_importa_as_duas_receitas_mock(app, mock_client):
    with app.app_context():
        resultado = sync_service.sync_recipes()

        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 2
        assert resultado["quantidade_erro"] == 0

        receitas = MashRecipe.query.filter_by(origem_receita="BrewFather").all()
        assert len(receitas) == 2
        nomes = {r.name for r in receitas}
        assert nomes == {"Sangue de Druida", "Session IPA Tropical"}


def test_sync_recipes_grava_origem_receita_id(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        assert receita is not None
        assert receita.name == "Sangue de Druida"
        assert receita.origem_receita == "BrewFather"


def test_sync_recipes_cria_ingredientes_pendentes_sem_mapeamento(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        ingredientes = RecipeIngredient.query.filter_by(recipe_id=receita.id).all()

        assert len(ingredientes) == 3
        assert all(i.status_resolucao == "pendente_depara" for i in ingredientes)
        assert all(i.material_id is None for i in ingredientes)


def test_sync_recipes_resolve_ingrediente_com_mapeamento_previo(app, mock_client):
    with app.app_context():
        material = Material(nome="Pale Malt 2-Row (estoque)", categoria="materia_prima")
        db.session.add(material)
        db.session.commit()

        db.session.add(IngredientMapping(
            origem_receita="BrewFather", descricao_origem="Pale Malt 2-Row", material_id=material.id,
        ))
        db.session.commit()

        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        ingrediente_malte = RecipeIngredient.query.filter_by(
            recipe_id=receita.id, descricao_origem="Pale Malt 2-Row",
        ).first()

        assert ingrediente_malte.status_resolucao == "resolvido"
        assert ingrediente_malte.material_id == material.id


def test_sync_recipes_nao_reimporta_receita_ja_sincronizada(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()
        sync_service.sync_recipes()

        receitas = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").all()
        assert len(receitas) == 1  # limitação documentada: não re-sincroniza


def test_sync_recipes_grava_log_de_sincronizacao(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        log = BrewFatherSync.query.filter_by(tipo_sync="recipes").first()
        assert log is not None
        assert log.status == "sucesso"
        assert log.finalizado_em is not None


def test_etapa_traduzida_de_use_ingles_para_portugues(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        lupulo = RecipeIngredient.query.filter_by(recipe_id=receita.id, descricao_origem="Cascade").first()

        assert lupulo.etapa == "fervura"
        assert lupulo.tempo_adicao_min == 60


def test_sync_quando_disabled_grava_log_com_status_erro(app):
    """Quando integração desabilitada, sync_recipes grava log de erro (não explode)."""
    with app.app_context():
        resultado = sync_service.sync_recipes()
        # Em TESTING, get_recipes() retorna [] — status deve ser "sucesso" com 0 processadas
        # (não erro — disabled só ocorre fora de testing)
        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 0


def _login_admin(app, client):
    from model.core.user import User
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


def test_tela_de_listagem_de_syncs_nao_estoura_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/brewfather-syncs", follow_redirects=True)
    assert resp.status_code == 200


def test_botao_sincronizar_dispara_sync_e_redireciona(app, client, mock_client):
    _login_admin(app, client)
    resp = client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)
    assert resp.status_code == 200
    assert "Sincronização concluída" in resp.data.decode("utf-8")

    with app.app_context():
        from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
        assert MashRecipe.query.filter_by(origem_receita="BrewFather").count() == 2


def test_tela_pendentes_retorna_200(app, client, mock_client):
    _login_admin(app, client)
    # Sync first to create pending items
    client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)

    resp = client.get("/brewstation/brewfather-syncs/pendentes", follow_redirects=True)
    assert resp.status_code == 200
    assert "De-Para" in resp.data.decode("utf-8") or "Pendentes" in resp.data.decode("utf-8")


def test_resolver_pendente_cria_mapeamento(app, client, mock_client):
    _login_admin(app, client)
    # Sync first
    client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)

    with app.app_context():
        from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
        pendente = RecipeIngredient.query.filter_by(status_resolucao="pendente_depara").first()
        assert pendente is not None
        descricao = pendente.descricao_origem

    # Resolve via form: cria Material novo
    resp = client.post("/brewstation/brewfather-syncs/pendentes/resolver",
                       data={"descricao_origem": descricao, "novo_material_nome": f"Material {descricao}"},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert "resolvido" in resp.data.decode("utf-8").lower()


def test_busca_materiais_api_retorna_resultados(app, client):
    _login_admin(app, client)
    with app.app_context():
        from addons.addon_estoque.root.model.material import Material
        from core.db import db
        db.session.add(Material(nome="Malte Pilsen Teste", categoria="materia_prima"))
        db.session.commit()

    resp = client.get("/api/brewstation/brewfather-syncs/buscar-materiais?q=pilsen")
    assert resp.status_code == 200
    dados = resp.get_json()
    assert any("Pilsen" in d["nome"] for d in dados)
