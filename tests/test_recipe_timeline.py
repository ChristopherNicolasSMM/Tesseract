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


# ── Etapa atual/próxima no Dashboard (conversa — Ponto 2) ───────────────────

def _gerar_sessao_ativa(recipe, plant):
    return svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão Ativa", status="active")


def test_generate_session_grava_source_recipe_step_id(app):
    with app.app_context():
        recipe = _criar_receita()
        mash, boil, alert = _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Source")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="draft")
        steps = BrewSessionStep.query.filter_by(session_id=session.id).order_by(BrewSessionStep.step_index).all()
        assert steps[0].source_recipe_step_id == mash.id
        assert steps[1].source_recipe_step_id == boil.id
        assert steps[2].source_recipe_step_id == alert.id


def test_get_step_card_data_ativa_primeiro_passo_pending_automaticamente(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Card 1")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)

        data = svc.get_step_card_data(session)
        assert data["current"] is not None
        assert data["current"]["step_type"] == "mash"
        assert data["current"]["phase"] == "hold"  # timeline de teste não tem ramp_time_min
        assert data["current"]["hold_progress_pct"] == 0.0
        assert data["next"] is not None
        assert data["next"]["step_type"] == "boil"


def test_get_step_card_data_sem_sessao_devolve_vazio(app):
    with app.app_context():
        assert svc.get_step_card_data(None) == {"current": None, "next": None}


def test_get_step_card_data_calcula_progresso_por_tempo_decorrido(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)  # mash: 40min = 2400s
        plant = BrewPlant(name="Planta Card 2")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)
        svc.get_step_card_data(session)  # ativa o primeiro passo (lazy)

        current_step = BrewSessionStep.query.filter_by(session_id=session.id, status="active").first()
        current_step.started_at = datetime.now(timezone.utc) - timedelta(seconds=1200)  # metade de 2400s
        db.session.commit()

        data = svc.get_step_card_data(session)
        assert data["current"]["phase"] == "hold"
        assert data["current"]["hold_progress_pct"] == pytest.approx(50.0, abs=1.0)


def test_confirm_and_advance_step_conclui_atual_e_ativa_proximo(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Avanco")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)

        data = svc.confirm_and_advance_step(session.id)
        assert data["current"]["step_type"] == "boil"

        mash_step = BrewSessionStep.query.filter_by(session_id=session.id, step_type="mash").first()
        assert mash_step.status == "completed"
        assert mash_step.completed_at is not None
        assert mash_step.actual_duration_s is not None

        boil_step = BrewSessionStep.query.filter_by(session_id=session.id, step_type="boil").first()
        assert boil_step.status == "active"
        assert boil_step.started_at is not None


def test_confirm_and_advance_step_sem_sessao_falha(app):
    with app.app_context():
        with pytest.raises(svc.RecipeTimelineError):
            svc.confirm_and_advance_step(999999)


def test_confirm_and_advance_step_ultimo_passo_nao_sobra_current(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)  # mash, boil, alert
        plant = BrewPlant(name="Planta Ultimo")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)

        svc.confirm_and_advance_step(session.id)  # mash -> boil
        data = svc.confirm_and_advance_step(session.id)  # boil -> nenhum mash/boil pending sobrando
        assert data["current"] is None


def test_resync_session_steps_cria_etapa_nova_da_receita(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Resync 1")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)
        antes = BrewSessionStep.query.filter_by(session_id=session.id, is_deleted=False).count()

        db.session.add(RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=3, nome="Mash Extra", temperatura=70, tempo_min=10))
        db.session.commit()

        result = svc.resync_session_steps(session.id)
        assert result["created"] == ["Mash Extra"]
        depois = BrewSessionStep.query.filter_by(session_id=session.id, is_deleted=False).count()
        assert depois == antes + 1


def test_resync_session_steps_atualiza_pending_alterado(app):
    with app.app_context():
        recipe = _criar_receita()
        mash, boil, alert = _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Resync 2")
        db.session.add(plant)
        db.session.commit()
        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="draft")

        boil.temperatura = 99
        boil.nome = "Fervura Ajustada"
        db.session.commit()

        result = svc.resync_session_steps(session.id)
        assert "Fervura Ajustada" in result["updated"]
        boil_step = BrewSessionStep.query.filter_by(session_id=session.id, source_recipe_step_id=boil.id).first()
        assert boil_step.target_temp == 99
        assert boil_step.name == "Fervura Ajustada"


def test_resync_session_steps_remove_pending_orfao(app):
    with app.app_context():
        recipe = _criar_receita()
        mash, boil, alert = _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Resync 3")
        db.session.add(plant)
        db.session.commit()
        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="draft")

        svc.remove_step(alert.id)  # some da timeline

        result = svc.resync_session_steps(session.id)
        assert "Lúpulo manual" in result["removed"]
        alert_step = BrewSessionStep.query.filter_by(session_id=session.id, source_recipe_step_id=alert.id).first()
        assert alert_step.is_deleted is True


def test_resync_session_steps_nunca_mexe_em_passo_ja_completo(app):
    with app.app_context():
        recipe = _criar_receita()
        mash, boil, alert = _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Resync 4")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)

        svc.confirm_and_advance_step(session.id)  # completa o mash

        mash.temperatura = 55  # muda a receita depois do passo já concluído
        db.session.commit()

        svc.resync_session_steps(session.id)
        mash_step = BrewSessionStep.query.filter_by(session_id=session.id, source_recipe_step_id=mash.id).first()
        assert mash_step.status == "completed"
        assert mash_step.target_temp == 67  # não foi sobrescrito — histórico é imutável


