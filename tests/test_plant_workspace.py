"""
tests/test_plant_workspace.py

Workspace consolidado por Planta: casca, abas AJAX, planta/dashboard,
sessões, alarmes e receita. Inclui saneamento local, revisão completa e
dados planejados, preservando histórico, permissões e transações.
"""
import pytest
from html.parser import HTMLParser


def _dashboard_combo_ids(html):
    """Lê o escopo REAL do combo que será enviado à API, sem depender de options."""
    class ComboParser(HTMLParser):
        ids = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "div" and attrs.get("data-weakref-source") == "dashboard_layouts":
                self.ids = [int(value) for value in attrs["data-weakref-ids"].split(",") if value]

    parser = ComboParser()
    parser.feed(html)
    assert parser.ids is not None, "Combo pesquisável de dashboards ausente"
    return parser.ids


def _workspace_sanitation_data(app):
    from addons.addon_estoque.root.model.material import Material
    from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
    from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
    from addons.addon_estoque.root.model.categoria import Categoria
    with app.app_context():
        origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
        tipo = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
        categoria = Categoria.query.filter_by(descricao="materia_prima").first()
        if not categoria:
            categoria = Categoria(descricao="materia_prima", codigo="MATERIA_PRIMA", tipo_produto_id=tipo.id)
            db.session.add(categoria)
            db.session.flush()
        material = Material(nome="Malte para saneamento", sku="MALTE-SANEAMENTO", unidade_medida="kg",
                            origem_id=origem.id, tipo_produto_id=tipo.id, categoria_id=categoria.id)
        plant = BrewPlant(name="Planta saneamento")
        recipe = MashRecipe(name="Receita saneamento", origem_receita="Manual", versao=1)
        db.session.add_all([material, plant, recipe])
        db.session.flush()
        ing = RecipeIngredient(recipe_id=recipe.id, descricao_origem="Malte importado",
                               quantidade=5, unidade_medida="kg", tipo_ingrediente="fermentavel")
        db.session.add(ing)
        db.session.commit()
        return plant.id, recipe.id, ing.id, material.id


def test_workspace_saneamento_vincula_e_recarrega_conferencia_sem_consumo(app, client):
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_estoque.root.model.material import Material
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    url = f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize"
    with app.app_context():
        before = db.session.get(RecipeIngredient, iid).to_dict()
        count, materials = Movimentacao.query.count(), Material.query.count()
    response = client.post(url, data={"material_id": mid, "status_resolucao": "resolvido",
                                     "quantidade": 999, "recipe_id": 99999},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200 and response.get_json()["ok"]
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).to_dict() == {**before, "material_id": mid, "status_resolucao": "resolvido"}
        assert Movimentacao.query.count() == count and Material.query.count() == materials
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'class="pw-ingredient-sanitation' in html
    assert 'data-weakref-source="materials"' in html
    assert 'name="status_resolucao" class="form-select"' in html
    assert "Malte para saneamento" in html and "Pronto" in html
    assert "confirm_ignore_ingredient" in html and "__workspaceSubmitForm" in html
    assert "<datalist" not in html
    options = client.get("/api/options/materials?search=Malte%20para%20saneamento").get_json()
    assert any(str(row["id"]) == str(mid) for row in options["results"])
    ignored = client.post(url, data={"status_resolucao": "ignorado"}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert ignored.status_code == 200
    with app.app_context():
        saved = db.session.get(RecipeIngredient, iid)
        assert saved.material_id is None and saved.status_resolucao == "ignorado"
        assert Movimentacao.query.count() == count


@pytest.mark.parametrize("problema", ["planta", "receita", "ingrediente", "outra_receita"])
def test_workspace_saneamento_rejeita_contextos_apagados_ou_incompativeis(app, client, problema):
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    with app.app_context():
        if problema == "planta": db.session.get(BrewPlant, pid).is_deleted = True
        elif problema == "receita": db.session.get(MashRecipe, rid).is_deleted = True
        elif problema == "ingrediente": db.session.get(RecipeIngredient, iid).is_deleted = True
        else:
            other = MashRecipe(name="Outra receita saneamento", origem_receita="Manual", versao=1)
            db.session.add(other)
            db.session.flush()
            rid = other.id
        db.session.commit()
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data={"status_resolucao": "resolvido", "material_id": mid},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 404
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).material_id is None


@pytest.mark.parametrize("deleted", [False, True])
def test_workspace_saneamento_bloqueia_receita_em_uso_em_qualquer_planta(app, client, deleted):
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    with app.app_context():
        other_plant = BrewPlant(name="Outra planta histórica")
        db.session.add(other_plant)
        db.session.flush()
        db.session.add(BrewSession(name="Lote protegido", recipe_id=rid, plant_id=other_plant.id,
                                   status="draft", is_deleted=deleted))
        db.session.commit()
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'class="pw-ingredient-sanitation' not in html and "edição local está bloqueada" in html
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data={"status_resolucao": "ignorado"}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 409


def test_workspace_saneamento_respeita_permissao_na_tela_e_no_post(app, client, monkeypatch):
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != "recipe_ingredients.update")
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'class="pw-ingredient-sanitation' not in html
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data={"status_resolucao": "ignorado"}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).status_resolucao == "pendente_depara"


@pytest.mark.parametrize("payload", [{"status_resolucao": "resolvido", "material_id": "abc"},
                                     {"status_resolucao": "resolvido", "material_id": "99999"},
                                     {"status_resolucao": "inventado"}])
def test_workspace_saneamento_rejeita_payload_invalido(app, client, payload):
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 400 and not response.get_json()["ok"]


def test_workspace_saneamento_retorno_normal_preserva_receita(app, client):
    from urllib.parse import urlparse, parse_qs
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data={"status_resolucao": "resolvido", "material_id": mid})
    assert response.status_code == 302
    assert parse_qs(urlparse(response.location).query) == {"tab": ["recipe"], "recipe_id": [str(rid)]}
    html = client.get(response.location).data.decode()
    assert f'const initialRecipeId = "{rid}";' in html


@pytest.mark.parametrize("rid", ["abc", "0", "-1", "99999", ""])
def test_workspace_receita_explicitamente_invalida_nao_abre_picker(app, client, rid):
    _login_admin(app, client)
    pid, _, _, _ = _workspace_sanitation_data(app)
    response = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe", query_string={"recipe_id": rid})
    assert response.status_code == 404
    assert "Receita não encontrada" in response.data.decode()


def test_workspace_saneamento_falha_reverte_e_nao_expoe_excecao(app, client, monkeypatch):
    from addons.addon_brewstation.features.feature_mash_control.services import ingredient_sanitation_service
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    def falhar(*args, **kwargs):
        db.session.get(RecipeIngredient, iid).material_id = mid
        db.session.flush()
        raise RuntimeError("Detalhe interno")
    monkeypatch.setattr(ingredient_sanitation_service, "sanear_ingrediente", falhar)
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/sanitize",
                           data={"status_resolucao": "resolvido", "material_id": mid},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 500 and "Detalhe interno" not in response.data.decode()
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).material_id is None

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
    assert b'data-weakref-source="device_functions"' in fragment.data
    assert b'data-weakref-value-field="name"' in fragment.data
    # O combo padrão carrega opções pela API, não pelo HTML inicial.
    options = client.get("/api/options/device_functions?search=Temperatura&value_field=name")
    assert options.status_code == 200
    assert {"id": "workspace_temp", "text": "Temperatura"} in options.get_json()["results"]

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

    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    assert fragment.status_code == 200
    assert b'workspace_temp' in fragment.data


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
    assert "Esta planta não tem dashboard disponível." in html
    assert "pwDashboardMaintenance" in html
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


