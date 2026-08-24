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


# ── Função pura de cálculo (sempre linear — exponencial removido) ──────────

def test_modelo_linear_decai_corretamente():
    result = compute_estimated_viability(
        reference_viability=90.0,
        days=10, daily_loss_pct=1.0, correction_factor=1.0, floor_pct=0.0,
    )
    assert result == 80.0


def test_correction_factor_eh_aplicado():
    result = compute_estimated_viability(
        reference_viability=90.0,
        days=0, daily_loss_pct=1.0, correction_factor=0.5, floor_pct=0.0,
    )
    assert result == 45.0


def test_nunca_passa_do_piso_minimo():
    result = compute_estimated_viability(
        reference_viability=10.0,
        days=1000, daily_loss_pct=1.0, correction_factor=1.0, floor_pct=5.0,
    )
    assert result == 5.0


def test_nunca_passa_de_100():
    result = compute_estimated_viability(
        reference_viability=90.0,
        days=0, daily_loss_pct=1.0, correction_factor=2.0, floor_pct=0.0,
    )
    assert result == 100.0


# ── Prioridade de referência ─────────────────────────────────────────────────

def _make_container(app):
    from core.db import db
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_device import (
        YeastStorageDevice,
    )
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_container import (
        YeastContainer,
    )

    device = YeastStorageDevice(name="Freezer teste")
    db.session.add(device)
    db.session.commit()

    container = YeastContainer(name="Caixa teste", device_id=device.id)
    db.session.add(container)
    db.session.commit()
    return container


def _make_strain_and_item(app):
    from core.db import db
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem

    strain = YeastStrain(name="US-05", initial_reference_viability_pct=90.0)
    db.session.add(strain)
    db.session.commit()

    container = _make_container(app)
    item = YeastBankItem(
        strain_id=strain.id, storage_type="slant", container_id=container.id,
        prepared_date=datetime.date.today(),
    )
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

        container = _make_container(app)
        item = YeastBankItem(strain_id=strain.id, storage_type="slant", container_id=container.id)
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


# ── YeastBankConfig por storage_type (BACKLOG Fase 18) ──────────────────────

def test_config_do_storage_type_substitui_decaimento_da_cepa(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )

        strain, item = _make_strain_and_item(app)
        strain.daily_viability_loss_pct = 1.0  # decaimento da cepa
        db.session.commit()

        # Config do storage_type do item com decaimento BEM diferente
        # do da cepa — se a config for consultada de verdade, o
        # resultado bate com ela, não com o da cepa.
        config = YeastBankConfig(storage_type=item.storage_type, daily_viability_loss_pct=5.0)
        db.session.add(config)
        db.session.commit()

        item.prepared_date = datetime.date.today() - datetime.timedelta(days=10)
        db.session.commit()

        result = recalculate_all()
        assert result["updated"] == 1

        item = db.session.get(type(item), item.id)
        # referência = strain_default (90.0), 10 dias, 5%/dia (config) = 40.0
        # se estivesse usando o da cepa (1%/dia) daria 80.0
        assert item.estimated_viability_pct == 40.0


def test_sem_config_para_o_storage_type_usa_decaimento_da_cepa(app):
    with app.app_context():
        strain, item = _make_strain_and_item(app)
        strain.daily_viability_loss_pct = 1.0
        item.prepared_date = datetime.date.today() - datetime.timedelta(days=10)
        db.session.commit()

        # Nenhuma YeastBankConfig cadastrada pro storage_type do item.
        result = recalculate_all()
        assert result["updated"] == 1

        item = db.session.get(type(item), item.id)
        assert item.estimated_viability_pct == 80.0  # 90 - 1%*10 dias


def test_config_com_decaimento_vazio_nao_substitui_o_da_cepa(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )

        strain, item = _make_strain_and_item(app)
        strain.daily_viability_loss_pct = 1.0
        item.prepared_date = datetime.date.today() - datetime.timedelta(days=10)
        db.session.commit()

        # Config existe pro storage_type, mas sem decaimento preenchido
        # — não deve substituir o da cepa (só substitui quando presente).
        config = YeastBankConfig(storage_type=item.storage_type, expiry_days=90)
        db.session.add(config)
        db.session.commit()

        result = recalculate_all()
        item = db.session.get(type(item), item.id)
        assert item.estimated_viability_pct == 80.0


