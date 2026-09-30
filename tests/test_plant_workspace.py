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
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule_log import AutomationRuleLog


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


def test_mapeamento_planta_cria_vinculo_e_rejeita_outra_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Mapeada")
        other = BrewPlant(name="Outra Planta")
        db.session.add_all([plant, other])
        db.session.flush()
        vessel = BrewPlantVessel(plant_id=plant.id, label_text="Mostura", vessel_type="mash_tun")
        other_vessel = BrewPlantVessel(plant_id=other.id, label_text="Fervura", vessel_type="boil_kettle")
        function = DeviceFunction(name="workspace_temp", display_name="Temperatura", category="sensor")
        db.session.add_all([vessel, other_vessel, function])
        db.session.commit()
        plant_id, vessel_id, other_id = plant.id, vessel.id, other_vessel.id

    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    assert fragment.status_code == 200
    assert b'pwMappingForm' in fragment.data
    assert b'workspace_temp' in fragment.data

    url = f"/brewstation/plant-workspace/{plant_id}/mappings"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    payload = {"vessel_id": other_id, "role_key": "sensor_temp",
               "device_function_name": "workspace_temp", "is_required": "on"}
    assert client.post(url, data=payload, headers=headers).status_code == 400
    payload["vessel_id"] = vessel_id
    payload["role_key"] = "actor_heat"
    assert client.post(url, data=payload, headers=headers).status_code == 400
    payload["role_key"] = "sensor_temp"
    assert client.post(url, data=payload, headers=headers).status_code == 201
    assert client.post(url, data=payload, headers=headers).status_code == 409
    with app.app_context():
        mapping = BrewPlantMapping.query.filter_by(vessel_id=vessel_id, role_key="sensor_temp").one()
        assert mapping.device_function_name == "workspace_temp"
        assert mapping.is_required is True


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


def test_atalho_de_sessoes_preserva_aba_ao_escolher_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Menu Sessões")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id
    html = client.get("/brewstation/plant-workspace/?tab=sessions").data.decode("utf-8")
    assert f"/brewstation/plant-workspace/{plant_id}?tab=sessions" in html


