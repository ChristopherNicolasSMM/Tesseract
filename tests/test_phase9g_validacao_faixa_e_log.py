"""
tests/test_phase9g_validacao_faixa_e_log.py

Cobre os 2 itens que fechavam a Fase D (docs/skills/05-*.md, decisão
2.6 e seção 5.1/5.2): validação de faixa (min_value/max_value) antes
de aceitar/publicar valor, e log de integração local em 3 camadas.
"""
import logging

import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services.integration_logger import (
    get_integration_logger, reset_for_tests,
)


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture(autouse=True)
def _reset_integration_logger():
    reset_for_tests()
    yield
    reset_for_tests()


def _criar_actor_com_faixa(*, name, min_value=None, max_value=None):
    function = DeviceFunction(
        name=f"func_{name}", display_name=name, category="actuator",
        min_value=min_value, max_value=max_value,
    )
    db.session.add(function)
    db.session.commit()

    device = DeviceMetadata(name=f"device_{name}")
    db.session.add(device)
    db.session.commit()

    actor = DeviceActor(device_id=device.id, port_name="GPIO1", function_id=function.id,
                         actor_type="actuator", name=name)
    db.session.add(actor)
    db.session.commit()
    return actor


# ── Validação de faixa ────────────────────────────────────────────────────────

def test_set_value_dentro_da_faixa_e_aceito(app):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="heater_faixa1", min_value=0, max_value=100)
        ok = device_service.set_value(actor.external_id, 85, publish=False)
        assert ok is True
        assert device_service.get_value(actor.external_id) == 85


def test_set_value_fora_da_faixa_e_rejeitado(app):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="heater_faixa2", min_value=0, max_value=100)
        ok = device_service.set_value(actor.external_id, 150, publish=False)
        assert ok is False
        # valor não deve ter sido aplicado
        assert device_service.get_value(actor.external_id) is None


def test_set_value_abaixo_do_minimo_e_rejeitado(app):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="heater_faixa3", min_value=10, max_value=100)
        ok = device_service.set_value(actor.external_id, 5, publish=False)
        assert ok is False


def test_set_value_sem_faixa_configurada_aceita_qualquer_valor(app):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="heater_sem_faixa")  # min/max None
        ok = device_service.set_value(actor.external_id, 99999, publish=False)
        assert ok is True


def test_set_value_valor_nao_numerico_ignora_validacao_de_faixa(app):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="pump_bool", min_value=0, max_value=1)
        ok = device_service.set_value(actor.external_id, True, publish=False)
        assert ok is True  # bool não é validado contra faixa numérica


def test_update_from_mqtt_fora_da_faixa_e_registrado_mesmo_assim(app, caplog):
    """
    Diferente de set_value: leitura de sensor fora de faixa NUNCA é
    rejeitada — é dado observado, não comando. Só gera log de erro.
    """
    with app.app_context():
        actor = _criar_actor_com_faixa(name="sensor_faixa1", min_value=0, max_value=100)
        with caplog.at_level(logging.ERROR, logger="addons.addon_device_manager.root.services.device_service"):
            device_service.update_from_mqtt(actor, 150)

        assert device_service.get_value(actor.external_id) == 150  # registrado mesmo fora de faixa
        assert any("fora da faixa" in r.message for r in caplog.records)


# ── Log de integração local ───────────────────────────────────────────────────

def test_log_de_integracao_e_gravado_em_arquivo_local(app, tmp_path, monkeypatch):
    with app.app_context():
        actor = _criar_actor_com_faixa(name="logtest1", min_value=0, max_value=100)
        device_service.set_value(actor.external_id, 50, publish=False)

        logger = get_integration_logger()
        log_files = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")]
        assert len(log_files) == 1
        assert log_files[0].endswith("integration.log")

        with open(log_files[0], encoding="utf-8") as f:
            content = f.read()
        assert "logtest1" in content
        assert "value=50" in content


def test_log_de_integracao_nao_propaga_para_log_global(app):
    """
    propagate=False — eventos de rotina não devem aparecer no logger
    raiz/global, só no arquivo local (decisão 2.6: log de alto volume
    não pode poluir o log central).
    """
    with app.app_context():
        logger = get_integration_logger()
        assert logger.propagate is False


def test_log_de_integracao_desabilitado_via_manifesto(app, monkeypatch):
    import addons.addon_device_manager.root.services.integration_logger as mod

    monkeypatch.setattr(mod, "_load_manifest_logging_config", lambda: {"integration_log_enabled": False})
    reset_for_tests()
    logger = get_integration_logger()
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
