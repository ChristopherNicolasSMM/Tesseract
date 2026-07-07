"""
tests/test_feature_ingredientes.py

Cobre feature_ingredientes: Malte/Lupulo/Levedura, referência fraca
(material_id, SEM FK) para addon_estoque.Material, unicidade 1
Material : 1 spec por tipo.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
from addons.addon_brewstation.features.feature_ingredientes.model.levedura import Levedura


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _criar_material(nome="Malte Pilsen"):
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(nome=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(nome="materia_prima").first()
    if not categoria:
        categoria = Categoria(nome="materia_prima")
        db.session.add(categoria)
        db.session.flush()

    material = Material(
        nome=nome, sku=nome.upper().replace(" ", "-"), unidade_medida="kg",
        origem_id=origem.id, tipo_produto_id=tipo_produto.id, categoria_id=categoria.id,
    )
    db.session.add(material)
    db.session.commit()
    return material


def test_cria_malte_vinculado_a_material(app):
    with app.app_context():
        material = _criar_material(nome="Malte Pilsen")
        malte = Malte(material_id=material.id, cor_ebc=3.5, poder_diastatico=110, rendimento=80, tipo="base")
        db.session.add(malte)
        db.session.commit()

        assert malte.id is not None
        assert malte.material_id == material.id
        assert malte.is_deleted is False


def test_malte_material_id_e_unico(app):
    with app.app_context():
        material = _criar_material(nome="Malte Munich")
        db.session.add(Malte(material_id=material.id, tipo="especial"))
        db.session.commit()

        duplicado = Malte(material_id=material.id, tipo="base")
        db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_cria_lupulo_vinculado_a_material(app):
    with app.app_context():
        material = _criar_material(nome="Lúpulo Cascade")
        lupulo = Lupulo(material_id=material.id, alpha_acidos=5.5, beta_acidos=6.0, formato="pellet", origem="EUA")
        db.session.add(lupulo)
        db.session.commit()

        assert lupulo.id is not None
        assert lupulo.formato == "pellet"


def test_cria_levedura_vinculada_a_material(app):
    with app.app_context():
        material = _criar_material(nome="Levedura US-05")
        levedura = Levedura(material_id=material.id, atenuacao=75, temp_fermentacao=18, floculacao="media", formato="seca")
        db.session.add(levedura)
        db.session.commit()

        assert levedura.id is not None
        assert levedura.floculacao == "media"


def test_material_id_e_referencia_fraca_sem_fk(app):
    with app.app_context():
        # material_id aponta pra um id que nao existe em Material - nao
        # deve estourar erro de integridade de banco, porque nao ha FK
        # real (skill 02: referencia fraca cross-Addon).
        malte = Malte(material_id=99999, tipo="base")
        db.session.add(malte)
        db.session.commit()
        assert malte.id is not None


# ── Regressão: telas de listagem não podem estourar AttributeError ──
# (mesma classe de bug já vista em addon_estoque - checagem preventiva
# aqui, já que as 3 tabelas nasceram com is_deleted desta vez)

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
    "/brewstation/maltes",
    "/brewstation/lupulos",
    "/brewstation/leveduras",
])
def test_telas_de_listagem_nao_estouram_erro(app, client, rota):
    _login_admin(app, client)
    resp = client.get(rota, follow_redirects=True)
    assert resp.status_code == 200