def test_agua_agrupa_por_receita_e_detalha_contextos(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Água Consolidada", versao=2, origem_receita="BrewFather")
        db.session.add(recipe)
        db.session.flush()
        db.session.add_all([
            WaterProfile(recipe_id=recipe.id, contexto="source", calcio=0),
            WaterProfile(recipe_id=recipe.id, contexto="target", calcio=50, ph=5.4),
            WaterProfile(recipe_id=recipe.id, contexto="mash", calcio=60, is_deleted=True),
        ])
        db.session.commit()
        recipe_id = recipe.id
    response = client.get("/brewstation/water-profiles/portal/?q=Consolidada")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "2 contexto(s)" in html
    assert f"/brewstation/water-profiles/portal/{recipe_id}" in html
    response = client.get(f"/brewstation/water-profiles/portal/{recipe_id}")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Água de origem" in html and "Perfil alvo" in html
    assert "0.0 ppm" in html and "Não informado" in html
    assert "Mostura</h5>" not in html
    assert client.get("/brewstation/water-profiles/portal/999999").status_code == 404


def test_lista_antiga_de_agua_encaminha_ao_portal(app, client):
    _login_admin(app, client)
    response = client.get("/brewstation/water-profiles/")
    assert response.status_code == 302
    assert "/brewstation/water-profiles/portal/" in response.headers["Location"]
    assert client.get("/brewstation/water-profiles/?view=records").status_code == 200


def test_edicao_integrada_valida_dados_e_escopo_da_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Editar Workspace")
        other = BrewPlant(name="Outra planta de edição")
        db.session.add_all([plant, other])
        db.session.flush()
        vessel = BrewPlantVessel(plant_id=plant.id, label_text="Tanque original", vessel_type="mash_tun")
        other_vessel = BrewPlantVessel(plant_id=other.id, label_text="Tanque alheio", vessel_type="mash_tun")
        function = DeviceFunction(name="workspace_edit_temp", display_name="Temperatura edição", category="sensor")
        db.session.add_all([vessel, other_vessel, function])
        db.session.flush()
        mapping = BrewPlantMapping(vessel_id=vessel.id, role_key="sensor_temp", device_function_name=function.name)
        db.session.add(mapping)
        db.session.commit()
        pid, oid, vid, other_vid, mid = plant.id, other.id, vessel.id, other_vessel.id, mapping.id
    headers = {"X-Requested-With": "XMLHttpRequest"}
    base = f"/brewstation/plant-workspace/{pid}"
    payload = {"name": "Planta editada", "capacity_liters": "35,5", "description": "Descrição", "is_active": "on"}
    assert client.post(base + "/edit", data={**payload, "capacity_liters": "nan"}, headers=headers).status_code == 400
    response = client.post(base + "/edit", data=payload, headers=headers)
    assert response.status_code == 200
    assert response.json["plant_name"] == "Planta editada"
    tank = {"label_text": "Tanque editado", "vessel_type": "boil_kettle", "position_order": "2", "plant_id": oid}
    assert client.post(base + f"/vessels/{other_vid}/edit", data=tank, headers=headers).status_code == 404
    assert client.post(base + f"/vessels/{vid}/edit", data=tank, headers=headers).status_code == 200
    link = {"vessel_id": vid, "role_key": "sensor_temp", "device_function_name": "workspace_edit_temp", "label_text": "Leitura"}
    assert client.post(base + f"/mappings/{mid}/edit", data={**link, "vessel_id": other_vid}, headers=headers).status_code == 400
    assert client.post(f"/brewstation/plant-workspace/{oid}/mappings/{mid}/edit", data=link, headers=headers).status_code == 404
    assert client.post(base + f"/mappings/{mid}/edit", data=link, headers=headers).status_code == 200
    with app.app_context():
        assert db.session.get(BrewPlantVessel, vid).plant_id == pid
        assert db.session.get(BrewPlantMapping, mid).label_text == "Leitura"
        assert db.session.get(BrewPlantMapping, mid).is_required is False
    html = client.get(base + "/tab/plant").data.decode("utf-8")
    assert 'data-weakref-source="device_functions"' in html
    assert f'pwEditVessel{vid}' in html


def test_edicao_integrada_exige_permissao_de_atualizar(app, client):
    with app.app_context():
        plant = BrewPlant(name="Planta protegida")
        user = User(username="workspace_sem_acesso", email="workspace_sem_acesso@test.local",
                    nome="Teste", nome_completo="Teste", celular="0", is_active=True, is_admin=False)
        user.set_password("senha123")
        db.session.add_all([plant, user])
        db.session.commit()
        pid = plant.id
    client.post("/api/auth/login", json={"username": "workspace_sem_acesso", "password": "senha123"})
    for path in ("edit", "vessels/999999/edit", "mappings/999999/edit"):
        response = client.post(f"/brewstation/plant-workspace/{pid}/{path}",
                               data={"name": "Não permitido"}, headers={"X-Requested-With": "XMLHttpRequest"})
        assert response.status_code == 403
    with app.app_context():
        assert db.session.get(BrewPlant, pid).name == "Planta protegida"


def test_landing_sem_planta_nenhuma_mostra_aviso(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/")
    html = resp.data.decode("utf-8")
    assert "Nenhuma Planta cadastrada" in html


def test_landing_cria_planta_e_abre_configuracao(app, client):
    _login_admin(app, client)
    resp = client.post("/brewstation/plant-workspace/", data={"name": "Planta Piloto Integrada"})
    assert resp.status_code == 302
    with app.app_context():
        plant = BrewPlant.query.filter_by(name="Planta Piloto Integrada").first()
        assert plant is not None
        assert f"/brewstation/plant-workspace/{plant.id}?tab=plant" in resp.headers["Location"]
    shell_html = client.get(resp.headers["Location"]).data.decode("utf-8")
    assert 'id="pwTab-plant"' in shell_html
    assert "__workspaceSubmitForm" in shell_html


# ── Casca (shell) ────────────────────────────────────────────────────────────

def test_shell_renderiza_barra_de_abas(app, client):
    """[ATUALIZADO] As 5 abas planejadas em conversa agora estão TODAS
    habilitadas — não sobra nenhum atributo 'disabled' na barra."""
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
    tab_bar_html = html.split('id="pwTabBar"')[1].split("</ul>")[0]
    assert "disabled" not in tab_bar_html


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


def test_shell_modo_kiosk_presente(app, client):
    """Conversa — modo Kiosk: botão + lógica de fullscreen/esconder
    chrome do Tesseract ficam centralizados na casca (shell.html), não
    em cada aba — cobre as 5 abas do Workspace de graça."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Workspace Kiosk")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}")
    html = resp.data.decode("utf-8")
    assert 'id="pwKioskToggle"' in html
    assert "pw-kiosk-mode" in html
    assert "requestFullscreen" in html
    assert "Ctrl+Shift+K" in html or "ctrlKey && e.shiftKey" in html


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
    assert 'id="pwLayoutForm"' in html


def test_workspace_cria_layout_da_planta_e_abre_editor(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Painel Inicial")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.post(f"/brewstation/plant-workspace/{plant_id}/dashboard-layouts",
                       data={"name": "Painel da Mostura"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 201
    layout_id = resp.get_json()["id"]
    with app.app_context():
        layout = db.session.get(DashboardLayout, layout_id)
        assert layout.plant_id == plant_id
        assert layout.is_default is True
    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/dashboard").data.decode("utf-8")
    assert "Painel da Mostura" in fragment
    assert 'id="dbCanvas"' in fragment


def test_workspace_nao_cria_layout_em_planta_inexistente(app, client):
    _login_admin(app, client)
    resp = client.post("/brewstation/plant-workspace/999999/dashboard-layouts",
                       data={"name": "Painel órfão"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


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
    assert 'id="pwNewSessionBtn"' in html
    assert "window.__workspaceOpenTab('recipe')" in html


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


def test_workspace_adiciona_tanque_na_planta_sem_aceitar_tipo_invalido(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Tanque Inicial")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    url = f"/brewstation/plant-workspace/{plant_id}/vessels"
    invalid = client.post(url, data={"label_text": "Tanque impróprio", "vessel_type": "qualquer"},
                          headers={"X-Requested-With": "XMLHttpRequest"})
    assert invalid.status_code == 400
    resp = client.post(url, data={"label_text": "Panela Principal", "vessel_type": "mash_tun"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 201
    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant").data.decode("utf-8")
    assert "Panela Principal" in fragment
    assert "1 tanque(s) cadastrado(s)" in fragment
    with app.app_context():
        vessels = BrewPlantVessel.query.filter_by(plant_id=plant_id).all()
        assert len(vessels) == 1
        assert vessels[0].id == resp.get_json()["id"]


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


def test_tab_recipe_reune_dados_importados_e_pendencias_sem_gerar_sessao(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta da Receita Completa")
        recipe = MashRecipe(name="Receita Brewfather Integrada", origem_receita="BrewFather",
                            origem_receita_id="externo-42")
        db.session.add_all([plant, recipe])
        db.session.flush()
        db.session.add_all([
            RecipeIngredient(recipe_id=recipe.id, descricao_origem="Malte sem de-para",
                             quantidade=2, unidade_medida="kg", status_resolucao="pendente_depara"),
            RecipeIngredient(recipe_id=recipe.id, descricao_origem="Água fora do estoque",
                             status_resolucao="ignorado"),
            RecipeStep(recipe_id=recipe.id, step_type="mash", nome="Mostura 65", ordem=0),
            FermentationStep(recipe_id=recipe.id, nome="Fermentação primária", ordem=0,
                             temperatura=19, tempo_dias=7),
            WaterProfile(recipe_id=recipe.id, contexto="target", ph=5.4, calcio=70),
        ])
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "<html" not in html.lower()
    for label in ("Receita Brewfather Integrada", "externo-42", "Malte sem de-para",
                  "Água fora do estoque", "1 pendência(s)", "Fermentação primária",
                  "target", "Mostura 65", "Volume planejado: não informado",
                  "Nenhum snapshot registrado"):
        assert label in html
    assert f'/brewstation/recipe-ingredients/' in html
    with app.app_context():
        assert BrewSession.query.count() == 0


def test_gerar_sessao_no_workspace_retorna_id_sem_sair_para_tela_completa(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Gerar no Workspace")
        recipe = MashRecipe(name="Receita Gerar no Workspace")
        db.session.add_all([plant, recipe])
        db.session.flush()
        db.session.add(RecipeStep(recipe_id=recipe.id, step_type="mash", nome="Etapa Inicial", ordem=0))
        db.session.commit()
        plant_id, recipe_id = plant.id, recipe.id

    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/recipe?recipe_id={recipe_id}").data.decode("utf-8")
    assert 'id="workspaceGenerateSessionForm"' in fragment
    assert 'target="_blank"' not in fragment.split('id="workspaceGenerateSessionForm"')[1].split('</form>')[0]
    assert "window.__workspaceOpenTab('sessions'" in fragment

    resp = client.post(f"/brewstation/recipe-timeline/{recipe_id}/generate-session", data={
        "plant_id": str(plant_id), "name": "Novo lote no workspace", "status": "draft",
    }, headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["plant_id"] == plant_id
    assert data["status"] == "draft"
    session_fragment = client.get(
        f"/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={data['session_id']}"
    ).data.decode("utf-8")
    assert "Novo lote no workspace" in session_fragment
    assert "Etapa Inicial" in session_fragment


def test_gerar_sessao_ajax_invalida_nao_cria_lote(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Sem Etapa")
        plant = BrewPlant(name="Planta Sem Etapa")
        db.session.add_all([recipe, plant])
        db.session.commit()
        recipe_id, plant_id = recipe.id, plant.id

    resp = client.post(f"/brewstation/recipe-timeline/{recipe_id}/generate-session", data={
        "plant_id": str(plant_id), "name": "Lote inválido", "status": "draft",
    }, headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
    with app.app_context():
        assert BrewSession.query.filter_by(name="Lote inválido").count() == 0


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


# ── Aba Automação (fragmento AJAX) ───────────────────────────────────────────

def test_tab_automation_sem_regra_mostra_aviso(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Regra")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Nenhuma regra de automação cadastrada" in html
    assert "<html" not in html.lower()


def test_tab_automation_mostra_regra_global_sem_sessao(app, client):
    """Regra sem session_id (nullable) é "global" — vale pra
    qualquer Planta, sempre aparece."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Regra Global")
        db.session.add(plant)
        db.session.commit()
        rule = AutomationRule(
            name="Regra Global Teste", sensor_function_name="temp_mash", condition_operator=">=",
            condition_value=68.0, actor_function_name="heater_mash", actor_action="OFF",
        )
        db.session.add(rule)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation")
    html = resp.data.decode("utf-8")
    assert "Regra Global Teste" in html


def test_tab_automation_mostra_regra_vinculada_a_sessao_da_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Regra Sessao")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="Sessão Pra Regra", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()
        rule = AutomationRule(
            name="Regra Da Sessao", sensor_function_name="temp_boil", condition_operator="<",
            condition_value=95.0, actor_function_name="heater_boil", actor_action="ON",
            session_id=session.id,
        )
        db.session.add(rule)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation")
    html = resp.data.decode("utf-8")
    assert "Regra Da Sessao" in html


def test_tab_automation_nao_mostra_regra_de_sessao_de_outra_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant_a = BrewPlant(name="Planta A Regra")
        plant_b = BrewPlant(name="Planta B Regra")
        db.session.add_all([plant_a, plant_b])
        db.session.commit()
        session_b = BrewSession(name="Sessão Planta B", plant_id=plant_b.id, status="active")
        db.session.add(session_b)
        db.session.commit()
        rule_b = AutomationRule(
            name="Regra Exclusiva Planta B", sensor_function_name="temp_x", condition_operator=">",
            condition_value=50.0, actor_function_name="actor_x", actor_action="ON",
            session_id=session_b.id,
        )
        db.session.add(rule_b)
        db.session.commit()
        plant_a_id = plant_a.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_a_id}/tab/automation")
    html = resp.data.decode("utf-8")
    assert "Regra Exclusiva Planta B" not in html