def test_dashboard_workspace_seleciona_layout_sem_sair_da_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Seleção Layout")
        other = BrewPlant(name="Outra Planta Seleção")
        db.session.add_all([plant, other])
        db.session.flush()
        first = DashboardLayout(name="Painel Principal Seleção", plant_id=plant.id, is_default=True)
        second = DashboardLayout(name="Painel Alternativo Seleção", plant_id=plant.id)
        foreign = DashboardLayout(name="Painel Outra Planta Seleção", plant_id=other.id)
        deleted = DashboardLayout(name="Painel Apagado Seleção", plant_id=plant.id, is_deleted=True)
        db.session.add_all([first, second, foreign, deleted])
        db.session.commit()
        plant_id, second_id, foreign_id, deleted_id = plant.id, second.id, foreign.id, deleted.id
    url = f"/brewstation/plant-workspace/{plant_id}/tab/dashboard"
    response = client.get(url, query_string={"layout_id": second_id})
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert '<h1>Painel Alternativo Seleção</h1>' in html
    assert 'id="pwDashboardSelector"' in html
    assert 'data-weakref-source="dashboard_layouts"' in html
    assert 'window.__workspaceLoadUrl(url)' in html
    assert 'id="pwLayoutEditForm"' in html
    assert 'id="pwLayoutAdditionalForm"' in html
    assert "window.__workspaceOpenTab('recipe')" in html
    for invalid_id in (foreign_id, deleted_id, "inválido"):
        assert client.get(url, query_string={"layout_id": invalid_id}).status_code == 404
    response = client.post(f"/brewstation/plant-workspace/{plant_id}/dashboard-layouts",
                           data={"name": "Painel Adicional Workspace"},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 201
    created_id = response.get_json()["id"]
    with app.app_context():
        created = db.session.get(DashboardLayout, created_id)
        assert created.plant_id == plant_id
        assert created.is_default is False
    refreshed = client.get(url)
    assert refreshed.status_code == 200
    allowed_ids = _dashboard_combo_ids(refreshed.get_data(as_text=True))
    assert created_id in allowed_ids
    assert foreign_id not in allowed_ids
    assert deleted_id not in allowed_ids
    options = client.get("/api/options/dashboard_layouts", query_string={
        "ids": ",".join(map(str, allowed_ids)), "search": "Painel Adicional Workspace",
    })
    assert options.status_code == 200
    assert options.get_json()["results"] == [{"id": created_id, "text": "Painel Adicional Workspace"}]
    selected = client.get(url, query_string={"layout_id": created_id})
    assert selected.status_code == 200
    assert '<h1>Painel Adicional Workspace</h1>' in selected.get_data(as_text=True)


def test_dashboard_workspace_edita_layout_preserva_planta_e_widgets(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Edição Layout")
        other = BrewPlant(name="Outra Planta Edição Layout")
        db.session.add_all([plant, other])
        db.session.flush()
        layout = DashboardLayout(name="Painel Antes", plant_id=plant.id, is_default=True)
        db.session.add(layout)
        db.session.flush()
        widget = DashboardWidget(layout_id=layout.id, widget_type="text", config_json={"content": "Preservado"})
        db.session.add(widget)
        db.session.commit()
        plant_id, other_id, layout_id, widget_id = plant.id, other.id, layout.id, widget.id
    url = f"/brewstation/plant-workspace/{plant_id}/dashboard-layouts/{layout_id}/edit"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    payload = {"name": "Painel Depois", "description": "Descrição do painel",
               "canvas_width": "1200", "canvas_height": "700", "plant_id": other_id}
    assert client.post(f"/brewstation/plant-workspace/{other_id}/dashboard-layouts/{layout_id}/edit",
                       data=payload, headers=headers).status_code == 404
    for invalid_width in ("0", "-1", "1.5", "nan", ""):
        assert client.post(url, data={**payload, "canvas_width": invalid_width}, headers=headers).status_code == 400
    response = client.post(url, data=payload, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    with app.app_context():
        saved = db.session.get(DashboardLayout, layout_id)
        assert saved.name == "Painel Depois"
        assert saved.description == "Descrição do painel"
        assert (saved.canvas_width, saved.canvas_height) == (1200, 700)
        assert saved.plant_id == plant_id
        assert saved.is_default is True
        assert db.session.get(DashboardWidget, widget_id).config_json == {"content": "Preservado"}
    html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/dashboard?layout_id={layout_id}").data.decode("utf-8")
    assert '<h1>Painel Depois</h1>' in html


def test_dashboard_workspace_edicao_exige_permissao(app, client, monkeypatch):
    _login_admin(app, client)
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != "dashboard_layouts.update")
    response = client.post("/brewstation/plant-workspace/1/dashboard-layouts/1/edit",
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 403


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
        layout_a_id, layout_b_id = layout_a.id, layout_b.id

    resp = client.get(f"/brewstation/dashboards/{layout_a_id}/view")
    html = resp.data.decode("utf-8")
    assert "Layout A View Cheia" in html
    allowed_ids = _dashboard_combo_ids(html)
    assert layout_a_id in allowed_ids
    assert layout_b_id in allowed_ids  # tela cheia inclui outras plantas
    options = client.get("/api/options/dashboard_layouts", query_string={
        "ids": ",".join(map(str, allowed_ids)), "search": "Layout B View Cheia",
    })
    assert options.status_code == 200
    assert options.get_json()["results"] == [{"id": layout_b_id, "text": "Layout B View Cheia"}]


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


def test_workspace_historico_acessa_sessao_antiga_e_filtra_nome_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Histórico Paginado")
        other = BrewPlant(name="Planta Histórico Separado")
        db.session.add_all([plant, other])
        db.session.flush()
        oldest = BrewSession(name="Histórico Antigo 100%", plant_id=plant.id, status="completed")
        foreign = BrewSession(name="Histórico Outra Planta", plant_id=other.id, status="completed")
        deleted = BrewSession(name="Histórico Apagado", plant_id=plant.id, is_deleted=True)
        db.session.add_all([oldest, foreign, deleted])
        db.session.flush()
        db.session.add_all([BrewSession(name=f"Histórico Novo {i:02d}", plant_id=plant.id, status="draft") for i in range(24)])
        db.session.commit()
        plant_id, oldest_id, foreign_id, deleted_id = plant.id, oldest.id, foreign.id, deleted.id
    url = f"/brewstation/plant-workspace/{plant_id}/tab/sessions"
    first = client.get(url).data.decode("utf-8")
    assert "Histórico Antigo 100%" not in first
    assert "Histórico Novo 23" in first
    second = client.get(url, query_string={"page": 2}).data.decode("utf-8")
    assert "Histórico Antigo 100%" in second
    assert "Histórico Novo 23" not in second
    selected = client.get(url, query_string={"session_id": oldest_id})
    assert selected.status_code == 200
    assert "Histórico Antigo 100%" in selected.data.decode("utf-8")
    filtered = client.get(url, query_string={"q": "%", "status": "completed"}).data.decode("utf-8")
    assert "Histórico Antigo 100%" in filtered
    assert "Histórico Novo" not in filtered
    empty = client.get(url, query_string={"q": "%", "status": "draft"}).data.decode("utf-8")
    assert "Nenhuma sessão encontrada com estes filtros." in empty
    for invalid in (foreign_id, deleted_id, "inválido"):
        response = client.get(url, query_string={"session_id": invalid})
        assert response.status_code == 404
        assert "Histórico Outra Planta" not in response.data.decode("utf-8")
    assert client.get(url, query_string={"status": "desconhecido"}).status_code == 400


def test_workspace_pagina_logs_alarmes_sem_misturar_sessoes(app, client):
    from datetime import datetime
    import html as html_module
    import re
    from urllib.parse import parse_qs, urlsplit

    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Histórico Eventos")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Sessão Histórico Eventos", plant_id=plant.id, status="completed")
        other = BrewSession(name="Sessão Outros Eventos", plant_id=plant.id)
        db.session.add_all([session, other])
        db.session.flush()
        when = datetime(2026, 1, 1, 12, 0)
        for i in range(25):
            db.session.add(BrewSessionLog(session_id=session.id, message=f"Registro Paginado {i:02d}", created_at=when,
                                         source="sensor", detail_json={"valor": i}))
            db.session.add(BrewSessionAlarm(session_id=session.id, message=f"Alarme Paginado {i:02d}", created_at=when))
        db.session.add(BrewSessionLog(session_id=other.id, message="Registro Exclusivo Outra Sessão"))
        db.session.add(BrewSessionAlarm(session_id=other.id, message="Alarme Exclusivo Outra Sessão"))
        db.session.add(BrewSessionLog(session_id=session.id, message="Registro Apagado", is_deleted=True))
        db.session.add(BrewSessionAlarm(session_id=session.id, message="Alarme Apagado", is_deleted=True))
        db.session.commit()
        plant_id, session_id = plant.id, session.id
    url = f"/brewstation/plant-workspace/{plant_id}/tab/sessions"
    first = client.get(url, query_string={"session_id": session_id}).data.decode("utf-8")
    assert "Registro Paginado 24" in first and "Registro Paginado 00" not in first
    assert "Alarme Paginado 24" in first and "Alarme Paginado 00" not in first
    assert "Origem: sensor" in first
    for message in ("Registro Exclusivo Outra Sessão", "Alarme Exclusivo Outra Sessão", "Registro Apagado", "Alarme Apagado"):
        assert message not in first
    links = re.findall(r'href="([^"]+)"[^>]*data-workspace-history-link', first)
    log_link = next(html_module.unescape(link) for link in links if "logs_page=2" in link)
    query = parse_qs(urlsplit(log_link).query)
    assert query["session_id"] == [str(session_id)]
    assert query["alarms_page"] == ["1"]
    log_next = client.get(log_link).data.decode("utf-8")
    assert "Registro Paginado 00" in log_next and "Registro Paginado 24" not in log_next
    assert "Alarme Paginado 24" in log_next
    both = client.get(url, query_string={"session_id": session_id, "logs_page": 2, "alarms_page": 2}).data.decode("utf-8")
    assert "Registro Paginado 00" in both and "Alarme Paginado 00" in both
    assert "Registro Paginado 24" not in both and "Alarme Paginado 24" not in both


def test_workspace_edita_lote_sem_alterar_execucao_ou_ledger(app, client):
    from datetime import datetime
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase

    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Edição de Lote")
        recipe = MashRecipe(name="Receita Edição de Lote")
        db.session.add_all([plant, recipe])
        db.session.flush()
        when = datetime(2026, 1, 1, 12, 0)
        session = BrewSession(name="Lote Original", plant_id=plant.id, recipe_id=recipe.id,
                             status="paused", started_at=when, paused_at=when,
                             insumos_baixados_em=when, custo_total_insumos=123.45, current_step_index=2)
        db.session.add(session)
        db.session.flush()
        step = BrewSessionStep(session_id=session.id, name="Etapa Preservada", step_index=2, status="active")
        db.session.add(step)
        db.session.commit()
        plant_id, recipe_id, session_id, step_id = plant.id, recipe.id, session.id, step.id
        movement_count, envase_count = Movimentacao.query.count(), Envase.query.count()
    url = f"/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/edit"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    payload = {"name": "Lote Renomeado", "notes": "Medição realizada\nSegunda linha", "volume_real_litros": "23,5",
               "status": "completed", "recipe_id": "", "current_step_index": "9",
               "custo_total_insumos": "0", "insumos_baixados_em": "", "plant_id": "999"}
    for invalid in ("-1", "nan", "inf", "-inf", "abc", "1e999"):
        assert client.post(url, data={**payload, "volume_real_litros": invalid}, headers=headers).status_code == 400
    assert client.post(url, data={**payload, "name": ""}, headers=headers).status_code == 400
    assert client.post(url, data={**payload, "name": "x" * 101}, headers=headers).status_code == 400
    assert client.post(url, data=payload, headers=headers).status_code == 200
    with app.app_context():
        saved = db.session.get(BrewSession, session_id)
        assert saved.name == "Lote Renomeado"
        assert saved.notes == "Medição realizada\nSegunda linha"
        assert saved.volume_real_litros == 23.5
        assert saved.status == "paused" and saved.current_step_index == 2
        assert saved.started_at == when and saved.paused_at == when
        assert saved.recipe_id == recipe_id and saved.plant_id == plant_id
        assert saved.custo_total_insumos == 123.45 and saved.insumos_baixados_em == when
        assert db.session.get(BrewSessionStep, step_id).status == "active"
        assert Movimentacao.query.count() == movement_count and Envase.query.count() == envase_count
    for value, expected in (("0", 0.0), ("", None)):
        assert client.post(url, data={**payload, "volume_real_litros": value}, headers=headers).status_code == 200
        with app.app_context():
            assert db.session.get(BrewSession, session_id).volume_real_litros == expected


def test_workspace_edicao_lote_verifica_planta_lixeira_e_permissao(app, client, monkeypatch):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Proteção Lote")
        other = BrewPlant(name="Outra Planta Proteção Lote")
        db.session.add_all([plant, other])
        db.session.flush()
        session = BrewSession(name="Lote Protegido", plant_id=plant.id)
        deleted = BrewSession(name="Lote Apagado", plant_id=plant.id, is_deleted=True)
        db.session.add_all([session, deleted])
        db.session.commit()
        plant_id, other_id, session_id, deleted_id = plant.id, other.id, session.id, deleted.id
    headers = {"X-Requested-With": "XMLHttpRequest"}
    payload = {"name": "Novo Nome", "volume_real_litros": "10", "notes": ""}
    for pid, sid in ((other_id, session_id), (plant_id, deleted_id)):
        assert client.post(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/edit",
                           data=payload, headers=headers).status_code == 404
    monkeypatch.setattr(User, "has_permission", lambda self, code: code not in ("brew_sessions.update", "envases.list"))
    assert client.post(f"/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/edit",
                       data=payload, headers=headers).status_code == 403
    html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={session_id}").data.decode("utf-8")
    assert 'id="pwSessionEditForm"' not in html
    assert 'id="pwSessionPackaging"' not in html


def test_workspace_lote_mostra_pendencias_custo_registrado_e_envases_corretos(app, client, monkeypatch):
    from datetime import datetime
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao

    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Resumo Lote")
        recipe = MashRecipe(name="Receita Resumo Lote")
        db.session.add_all([plant, recipe])
        db.session.flush()
        pending = BrewSession(name="Lote Pendente Resumo", plant_id=plant.id, recipe_id=recipe.id)
        confirmed = BrewSession(name="Lote Confirmado Resumo", plant_id=plant.id, recipe_id=recipe.id,
                                insumos_baixados_em=datetime(2026, 1, 1), custo_total_insumos=123.45)
        db.session.add_all([pending, confirmed])
        db.session.flush()
        db.session.add(RecipeIngredient(recipe_id=recipe.id, descricao_origem="Malte Pendente Resumo",
                                       tipo_ingrediente="fermentable", quantidade=2, unidade_medida="kg", status_resolucao="pendente"))
        included = Envase(lote_id=confirmed.id, tipo_envase="Garrafa do Lote", quantidade_litros=20)
        excluded = Envase(lote_id=pending.id, tipo_envase="Envase de Outro Lote", quantidade_litros=10)
        deleted = Envase(lote_id=confirmed.id, tipo_envase="Envase Apagado", is_deleted=True)
        db.session.add_all([included, excluded, deleted])
        db.session.commit()
        plant_id, pending_id, confirmed_id = plant.id, pending.id, confirmed.id
        movement_count = Movimentacao.query.count()
    url = f"/brewstation/plant-workspace/{plant_id}/tab/sessions"
    html = client.get(url, query_string={"session_id": pending_id}).data.decode("utf-8")
    assert "Malte Pendente Resumo" in html and "1 pendência(s)" in html
    assert "Estimativa incompleta" in html
    assert 'id="pwSessionEditForm"' in html
    from addons.addon_brewstation.features.feature_mash_control.controller import plant_workspace
    def no_reestimate(*args):
        raise AssertionError("Custo confirmado não deve ser recalculado")
    monkeypatch.setattr(plant_workspace, "conferir_ingredientes", no_reestimate)
    monkeypatch.setattr(plant_workspace, "calcular_custo_insumos_receita", no_reestimate)
    html = client.get(url, query_string={"session_id": confirmed_id}).data.decode("utf-8")
    assert "Custo registrado dos insumos" in html and "R$ 123.45" in html
    assert "Garrafa do Lote" in html
    assert "Envase de Outro Lote" not in html and "Envase Apagado" not in html
    assert f"/brewstation/precificacao-envase/?lote_id={confirmed_id}" in html
    with app.app_context():
        assert Movimentacao.query.count() == movement_count
        assert db.session.get(BrewSession, pending_id).insumos_baixados_em is None


def test_precificacao_abre_com_lote_e_retorna_para_mesma_sessao(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Atalho Precificação")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Lote Atalho Precificação", plant_id=plant.id)
        deleted = BrewSession(name="Lote Apagado Precificação", plant_id=plant.id, is_deleted=True)
        db.session.add_all([session, deleted])
        db.session.commit()
        plant_id, session_id, deleted_id = plant.id, session.id, deleted.id
    url = "/brewstation/precificacao-envase/"
    response = client.get(url, query_string={"lote_id": session_id})
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert f'id="pcLoteId" value="{session_id}"' in html
    assert 'value="Lote Atalho Precificação"' in html
    assert "Voltar à sessão na planta" in html
    for invalid in (deleted_id, "inválido", "999999"):
        assert client.get(url, query_string={"lote_id": invalid}).status_code == 404
    assert client.get(url).status_code == 200
    shell = client.get(f"/brewstation/plant-workspace/{plant_id}?tab=sessions&session_id={session_id}").data.decode("utf-8")
    assert f'const initialSessionId = "{session_id}";' in shell


def test_workspace_reconhece_alarme_registra_operador_sem_duplicar_log(app, client):
    from addons.addon_estoque.root.model.movimentacao import Movimentacao

    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Reconhecimento")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Sessão Reconhecimento", plant_id=plant.id, status="paused")
        db.session.add(session)
        db.session.flush()
        alarm = BrewSessionAlarm(session_id=session.id, severity="high", message="Alarme Reconhecer Workspace")
        second_user = User(username="operador_reconhecimento", email="reconhecimento@test.local", nome="Operador",
                           nome_completo="Operador", celular="0", is_admin=True, is_active=True)
        second_user.set_password("operador123")
        db.session.add_all([alarm, second_user])
        db.session.commit()
        plant_id, session_id, alarm_id = plant.id, session.id, alarm.id
        admin_id = User.query.filter_by(username="admin").one().id
        second_user_id = second_user.id
        movement_count = Movimentacao.query.count()
    url = f"/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/alarms/{alarm_id}/acknowledge"
    headers = {"X-Requested-With": "XMLHttpRequest"}
    response = client.post(url, data={"acknowledged_by": second_user_id, "severity": "low"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["ja_reconhecido"] is False
    with app.app_context():
        saved = db.session.get(BrewSessionAlarm, alarm_id)
        assert saved.is_acknowledged is True and saved.acknowledged_by == admin_id
        acknowledged_at = saved.acknowledged_at
        assert acknowledged_at is not None
        assert saved.severity == "high" and saved.message == "Alarme Reconhecer Workspace"
        log = BrewSessionLog.query.filter_by(session_id=session_id).one()
        assert log.source == "user"
        assert log.detail_json == {"action": "acknowledge_alarm", "alarm_id": alarm_id, "user_id": admin_id}
        assert db.session.get(BrewSession, session_id).status == "paused"
        assert Movimentacao.query.count() == movement_count
    client.post("/api/auth/login", json={"username": "operador_reconhecimento", "password": "operador123"})
    response = client.post(url, headers=headers)
    assert response.status_code == 200 and response.get_json()["ja_reconhecido"] is True
    with app.app_context():
        saved = db.session.get(BrewSessionAlarm, alarm_id)
        assert saved.acknowledged_by == admin_id and saved.acknowledged_at == acknowledged_at
        assert BrewSessionLog.query.filter_by(session_id=session_id).count() == 1
    assert client.get(url).status_code == 405


def test_workspace_alarme_verifica_sessao_planta_lixeira_e_permissao(app, client, monkeypatch):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Proteção Alarmes")
        other = BrewPlant(name="Outra Planta Proteção Alarmes")
        db.session.add_all([plant, other])
        db.session.flush()
        session = BrewSession(name="Sessão Alarmes Protegida", plant_id=plant.id)
        other_session = BrewSession(name="Outra Sessão Alarmes", plant_id=plant.id)
        db.session.add_all([session, other_session])
        db.session.flush()
        alarm = BrewSessionAlarm(session_id=session.id, message="Alarme Protegido")
        deleted = BrewSessionAlarm(session_id=session.id, message="Alarme Apagado", is_deleted=True)
        db.session.add_all([alarm, deleted])
        db.session.commit()
        plant_id, other_id, session_id, other_session_id, alarm_id, deleted_id = plant.id, other.id, session.id, other_session.id, alarm.id, deleted.id
    headers = {"X-Requested-With": "XMLHttpRequest"}
    for pid, sid, aid in ((other_id, session_id, alarm_id), (plant_id, other_session_id, alarm_id), (plant_id, session_id, deleted_id)):
        assert client.post(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/alarms/{aid}/acknowledge", headers=headers).status_code == 404
    url = f"/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/alarms/{alarm_id}/acknowledge"
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != "brew_session_alarms.update")
    assert client.post(url, headers=headers).status_code == 403
    html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={session_id}").data.decode("utf-8")
    assert 'class="pw-alarm-ack-form' not in html
    with app.app_context():
        assert db.session.get(BrewSessionAlarm, alarm_id).is_acknowledged is False
        assert BrewSessionLog.query.filter_by(session_id=session_id).count() == 0


def test_workspace_falha_ao_salvar_reconhecimento_desfaz_estado_e_log(app, client, monkeypatch):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Rollback Alarmes")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Sessão Rollback Alarmes", plant_id=plant.id)
        db.session.add(session)
        db.session.flush()
        alarm = BrewSessionAlarm(session_id=session.id, message="Alarme Rollback")
        db.session.add(alarm)
        db.session.commit()
        plant_id, session_id, alarm_id = plant.id, session.id, alarm.id
    def fail_commit():
        raise RuntimeError("Falha simulada ao salvar reconhecimento")
    with monkeypatch.context() as scoped:
        scoped.setattr(db.session, "commit", fail_commit)
        response = client.post(f"/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/alarms/{alarm_id}/acknowledge",
                               headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 500 and response.get_json()["ok"] is False
    with app.app_context():
        saved = db.session.get(BrewSessionAlarm, alarm_id)
        assert saved.is_acknowledged is False and saved.acknowledged_at is None and saved.acknowledged_by is None
        assert BrewSessionLog.query.filter_by(session_id=session_id).count() == 0


def test_workspace_filtra_alarmes_preserva_sessao_e_conta_pendentes(app, client):
    import html as html_module
    import re
    from urllib.parse import parse_qs, urlsplit

    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Filtro Alarmes")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Sessão Filtro Alarmes", plant_id=plant.id)
        db.session.add(session)
        db.session.flush()
        db.session.add_all([BrewSessionAlarm(session_id=session.id, message=f"Alarme Filtro Pendente {i:02d}") for i in range(21)])
        db.session.add(BrewSessionAlarm(session_id=session.id, message="Alarme Filtro Reconhecido", is_acknowledged=True))
        db.session.add(BrewSessionAlarm(session_id=session.id, message="Alarme Filtro Apagado", is_deleted=True))
        db.session.commit()
        plant_id, session_id = plant.id, session.id
    url = f"/brewstation/plant-workspace/{plant_id}/tab/sessions"
    response = client.get(url, query_string={"session_id": session_id, "alarm_state": "pending"})
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "21 pendente(s)" in html
    assert "Alarme Filtro Reconhecido" not in html and "Alarme Filtro Apagado" not in html
    assert 'id="pwAlarmState" name="alarm_state" class="form-select' in html
    links = re.findall(r'href="([^"]+)"[^>]*data-workspace-history-link', html)
    alarm_link = next(html_module.unescape(link) for link in links if "alarms_page=2" in link)
    query = parse_qs(urlsplit(alarm_link).query)
    assert query["alarm_state"] == ["pending"] and query["session_id"] == [str(session_id)]
    next_html = client.get(alarm_link).data.decode("utf-8")
    assert "Alarme Filtro Pendente 00" in next_html
    html = client.get(url, query_string={"session_id": session_id, "alarm_state": "acknowledged"}).data.decode("utf-8")
    assert "Alarme Filtro Reconhecido" in html and "Alarme Filtro Pendente" not in html
    assert 'class="pw-alarm-ack-form' not in html
    assert client.get(url, query_string={"alarm_state": "inválido"}).status_code == 400


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
    assert 'data-weakref-source="brew_plants"' in html
    assert f'name="plant_id" value="{plant_id}"' in html
    assert 'value="Planta Pre Selecionada"' in html


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
    assert resp.status_code == 404
    html = resp.data.decode("utf-8")
    assert "Receita não encontrada" in html
    assert "<html" not in html.lower()


def test_tab_recipe_planta_inexistente_devolve_fragmento_de_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/plant-workspace/999999/tab/recipe")
    assert resp.status_code == 404
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


def test_workspace_revisao_abre_nova_receita_e_preserva_vinculo_do_lote(app, client):
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
    _login_admin(app, client)
    pid, rid, iid, _ = _workspace_sanitation_data(app)
    with app.app_context():
        recipe = db.session.get(MashRecipe, rid)
        recipe.volume_planejado_litros = 20
        from datetime import datetime, timezone
        session = BrewSession(name="Lote da receita anterior", recipe_id=rid, plant_id=pid,
                              status="completed", insumos_baixados_em=datetime.now(timezone.utc), custo_total_insumos=80)
        db.session.add(session)
        db.session.commit()
        sid = session.id
        before = session.to_dict()
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'id="pwRecipeRevisionForm"' in html and 'class="pw-ingredient-data-form' not in html
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/revise",
                           data={"observacao": "Planejar próxima brassagem", "recipe_id": "99999"},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200 and response.get_json()["ok"]
    new_id = response.get_json()["recipe_id"]
    assert new_id != rid
    with app.app_context():
        assert db.session.get(BrewSession, sid).to_dict() == before
        history = RecipeHistory.query.filter_by(recipe_id=new_id).first()
        assert history.alterado_por == User.query.filter_by(username="admin").first().id
        assert history.observacao == "Planejar próxima brassagem"
        assert history.get_snapshot()["source_recipe_id"] == rid
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={new_id}").data.decode()
    assert 'class="pw-ingredient-data-form' in html and 'data-weakref-source="unidades_catalogo"' in html
    assert 'data-weakref-value-field="codigo"' in html and '<datalist' not in html
    assert 'name="etapa" class="form-select"' in html
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/revise")
    assert response.status_code == 302 and f"recipe_id={new_id}" not in response.location
    assert "tab=recipe" in response.location and "recipe_id=" in response.location


@pytest.mark.parametrize("code,action", [("mash_recipes.create", "revise"),
    ("recipe_steps.list", "revise"), ("recipe_ingredients.update", "edit-data")])
def test_workspace_revisao_edicao_respeita_rbac(app, client, monkeypatch, code, action):
    _login_admin(app, client)
    pid, rid, iid, _ = _workspace_sanitation_data(app)
    monkeypatch.setattr(User, "has_permission", lambda self, permission: permission != code)
    base = f"/brewstation/plant-workspace/{pid}/recipes/{rid}"
    path = f"{base}/revise" if action == "revise" else f"{base}/ingredients/{iid}/edit-data"
    assert client.post(path, data={"quantidade": 99}, headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 403
    if code != "recipe_steps.list":
        html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
        assert ('id="pwRecipeRevisionForm"' if action == "revise" else 'class="pw-ingredient-data-form') not in html
    with app.app_context():
        assert MashRecipe.query.count() == 1 and db.session.get(RecipeIngredient, iid).quantidade == 5


def test_workspace_edicao_dados_ignora_campos_fora_do_escopo_e_registra_operador(app, client):
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    with app.app_context():
        if not UnidadeCatalogo.query.filter_by(codigo="KG").first():
            db.session.add(UnidadeCatalogo(codigo="KG", descricao="Quilograma", dimensao="massa"))
            db.session.commit()
        before = db.session.get(RecipeIngredient, iid).to_dict()
        ledger_before = Movimentacao.query.count()
    path = f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/edit-data"
    response = client.post(path, data={"quantidade": "7.5", "unidade_medida": "KG", "etapa": "mostura",
        "recipe_id": 99999, "material_id": mid, "status_resolucao": "ignorado", "descricao_origem": "Alterada",
        "usuario_id": 99999}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    with app.app_context():
        ing = db.session.get(RecipeIngredient, iid)
        assert ing.quantidade == 7.5 and ing.unidade_medida == "KG"
        for key in ("recipe_id", "material_id", "status_resolucao", "descricao_origem"):
            assert ing.to_dict()[key] == before[key]
        history = RecipeHistory.query.filter_by(recipe_id=rid).first()
        assert history.alterado_por == User.query.filter_by(username="admin").first().id
        assert Movimentacao.query.count() == ledger_before
    assert client.post(path, data={"quantidade": "NaN"}, headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 400


@pytest.mark.parametrize("context", ["plant", "recipe", "ingredient", "used", "foreign"])
def test_workspace_edicao_dados_rejeita_contexto_e_uso(app, client, context):
    _login_admin(app, client)
    pid, rid, iid, _ = _workspace_sanitation_data(app)
    with app.app_context():
        if context == "used":
            db.session.add(BrewSession(name="Lote na lixeira", recipe_id=rid, plant_id=pid, is_deleted=True))
        elif context == "foreign":
            other = MashRecipe(name="Outra receita para teste", versao=1, origem_receita="Manual")
            db.session.add(other)
            db.session.flush()
            ing = db.session.get(RecipeIngredient, iid)
            ing.recipe_id = other.id
        else:
            model, identity = {"plant": (BrewPlant, pid), "recipe": (MashRecipe, rid), "ingredient": (RecipeIngredient, iid)}[context]
            db.session.get(model, identity).is_deleted = True
        db.session.commit()
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/edit-data",
                           data={"quantidade": 99}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == (409 if context == "used" else 404)
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).quantidade == 5


def test_workspace_consultar_receita_usada_nao_sincroniza_alertas(app, client):
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
    _login_admin(app, client)
    pid, rid, iid, _ = _workspace_sanitation_data(app)
    with app.app_context():
        ing = db.session.get(RecipeIngredient, iid)
        ing.tipo_ingrediente, ing.etapa, ing.tempo_adicao_min = "lupulo", "fervura", 10
        db.session.add_all([BrewSession(name="Receita protegida", recipe_id=rid, plant_id=pid),
                           RecipeStep(recipe_id=rid, step_type="boil", tempo_min=60)])
        db.session.commit()
        before = [row.to_dict() for row in RecipeStep.query.filter_by(recipe_id=rid).all()]
    assert client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").status_code == 200
    assert client.get(f"/brewstation/recipe-timeline/{rid}").status_code == 200
    with app.app_context():
        assert [row.to_dict() for row in RecipeStep.query.filter_by(recipe_id=rid).all()] == before


@pytest.mark.parametrize("action", ["revise", "edit-data"])
def test_workspace_revisao_edicao_falha_rollback_e_mensagem_generica(app, client, monkeypatch, action):
    _login_admin(app, client)
    pid, rid, iid, _ = _workspace_sanitation_data(app)
    def fail():
        raise RuntimeError("detalhe interno sensível")
    with app.app_context():
        monkeypatch.setattr(db.session, "commit", fail)
    base = f"/brewstation/plant-workspace/{pid}/recipes/{rid}"
    path = f"{base}/revise" if action == "revise" else f"{base}/ingredients/{iid}/edit-data"
    response = client.post(path, data={"quantidade": 99}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 500 and "sensível" not in response.get_json()["error"]
    with app.app_context():
        assert MashRecipe.query.count() == 1 and db.session.get(RecipeIngredient, iid).quantidade == 5


@pytest.mark.parametrize("context", ["plant", "recipe"])
def test_workspace_revisao_rejeita_registros_apagados(app, client, context):
    _login_admin(app, client)
    pid, rid, _, _ = _workspace_sanitation_data(app)
    with app.app_context():
        db.session.get(BrewPlant if context == "plant" else MashRecipe, pid if context == "plant" else rid).is_deleted = True
        db.session.commit()
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/revise",
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 404
    with app.app_context():
        assert MashRecipe.query.count() == 1


def test_workspace_unidade_catalogo_combo_busca_codigo_pela_api(app, client):
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    _login_admin(app, client)
    with app.app_context():
        if not UnidadeCatalogo.query.filter_by(codigo="PCT").first():
            db.session.add(UnidadeCatalogo(codigo="PCT", descricao="Pacote", dimensao="embalagem"))
            db.session.commit()
    response = client.get("/api/options/unidades_catalogo?search=PCT&value_field=codigo")
    assert response.status_code == 200
    assert any(row["id"] == "PCT" for row in response.get_json()["results"])


def _workspace_preparation_data(app):
    pid, rid, _, mid = _workspace_sanitation_data(app)
    from addons.addon_estoque.root.model.material import Material
    with app.app_context():
        material = db.session.get(Material, mid)
        material.volume_real, material.unidade_medida_volume_real = 500, "ML"
        session = BrewSession(name="Histórico para preparar envase", recipe_id=rid, plant_id=pid, status="completed")
        db.session.add(session)
        db.session.commit()
        return pid, session.id, mid


def test_workspace_preparacao_no_lote_historico_preserva_selecao_e_nao_grava(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}").data.decode()
    assert 'id="pwEnvasePreparationForm"' in html and 'data-weakref-source="materials"' in html
    assert 'Consultar prévia de embalagens' in html and '<datalist' not in html
    assert f'/sessions/{sid}/prepare-envase' in html
    with app.app_context():
        before = db.session.get(BrewSession, sid).to_dict()
        count = Movimentacao.query.count()
    path = f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase"
    for _ in range(2):
        result = client.get(path, query_string={"material_resultante_id": mid, "quantidade_litros": 10}).get_json()
        assert result["ok"] and '20 unidade(s)' in result["html"]
        assert 'estimativa parcial' in result["html"] and 'ingredientes ainda não confirmados' in result["html"]
        assert 'não gera um envase' in result["html"]
    with app.app_context():
        assert db.session.get(BrewSession, sid).to_dict() == before
        assert Movimentacao.query.count() == count and Envase.query.count() == 0
    assert client.post(path).status_code == 405


@pytest.mark.parametrize("permission", ["brew_sessions.list", "envases.list", "envases.create"])
def test_workspace_preparacao_respeita_permissoes(app, client, monkeypatch, permission):
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != permission)
    response = client.get(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase",
                          query_string={"material_resultante_id": mid, "quantidade_litros": 10})
    assert response.status_code == 403
    if permission != "brew_sessions.list":
        html = client.get(f"/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}").data.decode()
        assert 'id="pwEnvasePreparationForm"' not in html


@pytest.mark.parametrize("context", ["plant", "session", "foreign", "missing"])
def test_workspace_preparacao_rejeita_contexto_sem_escolher_outro_lote(app, client, context):
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    with app.app_context():
        if context == "plant":
            db.session.get(BrewPlant, pid).is_deleted = True
        elif context == "session":
            db.session.get(BrewSession, sid).is_deleted = True
        elif context == "foreign":
            other = BrewPlant(name="Planta estrangeira de envase")
            db.session.add(other)
            db.session.flush()
            db.session.get(BrewSession, sid).plant_id = other.id
        else:
            sid = 999999
        db.session.commit()
    response = client.get(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase",
                          query_string={"material_resultante_id": mid, "quantidade_litros": 10})
    assert response.status_code == 404 and not response.get_json()["ok"]


@pytest.mark.parametrize("liters", ["", "abc", "0", "-1", "NaN", "Infinity"])
def test_workspace_preparacao_rejeita_litros_invalidos(app, client, liters):
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    response = client.get(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase",
                          query_string={"material_resultante_id": mid, "quantidade_litros": liters})
    assert response.status_code == 400 and not response.get_json()["ok"]


def test_workspace_preparacao_falha_mensagem_generica(app, client, monkeypatch):
    from addons.addon_brewstation.features.feature_envase.services import envase_preparation_service
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    def fail(*args):
        raise RuntimeError("detalhe interno sensível")
    monkeypatch.setattr(envase_preparation_service, "preparar_envase", fail)
    response = client.get(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase",
                          query_string={"material_resultante_id": mid, "quantidade_litros": 10})
    assert response.status_code == 500 and 'sensível' not in response.get_json()["error"]


def _workspace_envase_confirmation(client, pid, sid, mid, **kwargs):
    response = client.get(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/prepare-envase",
                          query_string={"material_resultante_id": mid, "quantidade_litros": 2, **kwargs})
    assert response.status_code == 200
    class TokenParser(HTMLParser):
        token = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "input" and attrs.get("name") == "confirmation_token":
                self.token = attrs["value"]
    parser = TokenParser()
    parser.feed(response.get_json()["html"])
    assert parser.token
    return parser.token


def test_workspace_envase_registra_repete_e_retorna_mesmo_lote_historico(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    # Material da fixture é também ingrediente: resolvê-lo não pode mudar a receita.
    with app.app_context():
        ing = RecipeIngredient.query.filter_by(recipe_id=db.session.get(BrewSession, sid).recipe_id).one()
        ing.material_id, ing.status_resolucao, ing.unidade_medida = mid, "resolvido", "kg"
        from addons.addon_estoque.root.services import estoque_service
        from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
        db.session.add(MaterialUnidade(material_id=mid, unidade="kg", fator_para_base=1, is_unidade_base=True))
        db.session.flush()
        estoque_service.registrar_movimentacao(mid, "entrada", 50, custo_unitario=2)
        db.session.commit()
        before_status = db.session.get(BrewSession, sid).status
    token = _workspace_envase_confirmation(client, pid, sid, mid, data_envase="2026-10-01", tipo_envase="garrafa")
    path = f"/brewstation/plant-workspace/{pid}/sessions/{sid}/register-envase"
    result = client.post(path, data={"confirmation_token": token})
    assert result.status_code == 200
    payload = result.get_json()
    assert payload["ok"] and not payload["ja_registrado"]
    assert f"session_id={sid}" in payload["url"]
    with app.app_context():
        count = Movimentacao.query.count()
        recorded_cost = db.session.get(BrewSession, sid).custo_total_insumos
        envase = db.session.get(Envase, payload["envase_id"])
        assert envase.lote_id == sid and envase.tipo_envase == "garrafa"
        assert envase.data_envase.isoformat() == "2026-10-01"
    repeated = client.post(path, data={"confirmation_token": token}).get_json()
    assert repeated["ja_registrado"] and repeated["envase_id"] == payload["envase_id"]
    with app.app_context():
        assert Envase.query.count() == 1 and Movimentacao.query.count() == count
        session = db.session.get(BrewSession, sid)
        assert session.custo_total_insumos == recorded_cost and session.status == before_status


@pytest.mark.parametrize("permission", ["envases.create", "envases.list", "brew_sessions.list", "brew_sessions.update"])
def test_workspace_envase_rejeita_permissao_sem_movimentar(app, client, monkeypatch, permission):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    token = _workspace_envase_confirmation(client, pid, sid, mid)
    with app.app_context():
        before = Movimentacao.query.count()
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != permission)
    response = client.post(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/register-envase",
                           data={"confirmation_token": token})
    assert response.status_code == 403
    with app.app_context():
        assert Envase.query.count() == 0 and Movimentacao.query.count() == before


def test_workspace_envase_token_invalidado_e_contexto_estrangeiro(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    token = _workspace_envase_confirmation(client, pid, sid, mid)
    path = f"/brewstation/plant-workspace/{pid}/sessions/{sid}/register-envase"
    assert client.post(path, data={"confirmation_token": token + "alterado"}).status_code == 400
    with app.app_context():
        other = BrewPlant(name="Outra planta registro envase")
        db.session.add(other); db.session.flush()
        other_session = BrewSession(name="Outro lote registro envase", plant_id=other.id)
        db.session.add(other_session); db.session.commit()
        other_pid, other_sid = other.id, other_session.id
    foreign = client.post(f"/brewstation/plant-workspace/{other_pid}/sessions/{other_sid}/register-envase",
                          data={"confirmation_token": token})
    assert foreign.status_code == 400
    assert client.post(f"/brewstation/plant-workspace/{other_pid}/sessions/{sid}/register-envase",
                       data={"confirmation_token": token}).status_code == 404
    with app.app_context():
        assert Envase.query.count() == 0


def test_workspace_envase_pendencias_apos_previa_rollback(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    token = _workspace_envase_confirmation(client, pid, sid, mid)
    with app.app_context():
        before = Movimentacao.query.count()
    response = client.post(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/register-envase",
                           data={"confirmation_token": token})
    assert response.status_code == 409
    with app.app_context():
        assert Envase.query.count() == 0 and Movimentacao.query.count() == before
        assert db.session.get(BrewSession, sid).insumos_baixados_em is None


def test_workspace_envase_insumos_confirmados_nao_exige_update_nem_recalcula(app, client, monkeypatch):
    from datetime import datetime, timezone
    _login_admin(app, client)
    pid, sid, mid = _workspace_preparation_data(app)
    with app.app_context():
        session = db.session.get(BrewSession, sid)
        session.insumos_baixados_em = datetime.now(timezone.utc)
        session.custo_total_insumos = 99
        db.session.commit()
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != "brew_sessions.update")
    token = _workspace_envase_confirmation(client, pid, sid, mid)
    response = client.post(f"/brewstation/plant-workspace/{pid}/sessions/{sid}/register-envase",
                           data={"confirmation_token": token})
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(BrewSession, sid).custo_total_insumos == 99


# 2B: histórico e estorno no lote, sem baixa em consultas.
def _workspace_reverse_data(app):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_estoque.root.services import estoque_service
    pid, _, _, mid = _workspace_sanitation_data(app)
    with app.app_context():
        session = BrewSession(name='Lote histórico para estorno', plant_id=pid, status='completed', custo_total_insumos=12)
        db.session.add(session)
        db.session.flush()
        estoque_service.registrar_movimentacao(mid, 'entrada', 10, custo_unitario=2)
        result = estoque_service.registrar_movimentacao(mid, 'saida', 2, custo_unitario=2)
        envase = Envase(lote_id=session.id, material_resultante_id=mid, quantidade_litros=1,
                        componentes_snapshot=[{'material_componente_id': mid, 'quantidade_total': 2,
                            'custo_medio': 2, 'custo_linha': 4, 'movimentacao_id': result['movimentacao']['id']}])
        db.session.add(envase)
        db.session.commit()
        return pid, session.id, envase.id, mid


def test_workspace_envase_detalhes_estorna_repete_preserva_lote_e_historico(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_estoque.root.services import material_lookup
    _login_admin(app, client)
    pid, sid, eid, mid = _workspace_reverse_data(app)
    tab = f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id={eid}'
    path = f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse'
    with app.app_context():
        before = db.session.get(BrewSession, sid).to_dict()
        snapshot = db.session.get(Envase, eid).componentes_snapshot
        count = Movimentacao.query.count()
    for _ in range(2):
        html = client.get(tab).data.decode()
        assert f'Detalhes do envase #{eid}' in html and 'pwEnvaseReverseReason' in html
        assert 'confirm_reverse_envase' in html and 'data-workspace-history-link' in html
    with app.app_context():
        assert Movimentacao.query.count() == count
    response = client.post(path, data={'motivo': 'Embalagem danificada'})
    assert response.status_code == 200 and f'envase_id={eid}' in response.get_json()['reload_url']
    with app.app_context():
        envase = db.session.get(Envase, eid)
        first = (envase.cancelado_em, envase.cancelado_por_id, envase.motivo_cancelamento, envase.estorno_snapshot)
        assert envase.componentes_snapshot == snapshot
        assert db.session.get(BrewSession, sid).to_dict() == before
        assert Movimentacao.query.count() == count + 1
        assert material_lookup.get_saldo(mid)['quantidade_atual'] == 10
        assert BrewSessionLog.query.filter_by(session_id=sid, source='envase').count() == 1
    assert client.post(path, data={'motivo': 'Segunda tentativa'}).status_code == 400
    html = client.get(tab).data.decode()
    assert 'Estorno registrado' in html and 'pwEnvaseReverseReason' not in html
    with app.app_context():
        envase = db.session.get(Envase, eid)
        assert (envase.cancelado_em, envase.cancelado_por_id, envase.motivo_cancelamento, envase.estorno_snapshot) == first
        assert Movimentacao.query.count() == count + 1


@pytest.mark.parametrize('permission', ['brew_sessions.list', 'envases.list', 'envases.detail', 'envases.update'])
def test_workspace_estorno_respeita_permissoes(app, client, monkeypatch, permission):
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, eid, _ = _workspace_reverse_data(app)
    with app.app_context():
        count = Movimentacao.query.count()
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != permission)
    assert client.post(f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse', data={'motivo': 'Teste'}).status_code == 403
    if permission == 'envases.update':
        assert 'pwEnvaseReverseReason' not in client.get(f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id={eid}').data.decode()
    else:
        assert client.get(f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id={eid}').status_code == 403
    with app.app_context():
        assert Movimentacao.query.count() == count


@pytest.mark.parametrize('context', ['plant', 'session', 'envase', 'foreign', 'other_lot', 'missing'])
def test_workspace_envase_estorno_valida_pertencimento_e_apagados(app, client, context):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    _login_admin(app, client)
    pid, sid, eid, _ = _workspace_reverse_data(app)
    with app.app_context():
        if context == 'plant': db.session.get(BrewPlant, pid).is_deleted = True
        elif context == 'session': db.session.get(BrewSession, sid).is_deleted = True
        elif context == 'envase': db.session.get(Envase, eid).is_deleted = True
        elif context == 'foreign':
            other = BrewPlant(name='Planta estrangeira'); db.session.add(other); db.session.flush()
            db.session.get(BrewSession, sid).plant_id = other.id
        elif context == 'other_lot':
            other = BrewSession(name='Outro lote', plant_id=pid); db.session.add(other); db.session.flush()
            db.session.get(Envase, eid).lote_id = other.id
        else: eid = 999999
        db.session.commit()
    assert client.get(f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id={eid}').status_code == 404
    assert client.post(f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse', data={'motivo': 'Teste'}).status_code == 404


@pytest.mark.parametrize('reason', ['', '   ', 'x' * 1001])
def test_workspace_envase_estorno_exige_motivo(app, client, reason):
    _login_admin(app, client)
    pid, sid, eid, _ = _workspace_reverse_data(app)
    assert client.post(f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse', data={'motivo': reason}).status_code == 400


def test_workspace_envase_estorno_falha_log_desfaz_devolucao(app, client, monkeypatch):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    _login_admin(app, client)
    pid, sid, eid, mid = _workspace_reverse_data(app)
    with app.app_context():
        count = Movimentacao.query.count()
        original_add = db.session.add
        def fail_log(obj, *args, **kwargs):
            if isinstance(obj, BrewSessionLog): raise RuntimeError('detalhe interno sensível')
            return original_add(obj, *args, **kwargs)
        monkeypatch.setattr(db.session, 'add', fail_log)
    response = client.post(f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse', data={'motivo': 'Teste'})
    assert response.status_code == 500 and 'sensível' not in response.get_json()['error']
    with app.app_context():
        envase = db.session.get(Envase, eid)
        assert envase.status == 'registrado' and envase.estorno_snapshot is None and envase.cancelado_em is None
        assert Movimentacao.query.count() == count
        from addons.addon_estoque.root.services import material_lookup
        assert material_lookup.get_saldo(mid)['quantidade_atual'] == 8
        assert BrewSessionLog.query.filter_by(session_id=sid).count() == 0


def test_workspace_envase_legado_sem_snapshot_so_consulta(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    _login_admin(app, client)
    pid, sid, eid, _ = _workspace_reverse_data(app)
    with app.app_context():
        db.session.get(Envase, eid).componentes_snapshot = None
        db.session.commit()
    html = client.get(f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id={eid}').data.decode()
    assert 'reconciliação manual' in html and 'pwEnvaseReverseReason' not in html
    assert client.post(f'/brewstation/plant-workspace/{pid}/sessions/{sid}/envases/{eid}/reverse', data={'motivo': 'Legado'}).status_code == 400
    assert client.get(f'/brewstation/plant-workspace/{pid}/tab/sessions?session_id={sid}&envase_id=abc').status_code == 404
    assert client.get(f'/brewstation/plant-workspace/{pid}?tab=sessions&session_id={sid}&envase_id={eid}').status_code == 200


def test_precificacao_contexto_envase_preserva_retorno_e_rejeita_estrangeiro(app, client):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    _login_admin(app, client)
    pid, sid, eid, _ = _workspace_reverse_data(app)
    url = f'/brewstation/precificacao-envase/?lote_id={sid}&envase_id={eid}'
    html = client.get(url).data.decode()
    assert f'id="pcEnvaseId" value="{eid}"' in html
    assert f'envase_id={eid}' in html and 'pcCostBasis' in html
    assert 'data-weakref-source="envases"' in html and 'pcCostScope' in html
    assert client.get(f'/brewstation/precificacao-envase/?lote_id={sid}&envase_id=abc').status_code == 404
    with app.app_context():
        other = BrewSession(name='Outro lote precificação'); db.session.add(other); db.session.flush()
        db.session.get(Envase, eid).lote_id = other.id
        db.session.commit()
    assert client.get(url).status_code == 404
    with app.app_context():
        item = db.session.get(Envase, eid)
        item.lote_id, item.status = sid, 'cancelado'
        db.session.commit()
    assert client.get(url).status_code == 404


def _appearance_layouts(app):
    with app.app_context():
        plant = BrewPlant(name='Planta aparência')
        other = BrewPlant(name='Outra aparência')
        db.session.add_all([plant, other]); db.session.flush()
        layouts = [DashboardLayout(name='Padrão anterior', plant_id=plant.id, is_default=True),
                   DashboardLayout(name='Painel aparência', plant_id=plant.id, layout_data='{"original":true}', is_standby_enabled=True, standby_duration_seconds=45),
                   DashboardLayout(name='Padrão externo', plant_id=other.id, is_default=True),
                   DashboardLayout(name='Padrão apagado', plant_id=plant.id, is_default=True, is_deleted=True)]
        db.session.add_all(layouts); db.session.flush()
        widget = DashboardWidget(layout_id=layouts[1].id, widget_type='text', config_json={'content': 'Intacto'})
        db.session.add(widget); db.session.commit()
        return plant.id, other.id, [row.id for row in layouts], widget.id


def test_dashboard_aparencia_padrao_preserva_widgets_outros_campos_e_escopo(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    url = f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/appearance'
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    payload = {'background_color': '#123456', 'background_image_url': '/static/img/fundo.png', 'is_default': 'on',
               'plant_id': other, 'layout_data': 'alterado', 'standby_duration_seconds': '0'}
    assert client.post(url, data=payload, headers=headers).status_code == 200
    with app.app_context():
        selected = db.session.get(DashboardLayout, ids[1])
        assert selected.is_default and selected.background_color == '#123456'
        assert selected.background_image_url == '/static/img/fundo.png'
        assert selected.plant_id == plant and selected.layout_data == '{"original":true}'
        assert selected.is_standby_enabled and selected.standby_duration_seconds == 45
        assert not db.session.get(DashboardLayout, ids[0]).is_default
        assert db.session.get(DashboardLayout, ids[2]).is_default
        assert db.session.get(DashboardLayout, ids[3]).is_default
        assert db.session.get(DashboardWidget, widget).config_json == {'content': 'Intacto'}
    html = client.get(f'/brewstation/plant-workspace/{plant}/tab/dashboard').get_data(as_text=True)
    assert '<h1>Painel aparência</h1>' in html
    assert 'id="dbBackgroundImage"' in html and 'pointer-events:none; z-index:0' in html
    assert 'pwLayoutAppearanceForm' in html
    full = client.get(f'/brewstation/dashboards/{ids[1]}/view').get_data(as_text=True)
    assert 'id="dbBackgroundImage"' in full
    assert 'pwLayoutAppearanceForm' not in full
    assert client.post(url, data={**payload, 'is_default': '', 'background_image_url': ''}, headers=headers).status_code == 200
    with app.app_context():
        selected = db.session.get(DashboardLayout, ids[1])
        assert not selected.is_default and selected.background_image_url is None
    html = client.get(f'/brewstation/plant-workspace/{plant}/tab/dashboard').get_data(as_text=True)
    assert '<h1>Padrão anterior</h1>' in html


@pytest.mark.parametrize('field,value', [('background_color', 'red;display:none'), ('background_color', '#12345'),
    ('background_image_url', 'javascript:alert(1)'), ('background_image_url', '//outside/image.png'),
    ('background_image_url', 'data:image/svg+xml,xxx'), ('background_image_url', 'https://host/x\n.png')])
def test_dashboard_aparencia_rejeita_dados_invalidos_sem_alterar_padrao(app, client, field, value):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    payload = {'background_color': '#abc', 'background_image_url': '', 'is_default': 'on', field: value}
    response = client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/appearance',
                           data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[0]).is_default
        assert not db.session.get(DashboardLayout, ids[1]).is_default


def test_dashboard_aparencia_recusa_externo_apagado_e_sem_permissao(app, client, monkeypatch):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    payload = {'background_color': '#abc'}
    for layout in (ids[2], ids[3], 999999):
        assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{layout}/appearance', data=payload,
                           headers={'X-Requested-With': 'XMLHttpRequest'}).status_code == 404
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'dashboard_layouts.update')
    assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/appearance', data=payload).status_code == 403


def test_dashboard_aparencia_rollback_preserva_primeiro_padrao(app, monkeypatch):
    from addons.addon_brewstation.features.feature_mash_control.services.dashboard_workspace_actions import configure_layout
    plant, other, ids, widget = _appearance_layouts(app)
    with app.app_context():
        def fail():
            raise RuntimeError('Falha de gravação')
        monkeypatch.setattr(db.session, 'commit', fail)
        with pytest.raises(RuntimeError):
            configure_layout(plant, ids[1], color='#abc', image='/static/img/test.png', is_default=True)
        assert db.session.get(DashboardLayout, ids[0]).is_default
        selected = db.session.get(DashboardLayout, ids[1])
        assert not selected.is_default and selected.background_image_url is None


def test_dashboard_fundo_legado_invalido_nao_renderiza_script_nem_altera_dados(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    with app.app_context():
        selected = db.session.get(DashboardLayout, ids[1])
        selected.background_color = 'red;display:none'
        selected.background_image_url = 'javascript:alert(1)'
        db.session.commit()
    html = client.get(f'/brewstation/dashboards/{ids[1]}/view').get_data(as_text=True)
    assert 'background-color:#0f1117' in html
    assert 'id="dbBackgroundImage"' not in html
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[1]).background_image_url == 'javascript:alert(1)'


def test_dashboard_aparencia_retorno_normal_preserva_layout(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    response = client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/appearance',
                           data={'background_color': '#abc', 'background_image_url': ''})
    assert response.status_code == 302
    assert f'layout_id={ids[1]}' in response.location
    html = client.get(response.location).get_data(as_text=True)
    assert f'const initialLayoutId = "{ids[1]}";' in html
    assert 'encodeURIComponent(initialLayoutId)' in html


def test_workspace_lixeira_painel_preserva_widgets_e_retorna_fallback(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    url = f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}'
    response = client.post(url + '/trash', headers=headers)
    assert response.status_code == 200
    assert response.get_json()['layout_id'] == ids[0]
    assert response.get_json()['dashboard_reload']
    with app.app_context():
        removed = db.session.get(DashboardLayout, ids[1])
        assert removed.is_deleted and removed.deleted_at is not None
        timestamp = removed.deleted_at
        assert removed.layout_data == '{"original":true}'
        assert removed.standby_duration_seconds == 45
        assert not db.session.get(DashboardWidget, widget).is_deleted
        assert db.session.get(DashboardLayout, ids[2]).is_default
    assert client.post(url + '/trash', headers=headers).status_code == 400
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[1]).deleted_at == timestamp
    explicit = client.get(f'/brewstation/plant-workspace/{plant}/tab/dashboard?layout_id={ids[1]}')
    assert explicit.status_code == 404
    html = client.get(f'/brewstation/plant-workspace/{plant}/tab/dashboard').get_data(as_text=True)
    assert 'Restaurar painel' in html and 'Painel aparência' in html
    response = client.post(url + '/restore', headers=headers)
    assert response.get_json()['layout_id'] == ids[1]
    with app.app_context():
        restored = db.session.get(DashboardLayout, ids[1])
        assert not restored.is_deleted and restored.deleted_at is None
        assert db.session.get(DashboardWidget, widget).config_json == {'content': 'Intacto'}
    assert client.post(url + '/restore', headers=headers).status_code == 400


def test_workspace_restaurar_painel_nao_substitui_padrao_atual(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[3]).is_default
    response = client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[3]}/restore',
                           headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[0]).is_default
        assert not db.session.get(DashboardLayout, ids[3]).is_default
        assert db.session.get(DashboardLayout, ids[2]).is_default


def test_workspace_ultimo_painel_removido_mantem_lixeira_e_restaura_padrao(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name='Planta último painel'); db.session.add(plant); db.session.flush()
        layout = DashboardLayout(name='Último recuperável', plant_id=plant.id, is_default=True)
        db.session.add(layout); db.session.commit()
        plant_id, layout_id = plant.id, layout.id
    url = f'/brewstation/plant-workspace/{plant_id}/dashboard-layouts/{layout_id}'
    response = client.post(url + '/trash')
    assert response.status_code == 302 and 'layout_id=' not in response.location
    html = client.get(f'/brewstation/plant-workspace/{plant_id}/tab/dashboard').get_data(as_text=True)
    assert 'Último recuperável' in html and 'Restaurar painel' in html
    assert 'pwDashboardMaintenance' in html and '__tesseractConfirm' in html
    response = client.post(url + '/restore')
    assert response.status_code == 302 and f'layout_id={layout_id}' in response.location
    with app.app_context():
        assert db.session.get(DashboardLayout, layout_id).is_default


@pytest.mark.parametrize('action,permission', [('trash','dashboard_layouts.trash'), ('restore','dashboard_layouts.restore')])
def test_workspace_manutencao_layout_escopo_permissoes_e_planta_apagada(app, client, monkeypatch, action, permission):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    for layout_id in (ids[2], 999999):
        assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{layout_id}/{action}', headers=headers).status_code == 404
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != permission)
    assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/{action}', headers=headers).status_code == 403
    html = client.get(f'/brewstation/plant-workspace/{plant}/tab/dashboard').get_data(as_text=True)
    assert ('Enviar painel à lixeira' not in html) if action == 'trash' else ('Restaurar painel' not in html)
    monkeypatch.setattr(User, 'has_permission', lambda self, code: True)
    with app.app_context():
        db.session.get(BrewPlant, plant).is_deleted = True; db.session.commit()
    assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/{action}', headers=headers).status_code == 404


@pytest.mark.parametrize('action,index', [('trash',0), ('restore',3)])
def test_workspace_manutencao_layout_rollback_preserva_lixeira_e_padrao(app, client, monkeypatch, action, index):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    def fail():
        raise RuntimeError('Falha de gravação')
    monkeypatch.setattr(db.session, 'commit', fail)
    response = client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[index]}/{action}',
                           headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 500
    with app.app_context():
        row = db.session.get(DashboardLayout, ids[index])
        assert row.is_deleted == (action == 'restore')
        assert row.is_default
        assert db.session.get(DashboardLayout, ids[0]).is_default


def test_workspace_lixeira_layout_paginada_sem_misturar_plantas(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    with app.app_context():
        for number in range(25):
            db.session.add(DashboardLayout(name=f'Lixeira local {number:02d}', plant_id=plant, is_deleted=True))
        db.session.add(DashboardLayout(name='Lixeira externa secreta', plant_id=other, is_deleted=True))
        db.session.commit()
    url = f'/brewstation/plant-workspace/{plant}/tab/dashboard?layout_id={ids[1]}'
    first = client.get(url).get_data(as_text=True)
    assert 'Lixeira local 24' in first and 'Lixeira local 00' not in first
    assert 'Lixeira externa secreta' not in first
    assert f'layout_id={ids[1]}' in first and 'trash_page=2' in first
    second = client.get(url + '&trash_page=2').get_data(as_text=True)
    assert 'Lixeira local 00' in second and 'Lixeira local 24' not in second
    assert '<h1>Painel aparência</h1>' in second
    assert 'Página 2 de 2' in second


# Automação 4B.1: consulta paginada, sem acionamento ou escrita.
def _automation_history_data(app, count=23):
    from datetime import datetime
    with app.app_context():
        plant = BrewPlant(name="Automação paginada")
        other = BrewPlant(name="Outra planta automação")
        db.session.add_all([plant, other])
        db.session.flush()
        session = BrewSession(name="Sessão vinculada", plant_id=plant.id, status="paused")
        foreign_session = BrewSession(name="Sessão externa", plant_id=other.id)
        db.session.add_all([session, foreign_session])
        db.session.flush()
        rules = []
        for index in range(count):
            rule = AutomationRule(name=f"Regra paginada {index:02d}", sensor_function_name="sensor",
                                  condition_operator=">", condition_value=60, actor_function_name="actor",
                                  actor_action="OFF", session_id=session.id, trigger_count=7)
            db.session.add(rule)
            db.session.flush()
            rules.append(rule)
        foreign = AutomationRule(name="Regra externa secreta", sensor_function_name="sensor",
                                 condition_operator=">", condition_value=60, actor_function_name="actor",
                                 actor_action="OFF", session_id=foreign_session.id)
        global_rule = AutomationRule(name="Regra global 100%", sensor_function_name="sensor",
                                    condition_operator=">", condition_value=60, actor_function_name="actor",
                                    actor_action="OFF", is_active=False)
        db.session.add_all([foreign, global_rule])
        db.session.flush()
        for index in range(count):
            db.session.add(AutomationRuleLog(rule_id=rules[0].id, triggered_at=datetime(2026, 1, 1),
                                            success=False, error_message=f"Falha única {index:02d}", action_taken="OFF"))
        db.session.add(AutomationRuleLog(rule_id=foreign.id, success=False, error_message="Erro externo secreto"))
        db.session.commit()
        return plant.id, rules[0].id, foreign.id, global_rule.id, session.id


def test_automation_paginas_independentes_e_historico_antigo(app, client):
    from urllib.parse import urlparse, parse_qs
    _login_admin(app, client)
    plant_id, rule_id, _, _, _ = _automation_history_data(app)
    url = f"/brewstation/plant-workspace/{plant_id}/tab/automation"
    html = client.get(url + "?scope=session&outcome=error&rules_page=2&logs_page=2").get_data(as_text=True)
    assert html.count('data-automation-rule-id=') == 3
    assert html.count('data-automation-log-id=') == 3
    assert "Falha única 00" in html and "Falha única 22" not in html
    assert "Regra paginada 00" in html  # Nome do log mesmo fora da primeira página de regras.
    assert "Erro externo secreto" not in html
    class Links(HTMLParser):
        urls = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'a' and 'data-automation-page' in attrs:
                self.urls.append(attrs['href'])
    parser = Links()
    parser.feed(html)
    paged = [parse_qs(urlparse(link).query) for link in parser.urls if 'rules_page=' in link]
    assert any(q['rules_page'] == ['1'] and q['logs_page'] == ['2'] for q in paged)
    assert any(q['rules_page'] == ['2'] and q['logs_page'] == ['1'] for q in paged)
    assert all(q['scope'] == ['session'] and q['outcome'] == ['error'] for q in paged)
    selected = client.get(url + f"?rule_id={rule_id}&logs_page=999").get_data(as_text=True)
    assert selected.count('data-automation-rule-id=') == 1
    assert selected.count('data-automation-log-id=') == 3
    assert "Página 2 de 2" in selected


@pytest.mark.parametrize('selection', ['foreign', 'deleted', 'deleted_session', 'invalid'])
def test_automation_selecao_explicita_invalida_nao_escolhe_outra(app, client, selection):
    _login_admin(app, client)
    plant_id, rule_id, foreign_id, _, session_id = _automation_history_data(app, 1)
    with app.app_context():
        if selection == 'deleted':
            db.session.get(AutomationRule, rule_id).is_deleted = True
        elif selection == 'deleted_session':
            db.session.get(BrewSession, session_id).is_deleted = True
        db.session.commit()
    selected = foreign_id if selection == 'foreign' else 'abc' if selection == 'invalid' else rule_id
    response = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation?rule_id={selected}")
    assert response.status_code == 404
    assert b'data-automation-rule-id=' not in response.data


@pytest.mark.parametrize('parameter', ['active=bogus', 'scope=bogus', 'outcome=bogus'])
def test_automation_rejeita_enum_desconhecido(app, client, parameter):
    _login_admin(app, client)
    plant_id, *_ = _automation_history_data(app, 1)
    assert client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation?{parameter}").status_code == 400


def test_automation_busca_literal_combo_escopado_e_filtros(app, client):
    _login_admin(app, client)
    plant_id, rule_id, foreign_id, global_id, _ = _automation_history_data(app, 1)
    html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation?q=%25&active=inactive&scope=global").get_data(as_text=True)
    assert html.count('data-automation-rule-id=') == 1
    assert 'Regra global 100%' in html
    assert 'Global — compartilhada entre plantas' in html
    class Combo(HTMLParser):
        ids = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('data-weakref-source') == 'automation_rules':
                self.ids = {int(x) for x in attrs['data-weakref-ids'].split(',') if x}
    parser = Combo()
    parser.feed(html)
    assert parser.ids == {rule_id, global_id}
    assert foreign_id not in parser.ids
    assert 'class="form-select"' in html


def test_automation_permissoes_nao_expoem_logs_nem_atalhos(app, client, monkeypatch):
    _login_admin(app, client)
    plant_id, *_ = _automation_history_data(app, 1)
    denied = {'automation_rule_logs.list', 'automation_rules.create', 'automation_rules.detail'}
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code not in denied)
    html = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation").get_data(as_text=True)
    assert 'Sem permissão para consultar' in html
    assert 'Falha única' not in html and 'data-automation-log-id=' not in html
    assert 'Nova Regra' not in html and '>Detalhes</a>' not in html
    assert 'Regra paginada 00' in html
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'automation_rules.list')
    assert client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation").status_code == 403


def test_automation_consulta_nao_aciona_motor_nem_altera_dados(app, client, monkeypatch):
    from addons.addon_device_manager.root.services import device_service
    _login_admin(app, client)
    plant_id, rule_id, _, global_id, session_id = _automation_history_data(app, 1)
    def forbidden(*args, **kwargs):
        pytest.fail('Consulta não pode acionar dispositivos')
    monkeypatch.setattr(device_service, 'set_value', forbidden)
    def snapshot():
        rule = db.session.get(AutomationRule, rule_id)
        session = db.session.get(BrewSession, session_id)
        return (rule.trigger_count, rule.last_triggered_at, rule.is_active, session.status,
                AutomationRuleLog.query.count())
    with app.app_context():
        before = snapshot()
    for query in ['', '?outcome=error', f'?rule_id={global_id}', '?rules_page=999&logs_page=999']:
        assert client.get(f"/brewstation/plant-workspace/{plant_id}/tab/automation{query}").status_code == 200
    with app.app_context():
        assert snapshot() == before


# Patch combinado 4B.3/4B.4/4C.
def _workspace_rule_form(app):
    with app.app_context():
        for name, category in [('ws_rule_sensor', 'sensor'), ('ws_rule_actor', 'actuator')]:
            if not DeviceFunction.query.filter_by(name=name).first():
                db.session.add(DeviceFunction(name=name, display_name=name, category=category))
        plant = BrewPlant(name='Planta edição de regras')
        other = BrewPlant(name='Planta externa edição')
        db.session.add_all([plant, other])
        db.session.flush()
        session = BrewSession(name='Sessão regras', plant_id=plant.id, status='active')
        external = BrewSession(name='Sessão externa regras', plant_id=other.id, status='active')
        db.session.add_all([session, external])
        db.session.commit()
        return plant.id, session.id, external.id, dict(name='Regra editável', description='Descrição',
            sensor_function_name='ws_rule_sensor', actor_function_name='ws_rule_actor', sensor_metric='temperature',
            condition_operator='<=', condition_value='65.5', condition_unit='°C', actor_action='SET_VALUE',
            actor_value='40', cooldown_seconds='30', session_id='')


def test_workspace_cria_edita_regra_preserva_execucao_e_ignora_campos_protegidos(app, client):
    _login_admin(app, client)
    plant_id, _, _, data = _workspace_rule_form(app)
    url = f'/brewstation/plant-workspace/{plant_id}/automation-rules'
    data.update(is_active='true', trigger_count='999', last_triggered_at='2026-10-01', is_deleted='true')
    response = client.post(url, data=data)
    assert response.status_code == 200
    rule_id = response.get_json()['rule_id']
    with app.app_context():
        rule = db.session.get(AutomationRule, rule_id)
        assert not rule.is_active and not rule.is_deleted and rule.trigger_count == 0
        assert rule.last_triggered_at is None
        rule.trigger_count = 5
        log = AutomationRuleLog(rule_id=rule_id, success=True, action_taken='ON')
        db.session.add(log)
        db.session.commit()
    data['name'] = 'Regra renomeada'
    assert client.post(url + f'/{rule_id}/edit', data=data).status_code == 200
    with app.app_context():
        rule = db.session.get(AutomationRule, rule_id)
        assert rule.name == 'Regra renomeada' and rule.trigger_count == 5
        assert AutomationRuleLog.query.filter_by(rule_id=rule_id).count() == 1
        rule.is_active = True
        db.session.commit()
    assert client.post(url + f'/{rule_id}/edit', data={**data, 'name': 'Não alterar'}).status_code == 400
    with app.app_context():
        assert db.session.get(AutomationRule, rule_id).name == 'Regra renomeada'


@pytest.mark.parametrize('field,value', [('name', ''), ('name', 'x'*201), ('condition_value', 'nan'),
    ('condition_value', 'inf'), ('actor_value', ''), ('cooldown_seconds', '-1'), ('cooldown_seconds', '1.5'),
    ('cooldown_seconds', '9'*400), ('condition_operator', 'BAD'), ('actor_action', 'BAD'),
    ('sensor_function_name', 'ws_rule_actor'), ('actor_function_name', 'missing')])
def test_workspace_regras_validacao_sem_gravacao_parcial(app, client, field, value):
    _login_admin(app, client)
    plant_id, _, _, data = _workspace_rule_form(app)
    data[field] = value
    with app.app_context():
        before = AutomationRule.query.count()
    assert client.post(f'/brewstation/plant-workspace/{plant_id}/automation-rules', data=data).status_code == 400
    with app.app_context():
        assert AutomationRule.query.count() == before


def test_workspace_regra_vinculo_escopo_e_guarda_ativacao(app, client):
    _login_admin(app, client)
    plant_id, session_id, external_id, data = _workspace_rule_form(app)
    url = f'/brewstation/plant-workspace/{plant_id}/automation-rules'
    assert client.post(url, data={**data, 'session_id': external_id}).status_code == 400
    result = client.post(url, data={**data, 'session_id': session_id}).get_json()
    rule_id = result['rule_id']
    # Funções sem mapeamento/ator único não podem ser ativadas.
    assert client.post(url + f'/{rule_id}/activate').status_code == 400
    with app.app_context():
        assert not db.session.get(AutomationRule, rule_id).is_active
        db.session.get(AutomationRule, rule_id).session_id = external_id
        db.session.commit()
    for action in ['activate', 'deactivate', 'trash', 'restore', 'edit']:
        assert client.post(url + f'/{rule_id}/{action}', data=data).status_code == 404


def test_workspace_regra_lixeira_restauracao_idempotente_preserva_historico(app, client):
    _login_admin(app, client)
    plant_id, _, _, data = _workspace_rule_form(app)
    url = f'/brewstation/plant-workspace/{plant_id}/automation-rules'
    rule_id = client.post(url, data=data).get_json()['rule_id']
    assert client.post(url + f'/{rule_id}/activate').status_code == 200  # Global válida.
    with app.app_context():
        db.session.add(AutomationRuleLog(rule_id=rule_id, success=True, action_taken='ON'))
        db.session.commit()
    assert client.post(url + f'/{rule_id}/trash').status_code == 200
    with app.app_context():
        first_deleted_at = db.session.get(AutomationRule, rule_id).deleted_at
    assert client.post(url + f'/{rule_id}/trash').status_code == 200
    with app.app_context():
        rule = db.session.get(AutomationRule, rule_id)
        assert not rule.is_active and rule.deleted_at == first_deleted_at
    html = client.get(f'/brewstation/plant-workspace/{plant_id}/tab/automation').get_data(as_text=True)
    assert 'Restaurar inativa' in html and 'Regra editável' in html
    assert client.post(url + f'/{rule_id}/activate').status_code == 400
    assert client.post(url + f'/{rule_id}/restore').status_code == 200
    assert client.post(url + f'/{rule_id}/restore').status_code == 200
    with app.app_context():
        rule = db.session.get(AutomationRule, rule_id)
        assert not rule.is_active and not rule.is_deleted
        assert AutomationRuleLog.query.filter_by(rule_id=rule_id).count() == 1


@pytest.mark.parametrize('action,permission', [('edit', 'automation_rules.update'), ('activate', 'automation_rules.update'),
    ('deactivate', 'automation_rules.update'), ('trash', 'automation_rules.trash'), ('restore', 'automation_rules.restore')])
def test_workspace_regra_manutencao_permissoes(app, client, monkeypatch, action, permission):
    _login_admin(app, client)
    plant_id, _, _, data = _workspace_rule_form(app)
    url = f'/brewstation/plant-workspace/{plant_id}/automation-rules'
    rule_id = client.post(url, data=data).get_json()['rule_id']
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != permission)
    assert client.post(url + f'/{rule_id}/{action}', data=data).status_code == 403


def test_workspace_regra_rollback_e_criacao_sem_permissao(app, client, monkeypatch):
    _login_admin(app, client)
    plant_id, _, _, data = _workspace_rule_form(app)
    url = f'/brewstation/plant-workspace/{plant_id}/automation-rules'
    rule_id = client.post(url, data=data).get_json()['rule_id']
    original_commit = db.session.commit
    def fail():
        raise RuntimeError('falha simulada')
    monkeypatch.setattr(db.session, 'commit', fail)
    assert client.post(url + f'/{rule_id}/edit', data={**data, 'name': 'Alteração parcial'}).status_code == 500
    assert client.post(url + f'/{rule_id}/trash').status_code == 500
    monkeypatch.setattr(db.session, 'commit', original_commit)
    with app.app_context():
        rule = db.session.get(AutomationRule, rule_id)
        assert rule.name == data['name'] and not rule.is_deleted
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'automation_rules.create')
    assert client.post(url, data=data).status_code == 403


def _workspace_runtime_data(app):
    with app.app_context():
        plant = BrewPlant(name='Runtime workspace')
        other = BrewPlant(name='Runtime externo')
        db.session.add_all([plant, other])
        db.session.flush()
        session = BrewSession(name='Runtime sessão antiga', plant_id=plant.id, status='active')
        external = BrewSession(name='Runtime sessão externa', plant_id=other.id, status='active')
        db.session.add_all([session, external])
        db.session.flush()
        first = BrewSessionStep(session_id=session.id, step_index=0, name='Primeira', step_type='mash', status='active', duration_seconds=60)
        second = BrewSessionStep(session_id=session.id, step_index=1, name='Segunda', step_type='boil', status='pending', duration_seconds=60)
        db.session.add_all([first, second])
        db.session.commit()
        return plant.id, session.id, external.id, first.id, second.id


def test_workspace_runtime_reutiliza_avanco_rejeita_reenvio_e_sessao_externa(app, client):
    _login_admin(app, client)
    plant_id, session_id, external_id, first_id, second_id = _workspace_runtime_data(app)
    url = f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/runtime'
    data = dict(expected_status='active', expected_step_id=first_id)
    assert client.post(url + '/advance-step', data=data).status_code == 200
    assert client.post(url + '/advance-step', data=data).status_code == 409
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).status == 'completed'
        assert db.session.get(BrewSessionStep, second_id).status == 'active'
    assert client.post(url + '/go-back-step', data={**data, 'expected_step_id': second_id}).status_code == 200
    assert client.post(f'/brewstation/plant-workspace/{plant_id}/sessions/{external_id}/runtime/stop', data=data).status_code == 404


def test_workspace_runtime_pausa_retomada_conclusao_e_estado_desatualizado(app, client):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    url = f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/runtime'
    assert client.post(url + '/toggle-pause', data={'expected_status': 'active'}).status_code == 200
    assert client.post(url + '/toggle-pause', data={'expected_status': 'active'}).status_code == 409
    assert client.post(url + '/advance-step', data={'expected_status': 'paused', 'expected_step_id': first_id}).status_code == 400
    assert client.post(url + '/toggle-pause', data={'expected_status': 'paused'}).status_code == 200
    assert client.post(url + '/stop', data={'expected_status': 'active'}).status_code == 200
    assert client.post(url + '/advance-step', data={'expected_status': 'completed'}).status_code == 400
    with app.app_context():
        assert db.session.get(BrewSession, session_id).status == 'completed'


@pytest.mark.parametrize('action,permission', [('advance-step', 'dashboard_layouts.update'),
    ('go-back-step', 'dashboard_layouts.update'), ('resync-steps', 'dashboard_layouts.update'),
    ('toggle-pause', 'brew_sessions.update'), ('stop', 'brew_sessions.update')])
def test_workspace_runtime_permissoes(app, client, monkeypatch, action, permission):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != permission)
    response = client.post(f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/runtime/{action}',
                           data={'expected_status': 'active', 'expected_step_id': first_id})
    assert response.status_code == 403


def test_workspace_controles_combos_e_confirmacao_padrao(app, client):
    _login_admin(app, client)
    plant_id, _, external_id, _ = _workspace_rule_form(app)
    html = client.get(f'/brewstation/plant-workspace/{plant_id}/tab/automation').get_data(as_text=True)
    assert 'data-weakref-source="device_functions"' in html and 'data-weakref-value-field="name"' in html
    assert 'data-weakref-source="brew_sessions"' in html and 'window.__tesseractConfirm' in html
    assert 'Sessão externa regras' not in html
    assert 'Salvar inativa' in html
    plant_id, session_id, _, _, _ = _workspace_runtime_data(app)
    html = client.get(f'/brewstation/plant-workspace/{plant_id}/tab/sessions?session_id={session_id}').get_data(as_text=True)
    assert 'Concluir e avançar etapa' in html and 'Ressincronizar etapas' not in html  # Sem receita.
    assert 'expected_step_id' in html and 'data-session-confirm' in html


def test_workspace_runtime_resync_preserva_etapa_completa(app, client):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    with app.app_context():
        recipe = MashRecipe(name='Receita resync workspace', origem_receita='Manual', versao=1)
        db.session.add(recipe)
        db.session.flush()
        planned = RecipeStep(recipe_id=recipe.id, nome='Planejada nova', step_type='mash', ordem=3, tempo_min=10)
        db.session.add(planned)
        db.session.get(BrewSession, session_id).recipe_id = recipe.id
        db.session.get(BrewSessionStep, first_id).status = 'completed'
        db.session.commit()
    url = f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/runtime/resync-steps'
    assert client.post(url, data={'expected_status': 'active'}).status_code == 200
    assert client.post(url, data={'expected_status': 'active'}).status_code == 200
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).status == 'completed'
        assert BrewSessionStep.query.filter_by(session_id=session_id, name='Planejada nova', is_deleted=False).count() == 1


def test_workspace_runtime_rollback_desfaz_avanco(app, client, monkeypatch):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, second_id = _workspace_runtime_data(app)
    def fail():
        raise RuntimeError('Falha commit runtime')
    monkeypatch.setattr(db.session, 'commit', fail)
    response = client.post(f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/runtime/advance-step',
                           data={'expected_status': 'active', 'expected_step_id': first_id})
    assert response.status_code == 500
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).status == 'active'
        assert db.session.get(BrewSessionStep, second_id).status == 'pending'


