"""
tests/test_phase1_core.py

Cobre os 3 pilares da Fase 1: app sobe (/health), tabelas de Core são
criadas, EventBus publica/recebe evento.

Roda em SQLite em memória (TESSERACT_ENV=testing) — nunca toca no
banco de dev real.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.module_state import ModuleState


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_endpoint_responde_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["project"] == "Tesseract"
    assert body["active_modules"] == []


def test_tabelas_de_core_sao_criadas(app):
    with app.app_context():
        # Não levanta exceção = tabela existe e o model está mapeado certo.
        count = ModuleState.query.count()
        assert count == 0


def test_event_bus_publica_e_recebe(app):
    from core.event_bus import event_bus

    recebido = {}

    def _listener(module_name, module_type):
        recebido["module_name"] = module_name
        recebido["module_type"] = module_type

    event_bus.subscribe("core.module.activated", _listener)

    with app.app_context():
        event_bus.publish(
            "core.module.activated",
            module_name="addon_teste",
            module_type="addon",
        )

    assert recebido == {"module_name": "addon_teste", "module_type": "addon"}


def test_listener_com_erro_nao_quebra_publish(app):
    """
    Regra do core/event_bus.py: um listener com erro não pode propagar
    a exceção pro publicador nem impedir os demais listeners.
    """
    from core.event_bus import event_bus

    chamado = {"ok": False}

    def _listener_com_erro(**kwargs):
        raise RuntimeError("listener proposital com erro")

    def _listener_ok(**kwargs):
        chamado["ok"] = True

    event_bus.subscribe("core.module.activated", _listener_com_erro)
    event_bus.subscribe("core.module.activated", _listener_ok)

    with app.app_context():
        # não deve levantar exceção
        event_bus.publish(
            "core.module.activated", module_name="x", module_type="addon"
        )

    assert chamado["ok"] is True
