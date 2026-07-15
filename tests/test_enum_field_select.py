"""
tests/test_enum_field_select.py

Cobre a capacidade nova do CrudGen (conversa — "select box pra campo
de opção fixa"): @enum_field gera <select> no formulário de detalhe,
substituindo <input type="text"> livre. Diferente de @choices (já
existia, dinâmico — SELECT DISTINCT só pra filtro de lista).

- Mecanismo genérico (annotations.enum_field/get_enum_fields).
- Aplicado em 7 entidades reais que sofriam do problema (achado da
  conversa: BrewSession.status foi só o primeiro sintoma reportado).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from annotations import enum_field, get_enum_fields
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata


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


# ── Mecanismo genérico ────────────────────────────────────────────────────

def test_enum_field_registra_opcoes_string_simples():
    @enum_field("status", options=["a", "b"])
    class _Fake:
        pass

    fields = get_enum_fields(_Fake)
    assert fields == [{"field": "status", "label": "Status", "options": [
        {"value": "a", "label": "a"}, {"value": "b", "label": "b"},
    ]}]


def test_enum_field_registra_opcoes_tupla_valor_label():
    @enum_field("status_resolucao", options=[("pendente_depara", "Pendente"), ("resolvido", "Resolvido")])
    class _Fake2:
        pass

    fields = get_enum_fields(_Fake2)
    assert fields[0]["options"] == [
        {"value": "pendente_depara", "label": "Pendente"},
        {"value": "resolvido", "label": "Resolvido"},
    ]


def test_enum_field_aceita_label_customizado():
    @enum_field("status", options=["a"], label="Situação")
    class _Fake3:
        pass

    assert get_enum_fields(_Fake3)[0]["label"] == "Situação"


def test_get_enum_fields_vazio_sem_decorator():
    class _Fake4:
        pass

    assert get_enum_fields(_Fake4) == []


# ── Aplicado nas entidades reais (conversa — achados além de BrewSession) ──

def test_brew_plant_vessels_detail_renderiza_select_vessel_type(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Enum Vessel")
        db.session.add(plant)
        db.session.commit()
        vessel = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT Enum")
        db.session.add(vessel)
        db.session.commit()
        vessel_id = vessel.id

    resp = client.get(f"/brewstation/brew-plant-vessels/{vessel_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="vessel_type"' in html
    assert 'value="hlt" selected' in html
    assert 'value="mash_tun"' in html
    assert 'value="bright_tank"' in html


def test_brew_session_steps_detail_renderiza_select_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Enum Step", status="draft")
        db.session.add(session)
        db.session.commit()
        step = BrewSessionStep(session_id=session.id, step_index=0, name="Passo Enum", step_type="mash", status="active")
        db.session.add(step)
        db.session.commit()
        step_id = step.id

    resp = client.get(f"/brewstation/brew-session-steps/{step_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="status"' in html
    assert 'value="active" selected' in html
    assert 'value="completed"' in html
    assert 'value="skipped"' in html


def test_recipe_steps_detail_renderiza_select_step_type_junto_com_weak_ref(app, client):
    """RecipeStep já tinha campo weak_ref (parent_step_id) — garante
    que o branch novo de enum não quebra a cadeia if/elif existente."""
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Enum Step")
        db.session.add(recipe)
        db.session.commit()
        step = RecipeStep(recipe_id=recipe.id, step_type="boil", ordem=0, nome="Fervura Enum")
        db.session.add(step)
        db.session.commit()
        step_id = step.id

    resp = client.get(f"/brewstation/recipe-steps/{step_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="step_type"' in html
    assert 'value="boil" selected' in html
    assert 'value="mash"' in html
    assert 'value="alert"' in html


def test_recipe_ingredients_detail_renderiza_select_com_label_customizado(app, client):
    """status_resolucao usa opção (valor, label) diferente — confirma
    que o label customizado aparece, não só o valor cru."""
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Enum Ingrediente")
        db.session.add(recipe)
        db.session.commit()
        ing = RecipeIngredient(recipe_id=recipe.id, descricao_origem="Malte X", status_resolucao="resolvido")
        db.session.add(ing)
        db.session.commit()
        ing_id = ing.id

    resp = client.get(f"/brewstation/recipe-ingredients/{ing_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="status_resolucao"' in html
    assert 'value="resolvido" selected' in html
    assert '>Pendente de vínculo<' in html  # label customizado, não o valor cru "pendente_depara"


def test_envases_detail_renderiza_select_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Enum Envase", status="completed")
        db.session.add(session)
        db.session.commit()
        envase = Envase(lote_id=session.id, status="registrado")
        db.session.add(envase)
        db.session.commit()
        envase_id = envase.id

    resp = client.get(f"/brewstation/envases/{envase_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="status"' in html
    assert 'value="registrado" selected' in html
    assert 'value="cancelado"' in html


def test_brewfather_syncs_detail_renderiza_select_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        sync = BrewFatherSync(tipo_sync="recipes", status="erro")
        db.session.add(sync)
        db.session.commit()
        sync_id = sync.id

    resp = client.get(f"/brewstation/brewfather-syncs/{sync_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="status"' in html
    assert 'value="erro" selected' in html
    assert 'value="em_andamento"' in html
    assert 'value="parcial"' in html


def test_device_metadatas_detail_renderiza_select_device_type(app, client):
    _login_admin(app, client)
    with app.app_context():
        device = DeviceMetadata(name="Device Enum", device_type="gateway")
        db.session.add(device)
        db.session.commit()
        device_id = device.id

    resp = client.get(f"/device-manager/device-metadatas/{device_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="device_type"' in html
    assert 'value="gateway" selected' in html
    assert 'value="sensor"' in html
    assert 'value="actuator"' in html


# ── manage.html: formulário de criação + filtro (achado da conversa —
# form_modal.html.j2 confirmado morto; a criação real acontece dentro
# de manage.html.j2, que tinha o MESMO gap de enum que detail.html.j2
# tinha antes da rodada anterior) ───────────────────────────────────────────

def test_manage_brew_sessions_renderiza_select_no_formulario_de_criacao(app, client):
    """Entidade old-style (sem weak_ref) — confirma o branch enum no
    formulário 'Novo registro' embutido em manage.html."""
    _login_admin(app, client)
    resp = client.get("/brewstation/brew-sessions/")
    html = resp.data.decode("utf-8")
    assert 'id="createForm"' in html
    assert '<select name="status"' in html
    assert 'value="draft"' in html
    assert 'value="aborted"' in html


def test_manage_recipe_steps_renderiza_select_no_formulario_de_criacao(app, client):
    """Entidade moderna (com weak_ref) — confirma que o branch enum
    não quebra a cadeia if/elif com weak_ref no formulário de criação."""
    _login_admin(app, client)
    resp = client.get("/brewstation/recipe-steps/")
    html = resp.data.decode("utf-8")
    assert '<select name="step_type"' in html
    assert 'value="mash"' in html
    assert 'value="boil"' in html
    assert 'value="alert"' in html


def test_manage_device_metadatas_filtro_mostra_todas_opcoes_mesmo_sem_registro(app, client):
    """Achado da conversa: filtro antes só mostrava valor que já
    existe no banco (via @choices). Com @enum_field, mostra TODAS as
    opções válidas mesmo sem nenhum registro usando ainda."""
    _login_admin(app, client)
    with app.app_context():
        # Nenhum DeviceMetadata criado ainda — banco vazio pra este campo.
        assert DeviceMetadata.query.count() == 0

    resp = client.get("/device-manager/device-metadatas/")
    html = resp.data.decode("utf-8")
    assert '<select name="filter_device_type"' in html
    assert 'value="sensor"' in html
    assert 'value="actuator"' in html
    assert 'value="gateway"' in html


def test_manage_envases_filtro_por_enum_filtra_de_verdade(app, client):
    """Confirma que o filtro renderizado também FUNCIONA — _apply_filters
    precisa iterar _ENUM_FIELDS além de _CHOICES_FIELDS (achado real:
    esquecido na primeira versão do patch em lote desta rodada)."""
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Filtro Enum", status="completed")
        db.session.add(session)
        db.session.commit()
        db.session.add(Envase(lote_id=session.id, status="registrado"))
        db.session.add(Envase(lote_id=session.id, status="cancelado"))
        db.session.commit()

    resp = client.get("/brewstation/envases/?filter_status=cancelado")
    html = resp.data.decode("utf-8")
    assert "1 registro" in html  # só o "cancelado" bate o filtro


def test_manage_recipe_steps_filtro_por_enum_nao_duplica_com_choices(app, client):
    """RecipeStep.step_type tem @enum_field E @choices — confirma que
    o filtro não quebra e não duplica a condição (skip quando o campo
    já está em _CHOICES_FIELDS)."""
    _login_admin(app, client)
    resp = client.get("/brewstation/recipe-steps/?filter_step_type=boil")
    assert resp.status_code == 200


def test_form_modal_html_nao_existe_mais():
    """form_modal.html.j2 confirmado morto (nunca referenciado) —
    removido do CrudGen e de todas as instâncias já geradas."""
    import os
    assert not os.path.exists("core/crudgen/templates/form_modal.html.j2")
    modals_dirs = []
    for root, dirs, files in os.walk("addons"):
        if root.endswith("_modals"):
            modals_dirs.append(root)
    assert modals_dirs == []