def test_workspace_ajuste_etapa_registra_operador_preserva_receita_e_repeticao(app, client):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    url = f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/steps/{first_id}/adjust'
    with app.app_context():
        before = BrewSessionLog.query.filter_by(session_id=session_id).count()
        user_id = User.query.filter_by(username='admin').first().id
    data = {'field': 'duration_seconds', 'value': '120'}
    assert client.post(url, data=data).status_code == 200
    assert client.post(url, data=data).status_code == 200
    with app.app_context():
        step = db.session.get(BrewSessionStep, first_id)
        assert step.duration_seconds == 120 and step.status == 'active'
        assert db.session.get(BrewSession, session_id).recipe_id is None
        logs = BrewSessionLog.query.filter_by(session_id=session_id, step_id=first_id).all()
        assert len(logs) == before + 1
        assert logs[-1].detail_json['user_id'] == user_id


@pytest.mark.parametrize('field,value', [('status', 'completed'), ('duration_seconds', '-1'),
    ('duration_seconds', '1.5'), ('target_temp', 'nan'), ('name', '')])
def test_workspace_ajuste_recusa_dados_invalidos(app, client, field, value):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    response = client.post(f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/steps/{first_id}/adjust',
                           data={'field': field, 'value': value})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).duration_seconds == 60