def test_expiry_date_e_preenchido_automaticamente_a_partir_da_config(app, client):
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(storage_type="Seca", expiry_days=180)
        db.session.add(config)
        db.session.commit()

        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        strain = YeastStrain(name="US-05")
        db.session.add(strain)
        db.session.commit()
        strain_id = strain.id
        container = _make_container(app)
        container_id = container.id

    r = client.post("/brewstation/yeast-bank-items/", data={
        "strain_id": str(strain_id), "storage_type": "Seca",
        "container_id": str(container_id), "prepared_date": "2026-01-01",
    })
    assert r.status_code in (200, 302)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import (
            YeastBankItem,
        )
        item = YeastBankItem.query.filter_by(strain_id=strain_id).first()
        assert item.expiry_date is not None
        assert item.expiry_date.isoformat() == "2026-06-30"  # 2026-01-01 + 180 dias


def test_expiry_date_manual_nao_e_sobrescrito_pela_config(app, client):
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(storage_type="Seca", expiry_days=180)
        db.session.add(config)
        db.session.commit()

        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        strain = YeastStrain(name="US-05")
        db.session.add(strain)
        db.session.commit()
        strain_id = strain.id
        container = _make_container(app)
        container_id = container.id

    r = client.post("/brewstation/yeast-bank-items/", data={
        "strain_id": str(strain_id), "storage_type": "Seca",
        "container_id": str(container_id), "prepared_date": "2026-01-01",
        "expiry_date": "2026-03-01",  # informado manualmente
    })
    assert r.status_code in (200, 302)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import (
            YeastBankItem,
        )
        item = YeastBankItem.query.filter_by(strain_id=strain_id).first()
        assert item.expiry_date.isoformat() == "2026-03-01"  # não sobrescrito


def test_evento_tipo_contagem_cria_cell_count_automaticamente(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]
    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer X"})
    device_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    item_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Contagem de Células"},
    )
    assert r.status_code == 201
    event_data = r.get_json()["item"]
    assert event_data["cell_count_id"] is not None
    assert event_data["starter_id"] is None  # não confunde os dois tipos

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import (
            YeastCellCountHistory,
        )
        count = YeastCellCountHistory.query.get(event_data["cell_count_id"])
        assert count.bank_item_id == item_id


def test_evento_tipo_descarte_nao_cria_registro_especializado(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]
    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer X"})
    device_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    item_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Descarte", "notes": "Contaminado"},
    )
    assert r.status_code == 201
    event_data = r.get_json()["item"]
    assert event_data["starter_id"] is None
    assert event_data["cell_count_id"] is None


def test_bank_config_recusa_storage_type_duplicado_ativo(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-bank-configs/", json={"storage_type": "Seca"})
    assert r.status_code == 201

    r = client.post("/api/brewstation/yeast-bank-configs/", json={"storage_type": "Seca"})
    assert r.status_code != 201  # índice único parcial recusa duplicata ativa


# ── Reanálise de eventos (2026-08-24): status real, readonly na API, alertas ──

def _make_item_via_api(client, storage_type="Agar Inclinado", **extra):
    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]
    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer X"})
    device_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]
    payload = {
        "strain_id": strain_id, "storage_type": storage_type,
        "container_id": container_id, "status": "active",
    }
    payload.update(extra)
    r = client.post("/api/brewstation/yeast-bank-items/", json=payload)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["item"]["id"]


def test_status_do_item_aceita_discarded_e_contaminated(app, client):
    # Achado real: o dropdown não tinha esses valores, mesmo sendo
    # exatamente o que viability_engine._SKIP_STATUSES espera.
    _login_admin(app, client)
    item_id = _make_item_via_api(client)

    r = client.put(f"/api/brewstation/yeast-bank-items/{item_id}", json={"status": "discarded"})
    assert r.status_code == 200
    assert r.get_json()["item"]["status"] == "discarded"


def test_evento_descarte_muda_status_real_do_item(app, client):
    _login_admin(app, client)
    item_id = _make_item_via_api(client)

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Descarte", "status_after": "contaminated"},
    )
    assert r.status_code == 201
    event = r.get_json()["item"]
    assert event["status_before"] == "active"
    assert event["status_after"] == "contaminated"

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    assert r.get_json()["item"]["status"] == "contaminated"


def test_evento_descarte_sem_status_after_usa_discarded_como_padrao(app, client):
    _login_admin(app, client)
    item_id = _make_item_via_api(client)

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Descarte"},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["status_after"] == "discarded"

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    assert r.get_json()["item"]["status"] == "discarded"