def test_tab_automation_mostra_historico_de_disparo(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Historico")
        db.session.add(plant)
        db.session.commit()
        rule = AutomationRule(
            name="Regra Com Historico", sensor_function_name="temp_y", condition_operator=">=",
            condition_value=70.0, actor_function_name="actor_y", actor_action="OFF",
        )
        db.session.add(rule)
        db.session.commit()
        log = AutomationRuleLog(rule_id=rule.id, sensor_value_at_trigger=71.5, action_taken="OFF", success=True)
        db.session.add(log)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation")
    html = resp.data.decode("utf-8")
    assert "Regra Com Historico" in html
    assert "71.5" in html


def test_tab_automation_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/automation")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta não encontrada" in html
    assert "<html" not in html.lower()


def test_shell_todas_as_5_abas_habilitadas(app, client):
    """Fecha o desenho original: as 5 abas planejadas em conversa
    (Dashboard, Sessões, Planta, Receita Mash, Automação) agora
    funcionam de ponta a ponta."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Todas Abas")
        db.session.add(plant)
        db.session.commit()
        plant_id = plant.id

    resp = client.get(f"/brewstation/plant-workspace/{plant_id}")
    html = resp.data.decode("utf-8")
    assert "disabled" not in html.split('id="pwTabBar"')[1].split("</ul>")[0]