def test_workspace_ajuste_escopo_permissao_historico_e_rollback(app, client, monkeypatch):
    _login_admin(app, client)
    plant_id, session_id, external_id, first_id, _ = _workspace_runtime_data(app)
    path = f'/brewstation/plant-workspace/{plant_id}/sessions'
    data = {'field': 'name', 'value': 'Novo nome'}
    assert client.post(f'{path}/{external_id}/steps/{first_id}/adjust', data=data).status_code == 404
    url = f'{path}/{session_id}/steps/{first_id}/adjust'
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'brew_session_steps.update')
    assert client.post(url, data=data).status_code == 403
    monkeypatch.setattr(User, 'has_permission', lambda self, code: True)
    def fail():
        raise RuntimeError('Falha ao gravar ajuste e histórico')
    monkeypatch.setattr(db.session, 'commit', fail)
    assert client.post(url, data=data).status_code == 500
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).name == 'Primeira'
        assert BrewSessionLog.query.filter_by(session_id=session_id).count() == 0


def test_workspace_lixeira_regras_paginada_sem_vazar_outro_escopo(app, client, monkeypatch):
    _login_admin(app, client)
    plant_id, _, foreign_id, _, _ = _automation_history_data(app, 23)
    with app.app_context():
        for rule in AutomationRule.query.filter(AutomationRule.name.contains('Regra paginada')).all():
            rule.is_deleted = True
        db.session.get(AutomationRule, foreign_id).is_deleted = True
        db.session.commit()
    url = f'/brewstation/plant-workspace/{plant_id}/tab/automation?trash_page=2'
    html = client.get(url).get_data(as_text=True)
    assert 'Lixeira de regras (23)' in html and 'Regra paginada 00' in html
    assert 'Regra paginada 22' not in html and 'Regra externa secreta' not in html
    assert html.count('Restaurar inativa</button>') == 3
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'automation_rules.restore')
    html = client.get(url).get_data(as_text=True)
    assert 'Lixeira de regras' not in html and 'Regra paginada 00' not in html


