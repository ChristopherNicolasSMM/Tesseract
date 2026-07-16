"""
tests/test_plant_workspace.py

Workspace consolidado por Planta (conversa — "Dashboard + Etapas +
Sessões + Planta numa tela só"). Fase 1: casca (seletor/criação de
Planta + barra de abas) + aba Dashboard funcionando via fragmento
AJAX. As demais abas (Sessões, Planta, Receita Mash, Automação)
aparecem desabilitadas — sem rota de fragmento ainda, fora de escopo
desta rodada.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget


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


# ── Landing (escolher/criar Planta) ─────────────────────────────────────────

def test_landing_lista_plantas_existentes(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Workspace Landing")
        db.session.add(plant)
        db.session.commit()

    resp = client.get("/brewstation/plant-workspace/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta Workspace Landing" in html


def test_landing_sem_planta_nenhuma_mostra_aviso(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/")
    html = resp.data.decode("utf-8")
    assert "Nenhuma Planta cadastrada" in html


# ── Casca (shell) ────────────────────────────────────────────────────────────

def test_shell_renderiza_barra_de_abas(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Workspace Shell")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'id="pwTabBar"' in html
    assert 'id="pwTab-dashboard"' in html
    assert 'id="pwTab-sessions"' in html
    assert 'id="pwTab-plant"' in html
    assert 'id="pwTab-recipe"' in html
    assert 'id="pwTab-automation"' in html
    # só a aba Dashboard vem habilitada nesta fase
    assert html.count("disabled") >= 4


def test_shell_planta_inexistente_redireciona(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999", follow_redirects=True)
    assert resp.status_code == 200
    assert "Planta não encontrada" in resp.data.decode("utf-8") or "Workspace de Planta" in resp.data.decode("utf-8")


def test_shell_js_tem_hook_de_limpeza_de_aba(app, client):
    """Confirma que a casca chama __tabCleanup antes de trocar de aba —
    sem isso o polling do Dashboard ficaria rodando escondido."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Workspace Cleanup")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}")
    html = resp.data.decode("utf-8")
    assert "window.__tabCleanup" in html
    assert "teardownCurrentTab" in html


# ── Aba Dashboard (fragmento AJAX) ──────────────────────────────────────────

def test_tab_dashboard_sem_layout_mostra_estado_vazio(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Dashboard")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "ainda não tem nenhum Dashboard" in html
    # fragmento não pode ter o layout do Core em volta
    assert "<html" not in html.lower()


def test_tab_dashboard_com_layout_renderiza_fragmento(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Com Dashboard")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="Layout da Planta", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="text", config_json={"content": "Oi"})
        db.session.add(widget)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "<html" not in html.lower()
    assert 'id="dbCanvas"' in html
    assert "Oi" in html
    # o hook de limpeza do polling precisa estar presente no fragmento
    assert "window.__tabCleanup" in html


def test_tab_dashboard_so_lista_layouts_da_propria_planta(app, client):
    """Achado da conversa: dentro do workspace, trocar de layout não
    pode navegar a página inteira (perderia o contexto da aba) — e o
    seletor só deve listar os layouts DESTA planta, não do sistema
    inteiro."""
    _login_admin(app, client)
    with app.app_context():
        plant_a = BrewPlant(name="Planta A Workspace")
        plant_b = BrewPlant(name="Planta B Workspace")
        db.session.add_all([plant_a, plant_b])
        db.session.commit()
        layout_a1 = DashboardLayout(name="Layout A1", plant_id=plant_a.id)
        layout_a2 = DashboardLayout(name="Layout A2", plant_id=plant_a.id)
        layout_b1 = DashboardLayout(name="Layout B1", plant_id=plant_b.id)
        db.session.add_all([layout_a1, layout_a2, layout_b1])
        db.session.commit()
        plant_a_id = plant_a.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_a_id}/tab/dashboard")
    html = resp.data.decode("utf-8")
    assert "Layout A1" in html or "Layout A2" in html
    assert "Layout B1" not in html
    # dentro do fragmento, troca de layout não pode ser navegação de página inteira
    assert 'onchange="window.location.href=this.value"' not in html


def test_tab_dashboard_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta não encontrada" in html
    assert "<html" not in html.lower()


# ── Regressão: a tela cheia continua igual depois da extração pra partials ──

def test_view_cheia_continua_mostrando_todos_os_layouts_do_sistema(app, client):
    """A extração dos partials (_content.html/_scripts.html) não pode
    mudar o comportamento da tela cheia — ela continua listando TODOS
    os layouts do sistema no seletor, não só os da mesma Planta."""
    _login_admin(app, client)
    with app.app_context():
        plant_a = BrewPlant(name="Planta A View Cheia")
        plant_b = BrewPlant(name="Planta B View Cheia")
        db.session.add_all([plant_a, plant_b])
        db.session.commit()
        layout_a = DashboardLayout(name="Layout A View Cheia", plant_id=plant_a.id)
        layout_b = DashboardLayout(name="Layout B View Cheia", plant_id=plant_b.id)
        db.session.add_all([layout_a, layout_b])
        db.session.commit()
        layout_a_id = layout_a.id

    resp = client.get(f"/brewstation/dashboards/{layout_a_id}/view")
    html = resp.data.decode("utf-8")
    assert "Layout A View Cheia" in html
    assert "Layout B View Cheia" in html  # tela cheia = todos os layouts, comportamento inalterado
