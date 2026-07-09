"""
tests/test_menu_hierarquico.py

Cobre a skill 10 (menu hierárquico): Transaction.is_folder,
parent_id/order_index, e a tela admin_transactions.py com seletor de
pai em vez de texto livre de grupo.
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
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Model ────────────────────────────────────────────────────────────────

def test_is_folder_true_quando_route_none(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        assert tx.is_folder is True


def test_is_folder_false_quando_tem_rota(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_HOME").first()
        assert tx.is_folder is False


def test_parent_relationship_funciona(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_ROLES").first()
        assert tx.parent is not None
        assert tx.parent.code == "TX_GROUP_ADMIN"
        assert tx in tx.parent.children


def test_catalogo_core_nao_tem_mais_coluna_group():
    """Não-regressão: garante que ninguém reintroduziu `group` no model."""
    assert not hasattr(Transaction, "group")


# ── admin_transactions.py: seletor de pai ───────────────────────────────

def test_criar_transacao_manual_com_pai(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        parent_id = admin_folder.id

    resp = client.post(
        "/admin/transactions/",
        data={
            "code": "TX_MEU_LINK", "label": "Meu Link",
            "parent_id": str(parent_id), "route": "/meu-link",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_MEU_LINK").first()
        assert tx is not None
        assert tx.parent.code == "TX_GROUP_ADMIN"


def test_criar_transacao_manual_sem_rota_vira_pasta(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/transactions/",
        data={"code": "TX_MINHA_PASTA", "label": "Minha Pasta"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_MINHA_PASTA").first()
        assert tx is not None
        assert tx.is_folder is True


def test_nova_pasta_manual_fica_disponivel_como_pai(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/transactions/",
        data={"code": "TX_PASTA_NOVA", "label": "Pasta Nova"},
        follow_redirects=True,
    )
    with app.app_context():
        pasta = Transaction.query.filter_by(code="TX_PASTA_NOVA").first()
        pasta_id = pasta.id

    resp = client.post(
        "/admin/transactions/",
        data={
            "code": "TX_FILHO_DA_PASTA_NOVA", "label": "Filho",
            "parent_id": str(pasta_id), "route": "/filho",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        filho = Transaction.query.filter_by(code="TX_FILHO_DA_PASTA_NOVA").first()
        assert filho.parent_id == pasta_id


def test_excluir_pasta_com_filhos_falha(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/transactions/",
        data={"code": "TX_PASTA_COM_FILHO", "label": "Pasta Com Filho"},
        follow_redirects=True,
    )
    with app.app_context():
        pasta = Transaction.query.filter_by(code="TX_PASTA_COM_FILHO").first()
        pasta_id = pasta.id

    client.post(
        "/admin/transactions/",
        data={
            "code": "TX_FILHO_X", "label": "Filho X",
            "parent_id": str(pasta_id), "route": "/filho-x",
        },
        follow_redirects=True,
    )

    resp = client.post(f"/admin/transactions/{pasta_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Transaction.query.get(pasta_id) is not None  # não foi excluída


def test_transacao_de_codigo_nao_permite_editar_pai(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_HOME").first()
        tx_id = tx.id
        original_parent_id = tx.parent_id

    resp = client.post(
        f"/admin/transactions/{tx_id}",
        data={"label": "Início Hackeado", "route": "/", "parent_id": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        tx = Transaction.query.get(tx_id)
        assert tx.label == "Início"  # não mudou — é code-sourced
        assert tx.parent_id == original_parent_id


def test_tela_manage_carrega_com_breadcrumb(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/transactions/?q=TX_ADMIN_ROLES")
    assert resp.status_code == 200
    assert "Admin &gt; Papéis e Permissões".encode() in resp.data


# ── Estrutura real: promote/demote (skill 10 §8.1) ──────────────────────

def _create_manual(client, code, label, parent_id=None, route=None):
    data = {"code": code, "label": label}
    if parent_id is not None:
        data["parent_id"] = str(parent_id)
    if route is not None:
        data["route"] = route
    client.post("/admin/transactions/", data=data, follow_redirects=True)


def test_promote_transacao_manual_vira_irma_do_proprio_pai(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        admin_id = admin_folder.id

    _create_manual(client, "TX_PASTA_PROMOTE", "Pasta Promote", parent_id=admin_id)
    with app.app_context():
        pasta = Transaction.query.filter_by(code="TX_PASTA_PROMOTE").first()
        pasta_id = pasta.id

    _create_manual(client, "TX_FILHO_PROMOTE", "Filho Promote", parent_id=pasta_id, route="/filho-promote")
    with app.app_context():
        filho = Transaction.query.filter_by(code="TX_FILHO_PROMOTE").first()
        filho_id = filho.id

    resp = client.post(f"/admin/transactions/{filho_id}/promote", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        filho = Transaction.query.get(filho_id)
        assert filho.parent_id == admin_id  # virou irmão da própria pasta-mãe


def test_promote_item_na_raiz_falha(app, client):
    _login_admin(app, client)
    _create_manual(client, "TX_RAIZ_PROMOTE", "Raiz Promote", route="/raiz-promote")
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_RAIZ_PROMOTE").first()
        tx_id = tx.id

    resp = client.post(f"/admin/transactions/{tx_id}/promote", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Transaction.query.get(tx_id).parent_id is None  # não mudou


def test_demote_transacao_manual_vira_filha_do_irmao_anterior(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        admin_id = admin_folder.id

    # Dois itens manuais, sem rota (pastas), irmãos sob Admin.
    _create_manual(client, "TX_PASTA_A", "Pasta A", parent_id=admin_id)
    _create_manual(client, "TX_PASTA_B", "Pasta B", parent_id=admin_id)
    with app.app_context():
        pasta_a = Transaction.query.filter_by(code="TX_PASTA_A").first()
        pasta_b = Transaction.query.filter_by(code="TX_PASTA_B").first()
        pasta_a_id, pasta_b_id = pasta_a.id, pasta_b.id

    resp = client.post(f"/admin/transactions/{pasta_b_id}/demote", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        pasta_b = Transaction.query.get(pasta_b_id)
        assert pasta_b.parent_id == pasta_a_id


def test_demote_para_dentro_de_item_com_rota_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        admin_id = admin_folder.id

    _create_manual(client, "TX_COM_ROTA", "Com Rota", parent_id=admin_id, route="/com-rota")
    _create_manual(client, "TX_DEPOIS_DA_ROTA", "Depois Da Rota", parent_id=admin_id, route="/depois-da-rota")
    with app.app_context():
        depois = Transaction.query.filter_by(code="TX_DEPOIS_DA_ROTA").first()
        depois_id = depois.id
        original_parent_id = depois.parent_id

    resp = client.post(f"/admin/transactions/{depois_id}/demote", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        depois = Transaction.query.get(depois_id)
        assert depois.parent_id == original_parent_id  # não mudou — irmão anterior não é pasta


def test_demote_primeiro_item_da_lista_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        admin_id = admin_folder.id
        siblings = Transaction.query.filter_by(parent_id=admin_id).order_by(Transaction.order_index).all()
        first_id = siblings[0].id
        original_parent_id = siblings[0].parent_id

    resp = client.post(f"/admin/transactions/{first_id}/demote", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Transaction.query.get(first_id).parent_id == original_parent_id


def test_promote_demote_bloqueado_para_transacao_de_codigo(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_ROLES").first()
        tx_id = tx.id
        original_parent_id = tx.parent_id

    client.post(f"/admin/transactions/{tx_id}/promote", follow_redirects=True)
    client.post(f"/admin/transactions/{tx_id}/demote", follow_redirects=True)
    with app.app_context():
        assert Transaction.query.get(tx_id).parent_id == original_parent_id


# ── Exibição: reparenting virtual via order_overrides (skill 10 §8.1) ──────

def test_reparenting_virtual_nao_toca_parent_id_real(app, client):
    """
    order_overrides colocando um code sob outro pai muda só a ÁRVORE
    EXIBIDA (controller/core/pages.py) — nunca Transaction.parent_id.
    """
    with app.app_context():
        from services.core import menu_preference_service as svc
        roles = Transaction.query.filter_by(code="TX_ADMIN_ROLES").first()
        original_parent_id = roles.parent_id

        svc.set_global_defaults(order_overrides={
            "TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO": ["TX_ADMIN_ROLES"],
        })

    _login_admin(app, client)
    resp = client.get("/")
    assert resp.status_code == 200

    with app.app_context():
        # parent_id real não mudou.
        assert Transaction.query.filter_by(code="TX_ADMIN_ROLES").first().parent_id == original_parent_id


# ── Revisão 2026-07-07 (skill 10, seções 5.1/5.2/7.1) ──────────────────────

def test_tx_group_brewstation_agrupa_as_5_features(app):
    """
    Antes desta correção, as 5 Features de addon_brewstation
    declaravam parent_code=None e apareciam soltas na raiz do menu.
    """
    with app.app_context():
        grupo = Transaction.query.filter_by(code="TX_GROUP_BREWSTATION").first()
        assert grupo is not None
        assert grupo.parent_id is None

        for code in [
            "TX_GROUP_YEAST_BANK", "TX_GROUP_MASH_CONTROL", "TX_GROUP_INGREDIENTES",
            "TX_GROUP_ENVASE", "TX_GROUP_BREW_FATHER",
        ]:
            feature_group = Transaction.query.filter_by(code=code).first()
            assert feature_group.parent_id == grupo.id, f"{code} não aponta pro grupo do Addon"


def test_accordion_data_bs_parent_aponta_pro_container_imediato(app, client):
    """
    Bug real confirmado (não hipótese): antes da correção, TODO <ul>
    aninhado usava data-bs-parent="#sidebar-nav" fixo, fazendo o
    Bootstrap tratar a árvore inteira como um único accordion — abrir
    um nó em qualquer profundidade fechava qualquer outro nó aberto em
    qualquer outro lugar da árvore.

    TX_GROUP_BREWSTATION (nível 0) > TX_GROUP_YEAST_BANK (nível 1) é o
    cenário exato que expõe o bug: o node de nível 1 precisa apontar
    pro node de nível 0 ("#node-TX_GROUP_BREWSTATION"), não pro
    #sidebar-nav global.
    """
    _login_admin(app, client)
    resp = client.get("/")
    html = resp.data.decode("utf-8")

    # Nível 0 (filho direto do sidebar) - correto apontar pro sidebar-nav.
    assert (
        'id="node-TX_GROUP_BREWSTATION"' in html
        and 'data-bs-parent="#sidebar-nav"' in html
    )
    # Nível 1 (filho de TX_GROUP_BREWSTATION) - deve apontar pro pai
    # imediato, NUNCA pro #sidebar-nav global (bug corrigido).
    import re
    m = re.search(r'<ul id="node-TX_GROUP_YEAST_BANK"[^>]*data-bs-parent="([^"]+)"', html)
    assert m is not None
    assert m.group(1) == "#node-TX_GROUP_BREWSTATION"


def test_icon_max_depth_default_mostra_icone_em_todo_nivel(app, client):
    """Default (-1, sem system_config setado) = sem corte, comportamento visual inalterado."""
    _login_admin(app, client)
    resp = client.get("/")
    html = resp.data.decode("utf-8")

    idx = html.find('data-menu-node="TX_GROUP_YEAST_BANK"')
    trecho = html[idx:idx + 300]
    assert "<i class=" in trecho  # ícone presente por padrão


def test_icon_max_depth_configurado_esconde_icone_a_partir_do_nivel(app, client):
    """core.menu.icon_max_depth=1: nível 0 mostra ícone, nível 1+ não."""
    with app.app_context():
        from core.db import db
        from model.core.system_config import SystemConfig
        db.session.add(SystemConfig(key="core.menu.icon_max_depth", value="1", value_type="int"))
        db.session.commit()

    _login_admin(app, client)
    resp = client.get("/")
    html = resp.data.decode("utf-8")

    idx0 = html.find('data-menu-node="TX_GROUP_BREWSTATION"')
    trecho0 = html[idx0:idx0 + 300]
    assert "<i class=" in trecho0  # nível 0 continua com ícone

    idx1 = html.find('data-menu-node="TX_GROUP_YEAST_BANK"')
    trecho1_ate_span = html[idx1:html.find("<span>", idx1)]
    assert "<i class=" not in trecho1_ate_span  # nível 1 sem ícone (só o chevron depois do label)


# ── Tela /admin/menu-settings expõe e salva icon_max_depth (BACKLOG.md) ─────
# Achado real: a configuração core.menu.icon_max_depth já existia e
# funcionava (testes acima), mas só era alterável direto no banco —
# sem controle nenhum na tela de admin.

def test_tela_menu_settings_exibe_select_de_icon_max_depth(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/menu-settings/")
    assert resp.status_code == 200
    assert b'name="icon_max_depth"' in resp.data
    assert b"Sempre (todos os n\xc3\xadveis)" in resp.data


def test_salvar_icon_max_depth_pela_tela(app, client):
    from services.core import menu_preference_service as svc

    _login_admin(app, client)
    with app.app_context():
        assert svc.get_global_icon_max_depth() == -1

    resp = client.post(
        "/admin/menu-settings/",
        data={
            "order_overrides_json": "{}",
            "collapsed_nodes_json": "[]",
            "icon_max_depth": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert svc.get_global_icon_max_depth() == 1

    # E o valor salvo já reflete de volta na sidebar, sem precisar de
    # nenhum outro passo (mesma engine que os testes acima já cobrem).
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    idx1 = html.find('data-menu-node="TX_GROUP_YEAST_BANK"')
    trecho1_ate_span = html[idx1:html.find("<span>", idx1)]
    assert "<i class=" not in trecho1_ate_span