@pytest.mark.parametrize('blocked', ['completed_step', 'completed_session', 'deleted_step', 'deleted_plant'])
def test_workspace_ajuste_etapa_bloqueia_historico_fechado_e_exclusao(app, client, blocked):
    _login_admin(app, client)
    plant_id, session_id, _, first_id, _ = _workspace_runtime_data(app)
    with app.app_context():
        if blocked == 'completed_step':
            db.session.get(BrewSessionStep, first_id).status = 'completed'
        elif blocked == 'completed_session':
            db.session.get(BrewSession, session_id).status = 'completed'
        elif blocked == 'deleted_step':
            db.session.get(BrewSessionStep, first_id).is_deleted = True
        else:
            db.session.get(BrewPlant, plant_id).is_deleted = True
        db.session.commit()
    response = client.post(f'/brewstation/plant-workspace/{plant_id}/sessions/{session_id}/steps/{first_id}/adjust',
                           data={'field': 'name', 'value': 'Não alterar'})
    assert response.status_code == (404 if blocked.startswith('deleted') else 400)
    with app.app_context():
        assert db.session.get(BrewSessionStep, first_id).name == 'Primeira'


def test_standby_workspace_salva_preserva_campos_e_renderiza_views(app, client):
    _login_admin(app, client)
    plant, other, ids, widget = _appearance_layouts(app)
    url = f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/standby'
    payload = {'is_standby_enabled': 'on', 'standby_duration_seconds': '10', 'plant_id': other, 'is_default': 'on'}
    response = client.post(url, data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    assert response.json['layout_id'] == ids[1]
    with app.app_context():
        layout = db.session.get(DashboardLayout, ids[1])
        assert layout.is_standby_enabled and layout.standby_duration_seconds == 10
        assert layout.plant_id == plant and not layout.is_default
        assert layout.layout_data == '{"original":true}'
        assert db.session.get(DashboardWidget, widget).config_json == {'content': 'Intacto'}
    for view in (f'/brewstation/plant-workspace/{plant}/tab/dashboard?layout_id={ids[1]}', f'/brewstation/dashboards/{ids[1]}/view'):
        html = client.get(view).get_data(as_text=True)
        if '/view' in view:
            assert 'dashboard_standby.js' in html
        assert 'enabled: true' in html and 'seconds: 10' in html
        assert 'standbyCleanup();' in html
    response = client.post(url, data={'standby_duration_seconds': '30'})
    assert response.status_code == 302 and f'layout_id={ids[1]}' in response.location
    with app.app_context():
        assert not db.session.get(DashboardLayout, ids[1]).is_standby_enabled


@pytest.mark.parametrize('seconds', ['', '0', '9', '86401', '10.5', 'nan', '999999999999999999999999'])
def test_standby_workspace_valida_duracao(app, client, seconds):
    _login_admin(app, client)
    plant, _, ids, _ = _appearance_layouts(app)
    response = client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/standby',
        data={'is_standby_enabled': 'on', 'standby_duration_seconds': seconds}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[1]).standby_duration_seconds == 45


