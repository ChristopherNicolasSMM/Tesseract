"""
tests/test_phase7b_rules_engine.py

Cobre o catálogo de regras, o model FieldRule, a tela de admin, e a
conexão real com os formulários gerados pelo CrudGen (data-rules +
rule_engine.js). O motor de validação em si (JS) não é testável via
pytest — coberto manualmente (ver BACKLOG.md); aqui testamos que o
HTML/atributos chegam corretos até o navegador.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.field_rule import FieldRule


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        admin = User(
            username="admin", email="admin@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


# ── Catálogo ─────────────────────────────────────────────────────────────────

def test_catalogo_tem_os_3_grupos():
    from core.rules_catalog import RULE_CATALOG
    groups = {g["group"] for g in RULE_CATALOG}
    assert groups == {"Validação", "Visibilidade", "Cálculo"}


def test_so_validacao_esta_conectada():
    from core.rules_catalog import RULE_CATALOG
    connected = {g["group"]: g["connected"] for g in RULE_CATALOG}
    assert connected["Validação"] is True
    assert connected["Visibilidade"] is False
    assert connected["Cálculo"] is False


def test_get_rule_def_encontra_regra_existente():
    from core.rules_catalog import get_rule_def
    rule = get_rule_def("obrigatorio")
    assert rule is not None
    assert rule["js_function"] == "required"


def test_get_rule_def_retorna_none_para_inexistente():
    from core.rules_catalog import get_rule_def
    assert get_rule_def("regra_que_nao_existe") is None


# ── Tela de admin ────────────────────────────────────────────────────────────

def test_tela_abre_e_lista_grupos(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/field-rules/")
    assert resp.status_code == 200
    assert "Validação".encode() in resp.data


def test_criar_regra_pela_tela(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/field-rules/",
        data={"entity_key": "yeast_strains", "field_name": "name", "rule_id": "obrigatorio", "params_json": "{}"},
        follow_redirects=True,
    )
    assert "anexada".encode() in resp.data

    with app.app_context():
        rule = FieldRule.query.filter_by(entity_key="yeast_strains", field_name="name").first()
        assert rule is not None
        assert rule.rule_id == "obrigatorio"


def test_criar_regra_com_id_inexistente_falha(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/field-rules/",
        data={"entity_key": "yeast_strains", "field_name": "name", "rule_id": "regra_fake", "params_json": "{}"},
        follow_redirects=True,
    )
    assert "não existe no catálogo".encode() in resp.data


def test_criar_regra_com_json_invalido_falha(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/field-rules/",
        data={"entity_key": "yeast_strains", "field_name": "name", "rule_id": "obrigatorio", "params_json": "{invalido"},
        follow_redirects=True,
    )
    assert "JSON válido".encode() in resp.data


def test_desativar_regra(app, client):
    _login_admin(app, client)
    with app.app_context():
        rule = FieldRule(entity_key="yeast_strains", field_name="name", rule_id="obrigatorio")
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id

    client.post(f"/admin/field-rules/{rule_id}/toggle")

    with app.app_context():
        assert FieldRule.query.get(rule_id).is_active is False


def test_remover_regra(app, client):
    _login_admin(app, client)
    with app.app_context():
        rule = FieldRule(entity_key="yeast_strains", field_name="name", rule_id="obrigatorio")
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id

    client.post(f"/admin/field-rules/{rule_id}/delete")

    with app.app_context():
        assert FieldRule.query.get(rule_id) is None


# ── Conexão real com os formulários do CrudGen ─────────────────────────────

def test_campo_sem_regra_nao_tem_data_rules(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/yeast-strains/")
    assert b'name="name" class="form-control"' in resp.data
    assert b"data-rules=" not in resp.data


def test_campo_com_regra_recebe_data_rules_correto(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/field-rules/",
        data={"entity_key": "yeast_strains", "field_name": "name", "rule_id": "obrigatorio", "params_json": '{"message": "Nome obrigatório!"}'},
    )

    resp = client.get("/brewstation/yeast-strains/")
    assert b"data-rules=" in resp.data
    assert b"required" in resp.data
    assert b"Nome obrigat" in resp.data


def test_regra_inativa_nao_aparece_no_formulario(app, client):
    _login_admin(app, client)
    with app.app_context():
        rule = FieldRule(entity_key="yeast_strains", field_name="name", rule_id="obrigatorio", is_active=False)
        db.session.add(rule)
        db.session.commit()

    resp = client.get("/brewstation/yeast-strains/")
    assert b"data-rules=" not in resp.data


def test_regra_de_outra_entidade_nao_aparece(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/field-rules/",
        data={"entity_key": "device_functions", "field_name": "name", "rule_id": "obrigatorio", "params_json": "{}"},
    )

    resp = client.get("/brewstation/yeast-strains/")
    assert b"data-rules=" not in resp.data


def test_rule_engine_js_incluido_na_pagina(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/yeast-strains/")
    assert b"rule_engine.js" in resp.data


def test_rule_engine_js_existe_e_tem_as_funcoes_de_validacao():
    """O arquivo estático existe e expõe as funções esperadas (smoke test de presença, não execução JS)."""
    with open("static/js/rule_engine.js", encoding="utf-8") as f:
        content = f.read()
    for fn in ("required", "minLength", "maxLength", "email", "cpf", "cnpj", "onlyNumbers", "minValue", "maxValue", "validDate"):
        assert f"{fn}:" in content
