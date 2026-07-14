"""
tests/test_recipe_timeline.py

Cobre a timeline única de receita (RecipeStep, substitui MashStep —
decisão confirmada em conversa): sync automático de alertas de
lupulagem, CRUD/reorder de etapa, geração de Sessão (snapshot da
timeline, cálculo de trigger_at_seconds), disparo automático de
alerta durante sessão ativa, e ajuste em tempo de execução virando
histórico (BrewSessionLog).
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service as svc


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


def _criar_receita(name="Lagers da Casa"):
    r = MashRecipe(name=name)
    db.session.add(r)
    db.session.commit()
    return r


def _criar_timeline_completa(recipe):
    mash = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash", temperatura=67, tempo_min=40)
    boil = RecipeStep(recipe_id=recipe.id, step_type="boil", ordem=1, nome="Fervura", temperatura=100, tempo_min=60)
    db.session.add_all([mash, boil])
    db.session.commit()
    alert = RecipeStep(recipe_id=recipe.id, step_type="alert", ordem=2, nome="Lúpulo manual",
                        trigger_minutes_remaining=15, parent_step_id=boil.id, source="manual")
    db.session.add(alert)
    db.session.commit()
    return mash, boil, alert


# ── Sync automático de alertas de lupulagem ("toda lupulagem cria alertas") ──

def test_sync_hop_alerts_cria_alerta_pra_lupulo_com_tempo_de_adicao(app):
    with app.app_context():
        recipe = _criar_receita()
        boil = RecipeStep(recipe_id=recipe.id, step_type="boil", ordem=0, nome="Fervura", tempo_min=60)
        db.session.add(boil)
        db.session.commit()
        hop = RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Magnum 30g", quantidade=30, unidade_medida="g",
            tempo_adicao_min=60, etapa="fervura", tipo_ingrediente="lupulo",
        )
        db.session.add(hop)
        db.session.commit()

        result = svc.sync_hop_alerts(recipe)
        assert len(result["created"]) == 1

        alert = RecipeStep.query.filter_by(recipe_id=recipe.id, step_type="alert", source="auto_hop").first()
        assert alert is not None
        assert alert.trigger_minutes_remaining == 60
        assert alert.parent_step_id == boil.id
        assert "Magnum" in alert.nome


def test_sync_hop_alerts_ignora_lupulo_sem_tempo_de_adicao(app):
    with app.app_context():
        recipe = _criar_receita()
        db.session.add(RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Dry hop", quantidade=20, unidade_medida="g",
            etapa="fervura", tipo_ingrediente="lupulo",  # sem tempo_adicao_min
        ))
        db.session.commit()

        result = svc.sync_hop_alerts(recipe)
        assert result["created"] == []


def test_sync_hop_alerts_e_idempotente(app):
    with app.app_context():
        recipe = _criar_receita()
        db.session.add(RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Magnum", quantidade=30, unidade_medida="g",
            tempo_adicao_min=60, etapa="fervura", tipo_ingrediente="lupulo",
        ))
        db.session.commit()

        svc.sync_hop_alerts(recipe)
        result2 = svc.sync_hop_alerts(recipe)
        assert result2["created"] == []  # segunda chamada não duplica

        alerts = RecipeStep.query.filter_by(recipe_id=recipe.id, step_type="alert", source="auto_hop").all()
        assert len(alerts) == 1


def test_sync_hop_alerts_atualiza_se_quantidade_mudou(app):
    with app.app_context():
        recipe = _criar_receita()
        hop = RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Magnum", quantidade=30, unidade_medida="g",
            tempo_adicao_min=60, etapa="fervura", tipo_ingrediente="lupulo",
        )
        db.session.add(hop)
        db.session.commit()
        svc.sync_hop_alerts(recipe)

        hop.tempo_adicao_min = 45
        db.session.commit()
        result = svc.sync_hop_alerts(recipe)
        assert len(result["updated"]) == 1

        alert = RecipeStep.query.filter_by(recipe_id=recipe.id, step_type="alert", source="auto_hop").first()
        assert alert.trigger_minutes_remaining == 45


def test_sync_hop_alerts_remove_se_ingrediente_sumiu(app):
    with app.app_context():
        recipe = _criar_receita()
        hop = RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Magnum", quantidade=30, unidade_medida="g",
            tempo_adicao_min=60, etapa="fervura", tipo_ingrediente="lupulo",
        )
        db.session.add(hop)
        db.session.commit()
        svc.sync_hop_alerts(recipe)

        hop.is_deleted = True
        db.session.commit()
        result = svc.sync_hop_alerts(recipe)
        assert len(result["removed"]) == 1

        alert = RecipeStep.query.filter_by(recipe_id=recipe.id, step_type="alert", source="auto_hop").first()
        assert alert.is_deleted is True


def test_sync_hop_alerts_nunca_toca_alerta_manual(app):
    with app.app_context():
        recipe = _criar_receita()
        manual_alert = RecipeStep(recipe_id=recipe.id, step_type="alert", ordem=0, nome="Alerta manual",
                                   trigger_minutes_remaining=30, source="manual")
        db.session.add(manual_alert)
        db.session.commit()

        svc.sync_hop_alerts(recipe)

        db.session.refresh(manual_alert)
        assert manual_alert.is_deleted is False
        assert manual_alert.nome == "Alerta manual"


# ── CRUD/reorder da timeline ──────────────────────────────────────────────

def test_add_step_tipo_invalido_falha(app):
    with app.app_context():
        recipe = _criar_receita()
        with pytest.raises(svc.RecipeTimelineError):
            svc.add_step(recipe.id, step_type="fermentacao", nome="X")


def test_reorder_steps(app):
    with app.app_context():
        recipe = _criar_receita()
        s1 = svc.add_step(recipe.id, step_type="mash", nome="A")
        s2 = svc.add_step(recipe.id, step_type="mash", nome="B")
        s3 = svc.add_step(recipe.id, step_type="mash", nome="C")

        svc.reorder_steps(recipe.id, [s3.id, s1.id, s2.id])

        timeline = svc.get_timeline(recipe.id)
        assert [s.nome for s in timeline] == ["C", "A", "B"]


def test_remove_step_e_soft_delete(app):
    with app.app_context():
        recipe = _criar_receita()
        step = svc.add_step(recipe.id, step_type="mash", nome="X")
        svc.remove_step(step.id)
        assert RecipeStep.query.get(step.id).is_deleted is True
        assert svc.get_timeline(recipe.id) == []


# ── Geração de Sessão ("lote temporário ou não") ─────────────────────────

def test_generate_session_status_draft_nao_seta_started_at(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta X")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão 1", status="draft")
        assert session.status == "draft"
        assert session.started_at is None


def test_generate_session_status_active_seta_started_at(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Y")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão 2", status="active")
        assert session.status == "active"
        assert session.started_at is not None


def test_generate_session_copia_steps_snapshot(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Z")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão 3", status="draft")

        steps = BrewSessionStep.query.filter_by(session_id=session.id).order_by(BrewSessionStep.step_index).all()
        assert len(steps) == 3  # mash + boil + alert
        assert steps[0].step_type == "mash"
        assert steps[0].target_temp == 67
        assert steps[1].step_type == "boil"
        assert steps[2].step_type == "alert"


def test_generate_session_calcula_trigger_at_seconds_corretamente(app):
    """Mash 40min + Boil 60min (termina em 100min) — alerta a -15min do
    fim da fervura dispara aos 85min = 5100s."""
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta W")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão 4", status="draft")

        alert_step = BrewSessionStep.query.filter_by(session_id=session.id, step_type="alert").first()
        assert alert_step.trigger_at_seconds == 85 * 60


def test_generate_session_sem_timeline_falha(app):
    with app.app_context():
        recipe = _criar_receita()
        plant = BrewPlant(name="Planta Vazia")
        db.session.add(plant)
        db.session.commit()

        with pytest.raises(svc.RecipeTimelineError):
            svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="X", status="draft")


def test_generate_session_status_invalido_falha(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Inv")
        db.session.add(plant)
        db.session.commit()

        with pytest.raises(svc.RecipeTimelineError):
            svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="X", status="paused")


# ── Disparo automático de alerta ──────────────────────────────────────────

def test_check_and_fire_alerts_dispara_quando_vencido(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Disparo")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(
            name="S Disparo", plant_id=plant.id, status="active",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        )
        db.session.add(session)
        db.session.commit()
        step = BrewSessionStep(
            session_id=session.id, step_index=0, name="Lúpulo!", step_type="alert",
            trigger_at_seconds=60,  # já passou (120s decorridos)
        )
        db.session.add(step)
        db.session.commit()

        fired = svc.check_and_fire_alerts(session)
        assert len(fired) == 1
        assert BrewSessionAlarm.query.filter_by(session_id=session.id).count() == 1

        db.session.refresh(step)
        assert step.alarm_fired is True


def test_check_and_fire_alerts_nao_dispara_duas_vezes(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Disparo2")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(
            name="S Disparo2", plant_id=plant.id, status="active",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        )
        db.session.add(session)
        db.session.commit()
        db.session.add(BrewSessionStep(
            session_id=session.id, step_index=0, name="Lúpulo!", step_type="alert", trigger_at_seconds=60,
        ))
        db.session.commit()

        svc.check_and_fire_alerts(session)
        fired2 = svc.check_and_fire_alerts(session)
        assert fired2 == []
        assert BrewSessionAlarm.query.filter_by(session_id=session.id).count() == 1


def test_check_and_fire_alerts_nao_dispara_antes_da_hora(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Disparo3")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(
            name="S Disparo3", plant_id=plant.id, status="active",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        db.session.add(session)
        db.session.commit()
        db.session.add(BrewSessionStep(
            session_id=session.id, step_index=0, name="Lúpulo!", step_type="alert", trigger_at_seconds=600,
        ))
        db.session.commit()

        fired = svc.check_and_fire_alerts(session)
        assert fired == []


def test_check_and_fire_alerts_sessao_sem_started_at_nao_falha(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Draft")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S Draft", plant_id=plant.id, status="draft")
        db.session.add(session)
        db.session.commit()

        assert svc.check_and_fire_alerts(session) == []


# ── Ajuste em tempo de execução vira histórico ────────────────────────────

def test_adjust_session_step_grava_log(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Ajuste")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S Ajuste", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()
        step = BrewSessionStep(session_id=session.id, step_index=0, name="Mash", step_type="mash", target_temp=65)
        db.session.add(step)
        db.session.commit()

        svc.adjust_session_step(step.id, field="target_temp", new_value=68, user_id=1)

        db.session.refresh(step)
        assert step.target_temp == 68
        log = BrewSessionLog.query.filter_by(session_id=session.id, source="user").first()
        assert log is not None
        assert log.detail_json["old_value"] == 65
        assert log.detail_json["new_value"] == 68


def test_adjust_session_step_campo_nao_permitido_falha(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Ajuste2")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S Ajuste2", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()
        step = BrewSessionStep(session_id=session.id, step_index=0, name="Mash", step_type="mash")
        db.session.add(step)
        db.session.commit()

        with pytest.raises(svc.RecipeTimelineError):
            svc.adjust_session_step(step.id, field="session_id", new_value=999)


# ── Rotas web ────────────────────────────────────────────────────────────────

def test_picker_lista_receitas(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_receita("Receita Visível")

    resp = client.get("/brewstation/recipe-timeline/")
    assert resp.status_code == 200
    assert b"Receita Vis" in resp.data


def test_view_sincroniza_hop_alerts_automaticamente(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita("Receita Auto Sync")
        boil = RecipeStep(recipe_id=recipe.id, step_type="boil", ordem=0, nome="Fervura", tempo_min=60)
        db.session.add(boil)
        db.session.add(RecipeIngredient(
            recipe_id=recipe.id, descricao_origem="Cascade", quantidade=15, unidade_medida="g",
            tempo_adicao_min=10, etapa="fervura", tipo_ingrediente="lupulo",
        ))
        db.session.commit()
        recipe_id = recipe.id

    resp = client.get(f"/brewstation/recipe-timeline/{recipe_id}")
    assert resp.status_code == 200
    assert b"Cascade" in resp.data

    with app.app_context():
        assert RecipeStep.query.filter_by(recipe_id=recipe_id, source="auto_hop").count() == 1


def test_add_step_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita("Receita Add Step")
        recipe_id = recipe.id

    resp = client.post(f"/brewstation/recipe-timeline/{recipe_id}/steps", json={
        "step_type": "mash", "nome": "Mash Web", "temperatura": 66, "tempo_min": 30,
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        assert RecipeStep.query.filter_by(recipe_id=recipe_id, nome="Mash Web").count() == 1


def test_generate_session_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita("Receita Gerar Sessão")
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Rota")
        db.session.add(plant)
        db.session.commit()
        recipe_id, plant_id = recipe.id, plant.id

    resp = client.post(f"/brewstation/recipe-timeline/{recipe_id}/generate-session", data={
        "name": "Sessão via Web", "plant_id": str(plant_id), "status": "draft",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        session = BrewSession.query.filter_by(name="Sessão via Web").first()
        assert session is not None
        assert session.status == "draft"
        assert BrewSessionStep.query.filter_by(session_id=session.id).count() == 3