def test_standby_workspace_escopo_permissao_e_rollback(app, client, monkeypatch):
    _login_admin(app, client)
    plant, _, ids, _ = _appearance_layouts(app)
    payload = {'is_standby_enabled': 'on', 'standby_duration_seconds': '10'}
    for layout in (ids[2], ids[3], 999999):
        assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{layout}/standby', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'}).status_code == 404
    with app.app_context():
        from addons.addon_brewstation.features.feature_mash_control.services.dashboard_workspace_actions import configure_standby
        with monkeypatch.context() as patch:
            patch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('falha')))
            with pytest.raises(RuntimeError):
                configure_standby(plant, ids[1], enabled=False, seconds='10')
        assert db.session.get(DashboardLayout, ids[1]).standby_duration_seconds == 45
        assert db.session.get(DashboardLayout, ids[1]).is_standby_enabled
    monkeypatch.setattr(User, 'has_permission', lambda self, code: code != 'dashboard_layouts.update')
    assert client.post(f'/brewstation/plant-workspace/{plant}/dashboard-layouts/{ids[1]}/standby', data=payload).status_code == 403


def test_standby_legado_invalido_consulta_sem_gravar(app, client):
    _login_admin(app, client)
    plant, _, ids, _ = _appearance_layouts(app)
    with app.app_context():
        db.session.get(DashboardLayout, ids[1]).standby_duration_seconds = 0
        db.session.commit()
    html = client.get(f'/brewstation/dashboards/{ids[1]}/view').get_data(as_text=True)
    assert 'enabled: false' in html and 'seconds: 30' in html
    with app.app_context():
        assert db.session.get(DashboardLayout, ids[1]).standby_duration_seconds == 0


