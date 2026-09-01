"""
tests/test_skill25_acoes_em_massa.py

Cobre a skill 25 (docs/skills/25-proposta-acoes-em-massa-padrao-crudgen.md):
- Apagar/Inativar em massa genéricos, gerados pelo CrudGen (service.py.j2
  + controller.py.j2 + manage.html.j2).
- Caminho LOCAL (MashRecipe.is_active) e caminho DELEGADO (Malte -> Material.ativo
  via @weak_ref(bulk_deactivate_service=...)).
- Regressão: os 4 botões extras de Materiais (Movimentar Estoque/Cotação/
  Pedido/Modificação em Massa) sobrevivem à regeneração de manage.html
  (migrados pra _acoes_em_massa_extra.html, hook de template novo).
- Correção do bug de resync do BrewFather (_importar_receita agora respeita
  is_deleted=False).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_brew_father.services import sync_service


def _ids_lookup_padrao(categoria_nome: str = "materia_prima_skill25") -> dict:
    """Mesmo raciocínio de tests/test_addon_estoque.py::_ids_lookup_padrao —
    resolve os 3 FKs obrigatórios de Material por descricao/codigo, não por
    `nome` (que não existe mais em Categoria/TipoProduto)."""
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(descricao=categoria_nome).first()
    if not categoria:
        categoria = Categoria(
            descricao=categoria_nome,
            codigo=categoria_nome.upper().replace(" ", "_"),
            tipo_produto_id=tipo_produto.id,
        )
        db.session.add(categoria)
        db.session.flush()
    return {"origem_id": origem.id, "tipo_produto_id": tipo_produto.id, "categoria_id": categoria.id}


def _criar_material(nome: str, ativo: bool = True) -> Material:
    material = Material(
        nome=nome, sku=f"SKU-{nome}".upper().replace(" ", "-"), ativo=ativo,
        **_ids_lookup_padrao(),
    )
    db.session.add(material)
    db.session.commit()
    return material


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


# ── Regressão: os 4 botões extras de Materiais sobrevivem à regeneração ──

def test_materials_manage_preserva_botoes_extras_e_ganha_genericos(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_material("Material Regressao Bulk Actions")

    resp = client.get("/estoque/materials", follow_redirects=True)
    assert resp.status_code == 200
    # Genérico novo (skill 25) — "selecionar todos" sempre aparece no
    # cabeçalho; checkbox por linha só existe se houver ao menos 1 item
    # (por isso criamos um Material acima antes de checar).
    assert b'crudgenCheckboxSelecionarTodos' in resp.data
    assert b'crudgen-checkbox-selecionar-item' in resp.data
    assert b'data-crudgen-acao-massa="apagar"' in resp.data
    assert b'data-crudgen-acao-massa="inativar"' in resp.data  # Material tem `ativo` local
    # Extras específicos de Material (migrados pra _acoes_em_massa_extra.html)
    assert b'data-acao-massa="movimentar"' in resp.data
    assert b'data-acao-massa="cotacao"' in resp.data
    assert b'data-acao-massa="pedido"' in resp.data
    assert b'data-acao-massa="modificar"' in resp.data
    assert b'js/estoque/materials-acoes-em-massa.js' in resp.data
    assert b'js/crudgen-bulk-actions.js' in resp.data


def test_materials_bulk_inactivate_local(app, client):
    """Material tem `ativo` próprio -> caminho LOCAL (não delega)."""
    _login_admin(app, client)
    with app.app_context():
        m1 = _criar_material("Material Bulk Inativar 1")
        m2 = _criar_material("Material Bulk Inativar 2")
        ids = [m1.id, m2.id]

    resp = client.post("/estoque/materials/bulk-inactivate", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        assert db.session.get(Material, ids[0]).ativo is False
        assert db.session.get(Material, ids[1]).ativo is False


# ── Caminho LOCAL — MashRecipe (is_active, não `ativo`) ──

def test_mash_recipes_bulk_trash_e_bulk_inactivate(app, client):
    _login_admin(app, client)
    with app.app_context():
        r1 = MashRecipe(name="Receita Bulk 1", versao=1, origem_receita="Manual")
        r2 = MashRecipe(name="Receita Bulk 2", versao=1, origem_receita="Manual")
        db.session.add_all([r1, r2])
        db.session.commit()
        ids = [r1.id, r2.id]

    resp = client.post("/brewstation/mash-recipes/bulk-inactivate", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    with app.app_context():
        assert db.session.get(MashRecipe, ids[0]).is_active is False
        assert db.session.get(MashRecipe, ids[1]).is_active is False

    resp = client.post("/brewstation/mash-recipes/bulk-trash", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    with app.app_context():
        assert db.session.get(MashRecipe, ids[0]).is_deleted is True
        assert db.session.get(MashRecipe, ids[1]).is_deleted is True


# ── Caminho DELEGADO — Malte não tem `ativo`, delega pro Material ──

def test_maltes_bulk_inactivate_delega_para_material_ativo(app, client):
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material("Malte Pilsen Bulk Delegado")
        malte = Malte(material_id=material.id, cor_ebc=3.5, tipo="base")
        db.session.add(malte)
        db.session.commit()
        malte_id, material_id = malte.id, material.id

    resp = client.post("/brewstation/maltes/bulk-inactivate", json={"ids": [malte_id]})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        # Malte em si não tem `ativo` — quem muda é o Material vinculado.
        assert not hasattr(Malte, "ativo")
        assert db.session.get(Material, material_id).ativo is False


def test_maltes_bulk_trash_e_local_nao_delega(app, client):
    """Apagar em massa é sempre local (is_deleted do próprio Malte) —
    só Inativar delega. Material NÃO deve ser afetado aqui."""
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material("Malte Pilsen Bulk Trash")
        malte = Malte(material_id=material.id, cor_ebc=3.5, tipo="base")
        db.session.add(malte)
        db.session.commit()
        malte_id, material_id = malte.id, material.id

    resp = client.post("/brewstation/maltes/bulk-trash", json={"ids": [malte_id]})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        assert db.session.get(Malte, malte_id).is_deleted is True
        assert db.session.get(Material, material_id).ativo is True  # intocado


# ── Correção do bug de resync (skill 25, seção 3.1) ──

def test_sync_reimporta_receita_apagada(app):
    """Antes da correção, _importar_receita achava a receita apagada e
    devolvia ela sem recriar nada — apagar pra forçar resync não tinha
    efeito. Agora, com is_deleted=False no filtro, uma segunda chamada
    pro mesmo origem_receita_id cria uma NOVA receita."""
    with app.app_context():
        receita_externa = {"id": "bf-resync-123", "name": "IPA Resync Teste"}

        primeira = sync_service._importar_receita(receita_externa)
        assert primeira.origem_receita_id == "bf-resync-123"

        primeira.is_deleted = True
        db.session.commit()

        segunda = sync_service._importar_receita(receita_externa)
        assert segunda.id != primeira.id
        assert segunda.is_deleted is False
        assert segunda.origem_receita_id == "bf-resync-123"
        assert segunda.versao == primeira.versao + 1  # evita colidir com UniqueConstraint(name, versao)
