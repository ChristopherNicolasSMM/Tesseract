"""
tests/test_feature_envase.py

Cobre feature_envase: Envase/ItemEnvase, FK real pra BrewSession
(mesmo Addon), referência fraca pra Material (cross-Addon), e o fluxo
de baixa síncrona de estoque via envase_estoque_service.registrar_envase().
"""
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.services import estoque_service as material_movement_service
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
from addons.addon_brewstation.features.feature_envase.services import envase_estoque_service as svc


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _criar_lote(nome="IPA Tropical"):
    receita = MashRecipe(name=nome, versao=1, origem_receita="Manual")
    db.session.add(receita)
    db.session.commit()

    lote = BrewSession(name=f"Sessão {nome}", recipe_id=receita.id, status="concluida")
    db.session.add(lote)
    db.session.commit()
    return lote


def _criar_material_com_estoque(nome="Garrafa 600ml", quantidade_inicial=100):
    material = Material(nome=nome, categoria="embalagem", unidade_medida="un")
    db.session.add(material)
    db.session.commit()
    material_movement_service.registrar_movimentacao(material.id, "entrada", quantidade_inicial, custo_unitario=1.5)
    return material


def test_registrar_envase_cria_envase_e_itens(app):
    with app.app_context():
        lote = _criar_lote()
        material = _criar_material_com_estoque()

        resultado = svc.registrar_envase(
            lote.id, [{"material_id": material.id, "quantidade": 24}],
            quantidade_litros=18, tipo_envase="garrafa",
        )

        assert resultado["envase"]["lote_id"] == lote.id
        assert len(resultado["itens"]) == 1
        assert resultado["itens"][0]["material_id"] == material.id


def test_registrar_envase_da_baixa_no_estoque(app):
    with app.app_context():
        lote = _criar_lote()
        material = _criar_material_com_estoque(quantidade_inicial=100)

        svc.registrar_envase(lote.id, [{"material_id": material.id, "quantidade": 24}])

        saldo = material_movement_service.consultar_saldo(material.id)
        assert saldo["quantidade_atual"] == 76


def test_registrar_envase_lote_inexistente_levanta_erro(app):
    with app.app_context():
        material = _criar_material_com_estoque()
        with pytest.raises(svc.LoteNaoEncontradoError):
            svc.registrar_envase(99999, [{"material_id": material.id, "quantidade": 1}])


def test_registrar_envase_material_inexistente_nao_grava_nada(app):
    with app.app_context():
        lote = _criar_lote()
        with pytest.raises(svc.MaterialNaoEncontradoError):
            svc.registrar_envase(lote.id, [{"material_id": 99999, "quantidade": 1}])

        assert Envase.query.count() == 0
        assert ItemEnvase.query.count() == 0


def test_registrar_envase_multiplos_itens(app):
    with app.app_context():
        lote = _criar_lote()
        garrafa = _criar_material_com_estoque(nome="Garrafa 600ml", quantidade_inicial=50)
        tampinha = _criar_material_com_estoque(nome="Tampinha", quantidade_inicial=200)

        resultado = svc.registrar_envase(lote.id, [
            {"material_id": garrafa.id, "quantidade": 24},
            {"material_id": tampinha.id, "quantidade": 24},
        ])

        assert len(resultado["itens"]) == 2
        assert material_movement_service.consultar_saldo(garrafa.id)["quantidade_atual"] == 26
        assert material_movement_service.consultar_saldo(tampinha.id)["quantidade_atual"] == 176


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


@pytest.mark.parametrize("rota", [
    "/brewstation/envases",
    "/brewstation/item-envases",
])
def test_telas_de_listagem_nao_estouram_erro(app, client, rota):
    _login_admin(app, client)
    resp = client.get(rota, follow_redirects=True)
    assert resp.status_code == 200