def _workspace_conversion_data(app):
    from addons.addon_estoque.root.model.material import Material
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    pid, rid, iid, mid = _workspace_sanitation_data(app)
    with app.app_context():
        material = db.session.get(Material, mid)
        material.unidade_medida = "UN"
        ing = db.session.get(RecipeIngredient, iid)
        ing.unidade_medida = "items"
        ing.quantidade = 2
        ing.material_id = mid
        ing.status_resolucao = "resolvido"
        if not UnidadeCatalogo.query.filter_by(codigo="UN").first():
            db.session.add(UnidadeCatalogo(codigo="UN", descricao="Unidade", dimensao="contagem"))
        db.session.commit()
    return pid, rid, iid, mid


def test_workspace_conversion_resolve_items_sem_alterar_receita_ou_estoque(app, client):
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import conferir_ingredientes
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_conversion_data(app)
    with app.app_context():
        db.session.add(BrewSession(name="Sessão existente", recipe_id=rid, plant_id=pid, status="draft"))
        db.session.commit()
        before = db.session.get(RecipeIngredient, iid).to_dict()
        count = Movimentacao.query.count()
        assert conferir_ingredientes(rid)["pendencias"]
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'class="pw-ingredient-conversion"' in html and 'items → ITEM' in html
    assert 'class="pw-ingredient-sanitation' not in html
    assert 'brewstation_mashctrl.conversion.title' not in html
    url = f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/conversion"
    data = {"material_id": mid, "unidade_origem": "ITEM", "unidade_base": "UN", "fator_para_base": "1"}
    for _ in range(2):
        response = client.post(url, data=data, headers={"X-Requested-With": "XMLHttpRequest"})
        assert response.status_code == 200, response.get_json()
    with app.app_context():
        assert db.session.get(RecipeIngredient, iid).to_dict() == before
        assert Movimentacao.query.count() == count
        assert MaterialUnidade.query.filter_by(material_id=mid, is_deleted=False).count() == 2
        conference = conferir_ingredientes(rid)
        assert not conference["pendencias"]
        assert conference["prontos"][0]["quantidade_base"] == 2
        assert conference["prontos"][0]["unidade_base"] == "UN"


