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


def test_grupo_controle_de_mostura_tem_5_filhos_diretos(app):
    """
    [ATUALIZADO — reorganização de menu em conversa] Controle de
    Mostura tinha 18 transações soltas no mesmo nível — virou 4
    sub-grupos (Receitas/Planta & Sessão/Automação, mais Sessões dentro
    de Planta & Sessão) + os 2 itens de Dashboard (que ficam, mas saem
    do menu via is_active=False manual, não por código — skill 10, sync
    nunca mexe em is_active). O De-Para de Ingredientes saiu daqui e
    foi para TX_GROUP_INGREDIENTES.
    """
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_MASH_CONTROL").first()
        assert folder is not None
        filhos_diretos = {t.code for t in Transaction.query.filter_by(parent_id=folder.id).all()}
        assert filhos_diretos == {
            "TX_GROUP_MASH_RECIPES",
            "TX_GROUP_MASH_PLANT_SESSION",
            "TX_GROUP_MASH_AUTOMATION",
            "TX_DASHBOARD_LAYOUTS",
            "TX_DASHBOARD_WIDGETS",
        }


def test_grupo_receitas_tem_6_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_MASH_RECIPES").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 6


def test_grupo_planta_e_sessao_tem_3_filhos_diretos_mais_subgrupo_sessoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_MASH_PLANT_SESSION").first()
        assert folder is not None
        filhos = {t.code for t in Transaction.query.filter_by(parent_id=folder.id).all()}
        assert filhos == {
            "TX_BREW_PLANTS", "TX_BREW_PLANT_VESSELS", "TX_BREW_PLANT_MAPPINGS",
            "TX_GROUP_MASH_SESSIONS",
        }

        sessoes = Transaction.query.filter_by(code="TX_GROUP_MASH_SESSIONS").first()
        assert sessoes is not None
        assert sessoes.parent_id == folder.id
        filhos_sessoes = {t.code for t in Transaction.query.filter_by(parent_id=sessoes.id).all()}
        # 4 originais + TX_DASHBOARD_VIEW (dashboard de verdade, implementado
        # nesta conversa — "entra aqui quando o sistema de dashboard existir")
        assert filhos_sessoes == {
            "TX_BREW_SESSIONS", "TX_BREW_SESSION_STEPS", "TX_BREW_SESSION_LOGS",
            "TX_BREW_SESSION_ALARMS", "TX_DASHBOARD_VIEW",
        }


def test_grupo_automacao_tem_2_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_MASH_AUTOMATION").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 2


def test_de_para_de_ingredientes_agora_fica_em_ingredientes(app):
    with app.app_context():
        de_para = Transaction.query.filter_by(code="TX_INGREDIENT_MAPPINGS").first()
        assert de_para is not None
        parent = Transaction.query.get(de_para.parent_id)
        assert parent.code == "TX_GROUP_INGREDIENTES"


def test_grupo_ingredientes_tem_4_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_INGREDIENTES").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 4


def test_grupo_dispositivos_iot_tem_4_transacoes(app):
    with app.app_context():
        folder = Transaction.query.filter_by(code="TX_GROUP_DEVICE_MANAGER").first()
        assert folder is not None
        count = Transaction.query.filter_by(parent_id=folder.id).count()
        assert count == 4


def test_grupo_brewstation_generico_agora_e_a_pasta_raiz_do_addon(app):
    """
    [ATUALIZADO 2026-07-07, skill 10 seção 7.1] Este teste antes
    afirmava o oposto: que NENHUMA pasta "BrewStation" deveria existir
    (`route IS NULL` = pasta). Isso era correto na época em que foi
    escrito — `Transaction.group` ainda era string plana (skill 10 não
    existia), e havia um bucket genérico "BrewStation" duplicando as
    transações que também apareciam soltas, sem nenhuma sub-pasta por
    Feature. A correção da época foi remover esse bucket genérico em
    favor de uma pasta por Feature (`TX_GROUP_YEAST_BANK`, etc.).

    Com a árvore de profundidade arbitrária (skill 10, `parent_id`),
    esse dilema "genérico OU por Feature" deixou de existir — agora é
    "genérico E por Feature", em hierarquia: uma única pasta raiz
    `TX_GROUP_BREWSTATION` (label "BrewStation") contendo as 5 pastas
    de Feature como filhas, resolvendo o problema original (nenhuma
    Feature solta na raiz do menu) sem reintroduzir a duplicação
    original (cada transação aparece uma vez só, no lugar certo da
    árvore). Ver `tests/test_menu_hierarquico.py::test_tx_group_brewstation_agrupa_as_5_features`
    para a cobertura completa da hierarquia.
    """
    with app.app_context():
        pastas_brewstation = Transaction.query.filter_by(label="BrewStation").filter(Transaction.route.is_(None)).all()
        assert len(pastas_brewstation) == 1  # exatamente uma - a raiz, não mais nem menos
        assert pastas_brewstation[0].code == "TX_GROUP_BREWSTATION"
        assert pastas_brewstation[0].parent_id is None


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
