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
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep


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


# ── Aba Sessões (fragmento AJAX) ─────────────────────────────────────────────

def test_tab_sessions_sem_sessao_mostra_estado_vazio(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Sessao")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Nenhuma sessão cadastrada" in html
    assert "<html" not in html.lower()


def test_tab_sessions_seleciona_active_automaticamente(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sessao Auto")
        db.session.add(plant)
        db.session.commit()
        s1 = BrewSession(name="Sessão Draft Antiga", plant_id=plant.id, status="draft")
        db.session.add(s1)
        db.session.commit()
        s2 = BrewSession(name="Sessão Active Nova", plant_id=plant.id, status="active")
        db.session.add(s2)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions")
    html = resp.data.decode("utf-8")
    assert "Sessão Active Nova" in html
    # confirma que é a sessão ACTIVE selecionada (aparece no cabeçalho de detalhe), não a draft
    assert html.count("Sessão Active Nova") >= 2  # aparece na lista lateral + no cabeçalho


def test_tab_sessions_session_id_troca_selecao(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Troca Sessao")
        db.session.add(plant)
        db.session.commit()
        s1 = BrewSession(name="Sessão A Troca", plant_id=plant.id, status="completed")
        s2 = BrewSession(name="Sessão B Troca", plant_id=plant.id, status="completed")
        db.session.add_all([s1, s2])
        db.session.commit()
        plant_id, s1_id = plant.id, s1.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={s1_id}")
    html = resp.data.decode("utf-8")
    assert html.count("Sessão A Troca") >= 2


def test_tab_sessions_mostra_passos_logs_e_alarmes(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Passos Logs Alarmes")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="Sessão Completa Tab", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()
        step = BrewSessionStep(session_id=session.id, step_index=0, name="Mostura Principal", step_type="mash", status="active", target_temp=66.0, duration_seconds=3600, ramp_seconds=600)
        log = BrewSessionLog(session_id=session.id, log_level="warning", message="Temperatura acima do esperado")
        alarm = BrewSessionAlarm(session_id=session.id, severity="high", message="Lúpulo: Magnum - 22g")
        db.session.add_all([step, log, alarm])
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions")
    html = resp.data.decode("utf-8")
    assert "Mostura Principal" in html
    assert "Temperatura acima do esperado" in html
    assert "Lúpulo: Magnum - 22g" in html


def test_tab_sessions_adicionar_etapa_navega_pra_aba_receita_mash(app, client):
    """[ATUALIZADO] A aba Receita Mash agora existe de verdade — o
    botão 'Adicionar Etapa' não abre mais link externo, navega DENTRO
    do workspace (via window.__workspaceLoadUrl) pra
    plant_workspace.tab_recipe com a receita certa pré-selecionada."""
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Pra Sessao Tab")
        db.session.add(recipe)
        db.session.commit()
        plant = BrewPlant(name="Planta Adicionar Etapa")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="Sessão Com Receita", plant_id=plant.id, recipe_id=recipe.id, status="active")
        db.session.add(session)
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions")
    html = resp.data.decode("utf-8")
    assert f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}" in html
    assert "Adicionar Etapa" in html
    assert "dbGoToRecipeTabBtn" in html


def test_tab_sessions_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/sessions")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta não encontrada" in html
    assert "<html" not in html.lower()


def test_tab_sessions_troca_de_sessao_reexecuta_scripts_via_helper_global(app, client):
    """Achado real: a sub-navegação de troca de sessão dentro da aba
    também usa innerHTML — sem reexecutar o <script> novo via helper
    global, a segunda troca de sessão em diante perderia o listener de
    clique. [ATUALIZADO] o mecanismo virou genérico
    (window.__workspaceLoadUrl/window.__workspaceReloadCurrent),
    reaproveitado por qualquer aba com sub-navegação própria (Sessões
    e, agora, Receita Mash)."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Reexecuta Script")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    shell_html = client.get(f"/brewstation/plant-workspace/{plant_id}").data.decode("utf-8")
    assert "window.__workspaceLoadUrl = loadUrl;" in shell_html
    assert "window.__workspaceReloadCurrent = function" in shell_html

    tab_html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions").data.decode("utf-8")
    assert "window.__workspaceLoadUrl" in tab_html


# ── Aba Planta (fragmento AJAX) ──────────────────────────────────────────────

def test_tab_plant_mostra_dados_da_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Aba Dados", capacity_liters=50.0, vessel_count=2, is_active=True)
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta Aba Dados" in html
    assert "50.0 L" in html
    assert "<html" not in html.lower()


def test_tab_plant_lista_tanques_sem_nenhum_mostra_aviso(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Tanque")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    html = resp.data.decode("utf-8")
    assert "Nenhum Tanque cadastrado" in html


def test_tab_plant_lista_tanques_e_mapeamentos(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Com Tanques Mapeamentos")
        db.session.add(plant)
        db.session.commit()
        vessel = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Panela Principal")
        db.session.add(vessel)
        db.session.commit()
        mapping = BrewPlantMapping(vessel_id=vessel.id, role_key="sensor_temp", device_function_name="temp_mash_sensor")
        db.session.add(mapping)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    html = resp.data.decode("utf-8")
    assert "Panela Principal" in html
    assert "Mash Tun" in html  # vessel_type formatado (mash_tun -> Mash Tun)
    assert "sensor_temp" in html
    assert "temp_mash_sensor" in html


def test_tab_plant_nao_mistura_tanques_de_outra_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant_a = BrewPlant(name="Planta A Tanques")
        plant_b = BrewPlant(name="Planta B Tanques")
        db.session.add_all([plant_a, plant_b])
        db.session.commit()
        vessel_a = BrewPlantVessel(plant_id=plant_a.id, vessel_type="fermenter", label_text="Fermentador A")
        vessel_b = BrewPlantVessel(plant_id=plant_b.id, vessel_type="fermenter", label_text="Fermentador B")
        db.session.add_all([vessel_a, vessel_b])
        db.session.commit()
        plant_a_id = plant_a.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_a_id}/tab/plant")
    html = resp.data.decode("utf-8")
    assert "Fermentador A" in html
    assert "Fermentador B" not in html


def test_tab_plant_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/plant")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta não encontrada" in html
    assert "<html" not in html.lower()


# ── Aba Receita Mash (fragmento AJAX) ────────────────────────────────────────

def test_tab_recipe_sem_recipe_id_mostra_picker(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Receita Picker")
        db.session.add(plant)
        db.session.commit()
        recipe = MashRecipe(name="Receita Pra Picker")
        db.session.add(recipe)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Receita Pra Picker" in html
    assert "<html" not in html.lower()


def test_tab_recipe_picker_sem_receita_nenhuma_mostra_aviso(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Receita")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe")
    html = resp.data.decode("utf-8")
    assert "Nenhuma receita cadastrada" in html


def test_tab_recipe_com_recipe_id_embute_editor_de_timeline(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Receita Editor")
        db.session.add(plant)
        db.session.commit()
        recipe = MashRecipe(name="Receita Editor Timeline")
        db.session.add(recipe)
        db.session.commit()
        step = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mostura Editor")
        db.session.add(step)
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "<html" not in html.lower()
    assert 'id="timelineTable"' in html
    assert "Mostura Editor" in html


def test_tab_recipe_pre_seleciona_planta_do_workspace_no_gerar_sessao(app, client):
    """Achado real: dentro do workspace já sabemos qual Planta é —
    pré-seleciona ela no select de 'Gerar Sessão', em vez de deixar o
    usuário escolher de novo."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Pre Selecionada")
        db.session.add(plant)
        db.session.commit()
        recipe = MashRecipe(name="Receita Pre Selecao")
        db.session.add(recipe)
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}")
    html = resp.data.decode("utf-8")
    assert f'<option value="{plant_id}" selected>' in html


