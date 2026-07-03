"""
tests/test_feature_brew_father.py

Cobre feature_brew_father: sync_service.sync_recipes() usando o
cliente MOCK (brewfather_client.py) — sem chamada HTTP real. Confirma
que a receita importada vira MashRecipe com origem_receita="BrewFather",
ingredientes viram RecipeIngredient (resolvidos ou pendentes conforme
IngredientMapping existente), e BrewFatherSync registra o resultado.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_brewstation.features.feature_brew_father.services import sync_service


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_sync_recipes_importa_as_duas_receitas_mock(app):
    with app.app_context():
        resultado = sync_service.sync_recipes()

        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 2
        assert resultado["quantidade_erro"] == 0

        receitas = MashRecipe.query.filter_by(origem_receita="BrewFather").all()
        assert len(receitas) == 2
        nomes = {r.name for r in receitas}
        assert nomes == {"Sangue de Druida", "Session IPA Tropical"}


def test_sync_recipes_grava_origem_receita_id(app):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        assert receita is not None
        assert receita.name == "Sangue de Druida"
        assert receita.origem_receita == "BrewFather"


def test_sync_recipes_cria_ingredientes_pendentes_sem_mapeamento(app):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        ingredientes = RecipeIngredient.query.filter_by(recipe_id=receita.id).all()

        assert len(ingredientes) == 3
        assert all(i.status_resolucao == "pendente_depara" for i in ingredientes)
        assert all(i.material_id is None for i in ingredientes)


def test_sync_recipes_resolve_ingrediente_com_mapeamento_previo(app):
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


def test_sync_recipes_nao_reimporta_receita_ja_sincronizada(app):
    with app.app_context():
        sync_service.sync_recipes()
        sync_service.sync_recipes()

        receitas = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").all()
        assert len(receitas) == 1  # limitação documentada: não re-sincroniza


def test_sync_recipes_grava_log_de_sincronizacao(app):
    with app.app_context():
        sync_service.sync_recipes()

        log = BrewFatherSync.query.filter_by(tipo_sync="recipes").first()
        assert log is not None
        assert log.status == "sucesso"
        assert log.finalizado_em is not None
        assert log.raw_data is not None


def test_etapa_traduzida_de_use_ingles_para_portugues(app):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        lupulo = RecipeIngredient.query.filter_by(recipe_id=receita.id, descricao_origem="Cascade").first()

        assert lupulo.etapa == "fervura"
        assert lupulo.tempo_adicao_min == 60


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
