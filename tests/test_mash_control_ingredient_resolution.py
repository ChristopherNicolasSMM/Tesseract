"""
tests/test_mash_control_ingredient_resolution.py

Cobre feature_mash_control: MashRecipe estendida (origem_receita,
versao, unique name+versao), ingredient_resolution_service
(resolver_ingrediente, confirmar_mapeamento, criar_nova_versao).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.app_factory import create_app
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service as svc
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _criar_receita(nome="Sangue de Druida", origem="Manual", versao=1):
    receita = MashRecipe(name=nome, versao=versao, origem_receita=origem)
    db.session.add(receita)
    db.session.commit()
    return receita


def _criar_material(nome="Malte Pilsen"):
    origem_lookup = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(nome=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(nome="materia_prima").first()
    if not categoria:
        categoria = Categoria(nome="materia_prima")
        db.session.add(categoria)
        db.session.flush()

    material = Material(
        nome=nome, sku=nome.upper().replace(" ", "-"), unidade_medida="kg",
        origem_id=origem_lookup.id, tipo_produto_id=tipo_produto.id, categoria_id=categoria.id,
    )
    db.session.add(material)
    db.session.commit()
    return material


def test_nome_versao_e_unico(app):
    with app.app_context():
        _criar_receita(nome="IPA Tropical", versao=1)
        duplicada = MashRecipe(name="IPA Tropical", versao=1, origem_receita="Manual")
        db.session.add(duplicada)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_mesma_receita_versoes_diferentes_e_permitido(app):
    with app.app_context():
        _criar_receita(nome="IPA Tropical", versao=1)
        v2 = MashRecipe(name="IPA Tropical", versao=2, origem_receita="Manual")
        db.session.add(v2)
        db.session.commit()
        assert v2.id is not None


def test_origem_receita_invalida_e_rejeitada_pelo_service(app):
    with app.app_context():
        receita = _criar_receita()
        with pytest.raises(svc.OrigemInvalidaError):
            svc.resolver_ingrediente(receita.id, "OutraCoisa", "Malte Pilsen 5kg")


def test_resolver_ingrediente_sem_mapeamento_fica_pendente(app):
    with app.app_context():
        receita = _criar_receita()
        resultado = svc.resolver_ingrediente(
            receita.id, "BrewFather", "Pale Malt 2-Row", quantidade=5, unidade_medida="kg",
        )
        assert resultado["status_resolucao"] == "pendente_depara"
        assert resultado["material_id"] is None


def test_resolver_ingrediente_com_mapeamento_existente_resolve_direto(app):
    with app.app_context():
        material = _criar_material()
        receita = _criar_receita()

        db.session.add(IngredientMapping(
            origem_receita="BrewFather", descricao_origem="Pale Malt 2-Row", material_id=material.id,
        ))
        db.session.commit()

        resultado = svc.resolver_ingrediente(
            receita.id, "BrewFather", "Pale Malt 2-Row", quantidade=5, unidade_medida="kg",
        )
        assert resultado["status_resolucao"] == "resolvido"
        assert resultado["material_id"] == material.id


def test_confirmar_mapeamento_resolve_pendentes_da_mesma_origem_descricao(app):
    with app.app_context():
        material = _criar_material()
        receita1 = _criar_receita(nome="Receita A", origem="BrewFather")
        receita2 = _criar_receita(nome="Receita B", origem="BrewFather")

        svc.resolver_ingrediente(receita1.id, "BrewFather", "Pale Malt 2-Row", quantidade=5)
        svc.resolver_ingrediente(receita2.id, "BrewFather", "Pale Malt 2-Row", quantidade=3)

        resultado = svc.confirmar_mapeamento("BrewFather", "Pale Malt 2-Row", material.id)

        assert resultado["ingredientes_resolvidos"] == 2
        pendentes_restantes = RecipeIngredient.query.filter_by(status_resolucao="pendente_depara").count()
        assert pendentes_restantes == 0


def test_confirmar_mapeamento_material_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(ValueError):
            svc.confirmar_mapeamento("BrewFather", "Algo", 99999)


def test_criar_nova_versao_nao_altera_versao_anterior(app):
    with app.app_context():
        material = _criar_material()
        receita_v1 = _criar_receita(nome="Weiss Clássica", versao=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Trigo Maltado", quantidade=2)

        resultado = svc.criar_nova_versao(
            receita_v1.id, {"description": "ajuste de dry hop"}, observacao="Testando versionamento",
        )

        assert resultado["recipe"]["versao"] == 2
        assert resultado["recipe"]["name"] == "Weiss Clássica"
        assert resultado["recipe"]["description"] == "ajuste de dry hop"

        v1_recarregada = MashRecipe.query.filter_by(id=receita_v1.id).first()
        assert v1_recarregada.description != "ajuste de dry hop"


def test_criar_nova_versao_copia_ingredientes(app):
    with app.app_context():
        receita_v1 = _criar_receita(nome="Stout Imperial", versao=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Malte Chocolate", quantidade=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Lupulo Fuggle", quantidade=0.05)

        resultado = svc.criar_nova_versao(receita_v1.id, {})

        assert len(resultado["ingredientes"]) == 2
        nova_versao_id = resultado["recipe"]["id"]
        ingredientes_v2 = RecipeIngredient.query.filter_by(recipe_id=nova_versao_id).all()
        assert len(ingredientes_v2) == 2

        ingredientes_v1 = RecipeIngredient.query.filter_by(recipe_id=receita_v1.id).all()
        assert len(ingredientes_v1) == 2  # originais intactos


def test_criar_nova_versao_grava_snapshot_no_historico(app):
    with app.app_context():
        receita_v1 = _criar_receita(nome="Session IPA", versao=1)
        resultado = svc.criar_nova_versao(receita_v1.id, {}, observacao="Primeira revisão")

        historico = RecipeHistory.query.filter_by(recipe_id=resultado["recipe"]["id"]).first()
        assert historico is not None
        assert historico.observacao == "Primeira revisão"
        snapshot = historico.get_snapshot()
        assert snapshot["recipe"]["name"] == "Session IPA"
        assert snapshot["recipe"]["versao"] == 2


def test_criar_nova_versao_receita_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(svc.ReceitaNaoEncontradaError):
            svc.criar_nova_versao(99999, {})


def test_criar_nova_versao_rejeita_campo_nao_editavel(app):
    with app.app_context():
        receita_v1 = _criar_receita()
        with pytest.raises(ValueError):
            svc.criar_nova_versao(receita_v1.id, {"versao": 99})


# ── Regressão: tela de detalhe (view/render real, não só status code) ──
# Bug real: template usava 'record.xxx' mas o controller gerado pelo
# CrudGen passa a variável como 'item' - só um teste que RENDERIZA a
# página (não apenas GET no manage/list) pega isso.

@pytest.fixture
def client(app):
    return app.test_client()


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


def test_tela_de_detalhe_da_receita_renderiza_sem_erro(app, client):
    with app.app_context():
        receita = _criar_receita(nome="Receita para Teste de Detalhe")
        svc.resolver_ingrediente(receita.id, "Manual", "Malte Pilsen", quantidade=5, etapa="mostura")
        recipe_id = receita.id

    _login_admin(app, client)
    resp = client.get(f"/brewstation/mash-recipes/{recipe_id}", follow_redirects=True)

    assert resp.status_code == 200
    corpo = resp.data.decode("utf-8")
    assert "Receita para Teste de Detalhe" in corpo
    assert "Malte Pilsen" in corpo