def test_status_before_nao_pode_ser_injetado_via_api(app, client):
    # @readonly_fields agora protege tanto o formulário quanto o
    # service.py.j2 — achado real: a primeira versão só protegia a
    # tela, a API aceitava o campo direto.
    _login_admin(app, client)
    item_id = _make_item_via_api(client)

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Outro", "status_before": "HACKED"},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["status_before"] is None  # ignorado, "Outro" não preenche


def test_starter_id_nao_pode_ser_injetado_via_api(app, client):
    _login_admin(app, client)
    item_id = _make_item_via_api(client)

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Outro", "starter_id": 999},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["starter_id"] is None  # ignorado — "Outro" não cria starter


def test_alerta_de_validade_dispara_quando_dentro_do_limite(app, client):
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(storage_type="Agar Inclinado", alert_days_before_expiry=10)
        db.session.add(config)
        db.session.commit()

    expiry = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    item_id = _make_item_via_api(client, expiry_date=expiry)

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    data = r.get_json()["item"]
    assert data["expiry_alert"] is True
    assert data["low_viability_alert"] is False


def test_alerta_de_viabilidade_dispara_quando_abaixo_do_minimo(app, client):
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(storage_type="Agar Inclinado", alert_min_viability_pct=50.0)
        db.session.add(config)
        db.session.commit()

    item_id = _make_item_via_api(client, estimated_viability_pct=30.0)

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    data = r.get_json()["item"]
    assert data["low_viability_alert"] is True
    assert data["expiry_alert"] is False


def test_sem_config_nenhum_alerta_dispara(app, client):
    _login_admin(app, client)
    item_id = _make_item_via_api(
        client,
        expiry_date=(datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
        estimated_viability_pct=1.0,
    )

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    data = r.get_json()["item"]
    assert data["expiry_alert"] is False
    assert data["low_viability_alert"] is False


def test_alerta_nao_cria_evento_nenhum(app, client):
    # Decisão do Christopher: só sinaliza pra tela, não cria
    # YeastBankEvent automaticamente.
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(storage_type="Agar Inclinado", alert_min_viability_pct=90.0)
        db.session.add(config)
        db.session.commit()

    _make_item_via_api(client, estimated_viability_pct=1.0)

    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import (
            YeastBankEvent,
        )
        assert YeastBankEvent.query.count() == 0


# ── Painel: estimativa de "próximo starter" (2026-08-24) ───────────────────

def test_proximo_starter_calculado_a_partir_da_config(app, client):
    _login_admin(app, client)
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(
            storage_type="Agar Inclinado",
            daily_viability_loss_pct=1.0,
            alert_min_viability_pct=50.0,
        )
        db.session.add(config)
        db.session.commit()

    item_id = _make_item_via_api(client, estimated_viability_pct=80.0)

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    data = r.get_json()["item"]
    assert data["next_starter_days"] == 30  # (80 - 50) / 1.0
    assert data["next_starter_date"] is not None


def test_proximo_starter_zero_quando_ja_abaixo_do_limite(app, client):
    _login_admin(app, client)
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        config = YeastBankConfig(
            storage_type="Agar Inclinado",
            daily_viability_loss_pct=1.0,
            alert_min_viability_pct=50.0,
        )
        db.session.add(config)
        db.session.commit()

    item_id = _make_item_via_api(client, estimated_viability_pct=20.0)  # já abaixo

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    assert r.get_json()["item"]["next_starter_days"] == 0


def test_proximo_starter_none_sem_decaimento_configurado(app, client):
    _login_admin(app, client)
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
            YeastBankConfig,
        )
        # Config existe, mas sem daily_viability_loss_pct — e a cepa
        # também precisa ter o decaimento zerado explicitamente
        # (YeastStrain.daily_viability_loss_pct tem default 0.35, não
        # fica None só por omissão na criação via API).
        config = YeastBankConfig(storage_type="Agar Inclinado", alert_min_viability_pct=50.0)
        db.session.add(config)
        db.session.commit()

    item_id = _make_item_via_api(client, estimated_viability_pct=80.0)
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import (
            YeastBankItem,
        )
        item = db.session.get(YeastBankItem, item_id)
        item.strain.daily_viability_loss_pct = None
        db.session.commit()

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    assert r.get_json()["item"]["next_starter_days"] is None


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
        container = _make_container(app)
        item = YeastBankItem(
            strain_id=strain_id, storage_type="slant", container_id=container.id,
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