def test_tab_recipe_reload_view_usa_helper_do_workspace_nao_reload_de_pagina(app, client):
    """Achado real: os 3 pontos que faziam window.location.reload()
    direto (adicionar etapa, resync lúpulo, remover etapa) sairiam do
    contexto da aba. Substituídos por reloadView(), que reaproveita
    window.__workspaceReloadCurrent quando existe."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Reload View")
        db.session.add(plant)
        db.session.commit()
        recipe = MashRecipe(name="Receita Reload View")
        db.session.add(recipe)
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}")
    html = resp.data.decode("utf-8")
    assert "function reloadView()" in html
    assert html.count("window.location.reload();") == 1
    assert "reloadView();" in html


def test_tab_recipe_view_cheia_continua_funcionando_sem_is_fragment(app, client):
    """A extração dos partials não pode mudar a tela cheia de
    recipe_timeline — reload direto continua valendo lá (não tem
    window.__workspaceReloadCurrent fora do workspace)."""
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Tela Cheia")
        db.session.add(recipe)
        db.session.commit()
        recipe_id = recipe.id

    resp = client.get(f"/brewstation/recipe-timeline/{recipe_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Trocar receita" in html
    assert "Ver Dashboard" in html
    assert 'id="timelineTable"' in html


def test_tab_recipe_receita_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Receita Inexistente")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id=999999")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Receita não encontrada" in html
    assert "<html" not in html.lower()


def test_tab_recipe_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/recipe")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta não encontrada" in html
    assert "<html" not in html.lower()