@pytest.mark.parametrize("factor", ["", "0", "-1", "nan", "inf", "texto"])
def test_workspace_conversion_fator_invalido_nao_grava_catalogo_base_ou_movimento(app, client, factor):
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_conversion_data(app)
    with app.app_context():
        units = MaterialUnidade.query.count()
        catalog = UnidadeCatalogo.query.count()
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/conversion",
        data={"material_id": mid, "unidade_origem": "ITEM", "unidade_base": "UN", "fator_para_base": factor},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 400
    with app.app_context():
        assert MaterialUnidade.query.count() == units
        assert UnidadeCatalogo.query.count() == catalog


@pytest.mark.parametrize("permission", ["recipe_steps.list", "material_unidades.create"])
def test_workspace_conversion_respeita_permissao(app, client, monkeypatch, permission):
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_conversion_data(app)
    monkeypatch.setattr(User, "has_permission", lambda self, code: code != permission)
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/conversion",
        data={"material_id": mid, "unidade_origem": "ITEM", "unidade_base": "UN", "fator_para_base": 1},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 403


@pytest.mark.parametrize("case", ["plant", "recipe", "ingredient", "material", "source", "base"])
def test_workspace_conversion_rejeita_contexto_invalido_ou_obsoleto(app, client, case):
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_conversion_data(app)
    data = {"material_id": mid, "unidade_origem": "ITEM", "unidade_base": "UN", "fator_para_base": 1}
    if case == "plant": pid = 999999
    if case == "recipe": rid = 999999
    if case == "ingredient": iid = 999999
    if case == "material": data["material_id"] = 999999
    if case == "source": data["unidade_origem"] = "KG"
    if case == "base": data["unidade_base"] = "KG"
    response = client.post(f"/brewstation/plant-workspace/{pid}/recipes/{rid}/ingredients/{iid}/conversion",
        data=data, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == (404 if case in ("plant", "recipe", "ingredient") else 400)
    with app.app_context():
        assert MaterialUnidade.query.filter_by(material_id=mid).count() == 0


def test_workspace_conversion_nao_oferece_ajuste_quando_apenas_quantidade_esta_pendente(app, client):
    from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao
    _login_admin(app, client)
    pid, rid, iid, mid = _workspace_conversion_data(app)
    with app.app_context():
        cadastrar_conversao(mid, "items", 1, unidade_base_esperada="UN")
        db.session.get(RecipeIngredient, iid).quantidade = None
        db.session.commit()
    html = client.get(f"/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}").data.decode()
    assert 'class="pw-ingredient-conversion"' not in html
    assert 'class="pw-ingredient-sanitation' in html
    assert 'Informe uma quantidade positiva' in html