def test_resync_session_steps_sem_recipe_id_falha(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Receita")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="Sessão Solta", plant_id=plant.id, status="draft")
        db.session.add(session)
        db.session.commit()

        with pytest.raises(svc.RecipeTimelineError):
            svc.resync_session_steps(session.id)


# ── Rotas web do card de Etapa ───────────────────────────────────────────────

def test_advance_step_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Rota Avanco")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/advance-step")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["current"]["step_type"] == "boil"


def test_resync_steps_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Rota Resync")
        db.session.add(plant)
        db.session.commit()
        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="draft")
        session_id, recipe_id = session.id, recipe.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/resync-steps")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get(f"/brewstation/recipe-timeline/{recipe_id}/steps.json")
    assert resp2.status_code == 200
    assert len(resp2.get_json()["steps"]) == 3


# ── Rampa separada do hold (achado real pós-Ponto 2) ─────────────────────────

def test_generate_session_grava_ramp_seconds_separado_do_hold(app):
    with app.app_context():
        recipe = _criar_receita()
        mash = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash",
                           temperatura=67, tempo_min=40, ramp_time_min=10)
        db.session.add(mash)
        db.session.commit()
        plant = BrewPlant(name="Planta Ramp")
        db.session.add(plant)
        db.session.commit()

        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="draft")
        step = BrewSessionStep.query.filter_by(session_id=session.id).first()
        assert step.ramp_seconds == 600  # 10 min
        assert step.duration_seconds == 2400  # 40 min — hold, sem a rampa misturada


def test_get_step_card_data_fase_rampa_antes_do_alvo(app):
    with app.app_context():
        recipe = _criar_receita()
        mash = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash",
                           temperatura=67, tempo_min=40, ramp_time_min=10)
        db.session.add(mash)
        db.session.commit()
        plant = BrewPlant(name="Planta Ramp Fase")
        db.session.add(plant)
        db.session.commit()
        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="active")
        svc.get_step_card_data(session)  # ativa o primeiro passo (lazy)

        current_step = BrewSessionStep.query.filter_by(session_id=session.id, status="active").first()
        current_step.started_at = datetime.now(timezone.utc) - timedelta(seconds=300)  # metade dos 600s de rampa
        db.session.commit()

        data = svc.get_step_card_data(session)
        assert data["current"]["phase"] == "ramp"
        assert data["current"]["ramp_progress_pct"] == pytest.approx(50.0, abs=1.0)
        assert data["current"]["hold_progress_pct"] == 0.0
        assert data["current"]["remaining_seconds"] == pytest.approx(2700, abs=2)  # 600+2400-300


def test_get_step_card_data_fase_hold_apos_rampa_terminar(app):
    with app.app_context():
        recipe = _criar_receita()
        mash = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash",
                           temperatura=67, tempo_min=40, ramp_time_min=10)
        db.session.add(mash)
        db.session.commit()
        plant = BrewPlant(name="Planta Ramp Hold")
        db.session.add(plant)
        db.session.commit()
        session = svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="active")
        svc.get_step_card_data(session)

        current_step = BrewSessionStep.query.filter_by(session_id=session.id, status="active").first()
        # 600s de rampa + 1200s de hold (metade dos 2400s)
        current_step.started_at = datetime.now(timezone.utc) - timedelta(seconds=1800)
        db.session.commit()

        data = svc.get_step_card_data(session)
        assert data["current"]["phase"] == "hold"
        assert data["current"]["ramp_progress_pct"] == 100.0
        assert data["current"]["hold_progress_pct"] == pytest.approx(50.0, abs=1.0)


# ── "Voltar" (conversa — inspirado no painel de referência prev/next) ───────

def test_go_back_step_reativa_etapa_anterior(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Voltar")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)

        svc.confirm_and_advance_step(session.id)  # mash -> boil
        data = svc.go_back_step(session.id)

        assert data["current"]["step_type"] == "mash"
        mash_step = BrewSessionStep.query.filter_by(session_id=session.id, step_type="mash").first()
        assert mash_step.status == "active"
        assert mash_step.started_at is not None
        boil_step = BrewSessionStep.query.filter_by(session_id=session.id, step_type="boil").first()
        assert boil_step.status == "pending"
        assert boil_step.started_at is None


def test_go_back_step_sem_etapa_anterior_falha(app):
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Voltar Falha")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)
        svc.get_step_card_data(session)  # ativa o primeiro passo, nenhum completed ainda

        with pytest.raises(svc.RecipeTimelineError):
            svc.go_back_step(session.id)


def test_go_back_step_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = _criar_receita()
        _criar_timeline_completa(recipe)
        plant = BrewPlant(name="Planta Rota Voltar")
        db.session.add(plant)
        db.session.commit()
        session = _gerar_sessao_ativa(recipe, plant)
        session_id = session.id

    client.post(f"/brewstation/dashboards/sessions/{session_id}/advance-step")
    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/go-back-step")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["current"]["step_type"] == "mash"


# ── Select box de status (achado real reportado — não vinha como select) ────

def test_brew_session_detail_renderiza_select_para_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Status", status="active")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.get(f"/brewstation/brew-sessions/{session_id}")
    html = resp.data.decode("utf-8")
    assert '<select name="status"' in html
    assert 'value="active" selected' in html
    assert 'value="draft"' in html
    assert 'value="paused"' in html
    assert 'value="completed"' in html
    assert 'value="aborted"' in html
