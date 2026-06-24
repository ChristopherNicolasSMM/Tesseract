"""
tests/test_viability_engine.py

Cobre o motor de viabilidade portado do BrewStation: cálculo linear e
exponencial, prioridade de referência (histórico real > histórico
estimado > starter > valor inicial da cepa), exclusão de contaminados,
skip de itens descartados, e a correção de onde a permissão vive
(YeastBankItem, não YeastStrain).
"""
import datetime

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_brewstation.features.feature_yeast_bank.services.viability_engine import (
    compute_estimated_viability,
    best_viability_reference_for_item,
    recalculate_all,
)


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


# ── Função pura de cálculo ───────────────────────────────────────────────────

def test_modelo_linear_decai_corretamente():
    result = compute_estimated_viability(
        model_id="linear_decay_default", reference_viability=90.0,
        days=10, daily_loss_pct=1.0, correction_factor=1.0, floor_pct=0.0,
    )
    assert result == 80.0


def test_modelo_exponencial_decai_corretamente():
    result = compute_estimated_viability(
        model_id="exp_decay", reference_viability=100.0,
        days=10, daily_loss_pct=5.0, correction_factor=1.0, floor_pct=0.0,
    )
    # 100 * e^(-0.05*10) ≈ 60.6531
    assert abs(result - 60.6531) < 0.01


def test_correction_factor_eh_aplicado():
    result = compute_estimated_viability(
        model_id="linear_decay_default", reference_viability=90.0,
        days=0, daily_loss_pct=1.0, correction_factor=0.5, floor_pct=0.0,
    )
    assert result == 45.0


def test_nunca_passa_do_piso_minimo():
    result = compute_estimated_viability(
        model_id="linear_decay_default", reference_viability=10.0,
        days=1000, daily_loss_pct=1.0, correction_factor=1.0, floor_pct=5.0,
    )
    assert result == 5.0


def test_nunca_passa_de_100():
    result = compute_estimated_viability(
        model_id="linear_decay_default", reference_viability=90.0,
        days=0, daily_loss_pct=1.0, correction_factor=2.0, floor_pct=0.0,
    )
    assert result == 100.0


# ── Prioridade de referência ─────────────────────────────────────────────────

def _make_strain_and_item(app):
    from core.db import db
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem

    strain = YeastStrain(name="US-05", initial_reference_viability_pct=90.0)
    db.session.add(strain)
    db.session.commit()

    item = YeastBankItem(strain_id=strain.id, storage_type="slant", prepared_date=datetime.date.today())
    db.session.add(item)
    db.session.commit()
    return strain, item


def test_referencia_cai_para_valor_inicial_da_cepa_sem_historico(app):
    with app.app_context():
        strain, item = _make_strain_and_item(app)
        ref = best_viability_reference_for_item(item)
        assert ref["type"] == "strain_default"
        assert ref["value"] == 90.0


def test_referencia_prefere_historico_real_sobre_valor_inicial(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory

        strain, item = _make_strain_and_item(app)
        hist = YeastCellCountHistory(
            bank_item_id=item.id, viability_percent=70.0,
            sample_date=datetime.date.today(), contamination_detected=False,
        )
        db.session.add(hist)
        db.session.commit()

        ref = best_viability_reference_for_item(item)
        assert ref["type"] == "count_history_real"
        assert ref["value"] == 70.0


def test_referencia_ignora_historico_contaminado(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory

        strain, item = _make_strain_and_item(app)
        hist = YeastCellCountHistory(
            bank_item_id=item.id, viability_percent=70.0,
            sample_date=datetime.date.today(), contamination_detected=True,
        )
        db.session.add(hist)
        db.session.commit()

        # contaminado é ignorado -> cai pro valor inicial da cepa
        ref = best_viability_reference_for_item(item)
        assert ref["type"] == "strain_default"


def test_referencia_prefere_starter_sobre_valor_inicial(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import YeastStarterLog

        strain, item = _make_strain_and_item(app)
        starter = YeastStarterLog(
            bank_item_id=item.id, result_viability_percent=60.0,
            start_date=datetime.date.today(), contamination_detected=False,
        )
        db.session.add(starter)
        db.session.commit()

        ref = best_viability_reference_for_item(item)
        assert ref["type"] == "starter"
        assert ref["value"] == 60.0


# ── recalculate_all / fluxo completo via HTTP ───────────────────────────────

def test_recalculate_all_pula_itens_descartados(app):
    with app.app_context():
        strain, item = _make_strain_and_item(app)
        item.status = "discarded"
        db.session.commit()

        result = recalculate_all()
        assert result["skipped"] == 1
        assert result["updated"] == 0


def test_recalculate_all_marca_sem_referencia_quando_nao_ha_cepa(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain

        strain = YeastStrain(name="Sem Referencia")
        db.session.add(strain)
        db.session.commit()

        # O default=95.0 da coluna se aplica no INSERT mesmo passando
        # None explicitamente no construtor (comportamento padrão do
        # SQLAlchemy) — força None de verdade via UPDATE separado,
        # onde o default não se aplica.
        strain.initial_reference_viability_pct = None
        db.session.commit()
        assert strain.initial_reference_viability_pct is None

        item = YeastBankItem(strain_id=strain.id, storage_type="slant")
        db.session.add(item)
        db.session.commit()

        result = recalculate_all()
        assert result["items_without_reference"] == 1


def test_permissao_e_rota_estao_no_lugar_certo_yeast_bank_items(app, client):
    from model.core.permission import Permission

    with app.app_context():
        nomes = {p.name for p in Permission.query.all()}
        assert "yeast_bank_items.recalculate_viability" in nomes
        assert "yeast_strains.recalculate_viability" not in nomes


def test_fluxo_completo_via_http(app, client):
    _login_admin(app, client)

    r = client.post("/brewstation/yeast-strains/", data={
        "name": "US-05", "daily_viability_loss_pct": "1.0",
        "initial_reference_viability_pct": "90",
    })
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        strain_id = YeastStrain.query.first().id

        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
        item = YeastBankItem(
            strain_id=strain_id, storage_type="slant",
            prepared_date=datetime.date.today() - datetime.timedelta(days=10),
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    r = client.get("/brewstation/yeast-bank-tools/recalculate-viability")
    assert r.status_code == 200

    r = client.post("/brewstation/yeast-bank-tools/recalculate-viability")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["updated"] == 1

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
        item = YeastBankItem.query.get(item_id)
        assert item.estimated_viability_pct == 80.0
        assert item.last_viability_reference_type == "strain_default"
