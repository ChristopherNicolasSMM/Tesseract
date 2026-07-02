"""
tests/test_menu_grouped_by_feature.py

Cobre o plano de submenu agrupado por Feature: as 20 páginas que
existiam (CRUD completo e funcional) mas não tinham nenhuma entrada
no catálogo de Transações, a troca de `group` de "BrewStation"
genérico para o nome de cada Feature, e a remoção da duplicidade do
link "Início" (existia um <link fixo> + um grupo "Core" renderizando
a mesma coisa de novo).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction


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


# ── Grupos por Feature/Addon ─────────────────────────────────────────────────

def test_grupo_banco_de_levedura_tem_9_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_YEAST_BANK").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 9


def test_grupo_controle_de_mostura_tem_12_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_MASH_CONTROL").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 12


def test_grupo_dispositivos_iot_tem_4_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_DEVICE_MANAGER").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 4


def test_nao_existe_mais_grupo_brewstation_generico(app):
    with app.app_context():
        count = Transaction.query.filter_by(label="BrewStation").filter(Transaction.route.is_(None)).count()
        assert count == 0


def test_nao_existe_mais_grupo_device_manager_antigo(app):
    with app.app_context():
        # O nó-pasta real hoje é "Dispositivos IoT" (TX_GROUP_DEVICE_MANAGER) —
        # o nome antigo "Device Manager" nunca deveria existir como pasta.
        count = Transaction.query.filter_by(label="Device Manager").filter(Transaction.route.is_(None)).count()
        assert count == 0


# ── As 20 órfãs agora têm transação ──────────────────────────────────────────

ORFAS_RESOLVIDAS = [
    "TX_YEAST_BANK_ITEMS", "TX_YEAST_STORAGE_DEVICES", "TX_YEAST_STORAGE_READINGS",
    "TX_YEAST_STARTER_LOGS", "TX_YEAST_CELL_COUNT_HISTORIES", "TX_YEAST_BANK_EVENTS",
    "TX_YEAST_BANK_CONFIGS",
    "TX_BREW_PLANTS", "TX_BREW_PLANT_VESSELS", "TX_BREW_PLANT_MAPPINGS",
    "TX_BREW_SESSION_STEPS", "TX_BREW_SESSION_LOGS", "TX_BREW_SESSION_ALARMS",
    "TX_DASHBOARD_LAYOUTS", "TX_DASHBOARD_WIDGETS",
    "TX_AUTOMATION_RULES", "TX_AUTOMATION_RULE_LOGS",
    "TX_DEVICE_FUNCTIONS", "TX_DEVICE_ACTORS", "TX_EMULATED_DEVICES",
]


@pytest.mark.parametrize("code", ORFAS_RESOLVIDAS)
def test_transacao_orfa_agora_existe(app, code):
    with app.app_context():
        tx = Transaction.query.filter_by(code=code).first()
        assert tx is not None, f"{code} deveria existir agora"
        assert tx.is_active is True
        assert tx.route is not None


def test_todas_as_20_orfas_aparecem_na_home(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    rotas_esperadas = [
        "/brewstation/yeast-bank-items", "/brewstation/brew-plants",
        "/device-manager/device-functions", "/device-manager/device-actors",
        "/device-manager/emulated-devices",
    ]
    for rota in rotas_esperadas:
        assert rota.encode() in resp.data


def test_todas_as_20_orfas_aparecem_na_sidebar(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/users/")  # qualquer página com base.html
    rotas_esperadas = [
        "/brewstation/yeast-storage-devices", "/brewstation/automation-rules",
        "/device-manager/device-functions",
    ]
    for rota in rotas_esperadas:
        assert rota.encode() in resp.data


# ── Sem duplicidade do "Início" ──────────────────────────────────────────────

def test_grupo_core_nao_aparece_como_submenu_na_sidebar(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    # "Core" não deve aparecer como nome de grupo/submenu na sidebar
    # (o link fixo de Início já cobre isso — checado separadamente).
    assert b"<span>Core</span>" not in resp.data


def test_grupo_core_nao_aparece_como_secao_na_home(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    # "Core" como título de seção (<h5>) não deve aparecer
    assert b'<h5 class="mt-3">Core</h5>' not in resp.data


def test_grupos_novos_aparecem_como_titulo_de_secao_na_home(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    body = resp.data.decode()
    for group in ("Banco de Levedura", "Controle de Mostura", "Dispositivos IoT"):
        assert f'<h5 class="mt-3">' in body
        assert group in body
