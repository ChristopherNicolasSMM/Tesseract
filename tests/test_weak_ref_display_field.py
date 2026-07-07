"""
tests/test_weak_ref_display_field.py

Cobre a skill 11 (docs/skills/11-referencia-fraca-e-display-field.md):
- @display_field aplicado em Material + material_lookup.get_material()
  devolvendo a chave "display".
- @weak_ref resolvendo material_id em nome legível nas telas geradas
  de Malte (manage/detail) — 1 das 6 entidades cobertas basta pra
  provar o mecanismo genérico do controller/template do CrudGen.
- /api/options/materials — busca, paginação, e 400 pra plural
  desconhecido/sem @display_field.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from annotations import get_weak_refs
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


def _criar_material(nome="Malte Pilsen") -> Material:
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


def test_material_tem_display_field_nome(app):
    with app.app_context():
        assert getattr(Material, "_display_field", None) == "nome"


def test_get_material_devolve_chave_display(app):
    with app.app_context():
        material = _criar_material("Malte Pilsen")
        resolved = material_lookup.get_material(material.id)
        assert resolved["display"] == "Malte Pilsen"


def test_get_material_com_id_inexistente_devolve_none(app):
    with app.app_context():
        assert material_lookup.get_material(999999) is None


def test_malte_declara_weak_ref_material_id_com_options(app):
    with app.app_context():
        weak_refs = get_weak_refs(Malte)
        assert len(weak_refs) == 1
        assert weak_refs[0]["field"] == "material_id"
        assert weak_refs[0]["options"] == "materials"
        assert weak_refs[0]["resolver"] == "addons.addon_estoque.root.services.material_lookup.get_material"


def test_tela_de_listagem_de_maltes_mostra_nome_do_material_nao_o_id(app, client):
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material("Malte Pilsen Especial")
        db.session.add(Malte(material_id=material.id, cor_ebc=3.5, tipo="base"))
        db.session.commit()

    resp = client.get("/brewstation/maltes/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Malte Pilsen Especial" in html


def test_tela_de_detalhe_de_malte_mantem_id_cru_no_input_e_mostra_combo(app, client):
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material("Malte Viena")
        malte = Malte(material_id=material.id, cor_ebc=6.0, tipo="base")
        db.session.add(malte)
        db.session.commit()
        malte_id = malte.id
        material_id = material.id

    resp = client.get(f"/brewstation/maltes/{malte_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # input hidden continua com o id cru (nunca sobrescrito - senão quebra o save)
    assert f'value="{material_id}"' in html
    # combo de busca presente, com o source correto
    assert 'data-weakref-source="materials"' in html
    # nome resolvido aparece em algum lugar da tela (campo de busca pré-preenchido)
    assert "Malte Viena" in html


def test_material_apagado_nao_quebra_tela_cai_pro_id_cru(app, client):
    """Referência fraca sem garantia de integridade (skill 02) - se o
    Material for soft-deleted, a tela não pode quebrar, só perde a
    resolução de nome."""
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material("Malte Temporário")
        malte = Malte(material_id=material.id, cor_ebc=4.0, tipo="base")
        db.session.add(malte)
        db.session.commit()
        malte_id = malte.id

        material.is_deleted = True
        db.session.commit()

    resp = client.get(f"/brewstation/maltes/{malte_id}")
    assert resp.status_code == 200


def test_api_options_materials_busca_por_nome(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_material("Malte Cascade Especial")
        _criar_material("Lupulo Cascade")

    resp = client.get("/api/options/materials?search=Cascade")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 2
    assert all("Cascade" in r["text"] for r in data["results"])
    assert "pagination" in data and "more" in data["pagination"]


def test_api_options_plural_desconhecido_retorna_400(app, client):
    _login_admin(app, client)
    resp = client.get("/api/options/coisas_que_nao_existem")
    assert resp.status_code == 400


def test_api_options_exige_login(app, client):
    resp = client.get("/api/options/materials")
    assert resp.status_code in (302, 401)


def test_api_options_nao_expoe_model_sem_display_field(app, client):
    """User (Core) não declara @display_field - não pode virar fonte
    de options sem decisão explícita (skill 11, escopo restrito)."""
    _login_admin(app, client)
    resp = client.get("/api/options/users")
    assert resp.status_code == 400
