"""
tests/test_phase9e_task_system.py

Cobre o sistema de tasks portado do PyTeca (ScheduledTask, TaskLog,
MessageQueue, TaskService) — decisão de 2026-06-29 de portar como
infraestrutura geral do Core, antes da Fase E do device_manager. Ver
docs/skills/05-proposta-addon-device-manager-e-mqtt.md.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.scheduled_task import ScheduledTask
from model.core.task_log import TaskLog
from model.core.transaction import Transaction
from services.core.task_service import TaskService
from core.task_registry import register_task, list_registered_tasks


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


# ── Transação no catálogo ────────────────────────────────────────────────────

def test_tx_admin_tasks_existe_no_grupo_admin(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_TASKS").first()
        assert tx is not None
        assert tx.parent is not None
        assert tx.parent.label == "Admin"  # skill 10: grupo agora é o nó-pai
        assert tx.route == "/admin/tasks"


# ── CRUD de tarefa ────────────────────────────────────────────────────────────

def test_create_e_get_task(app, client):
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "Task Teste", "task_type": "python_call",
        "target": "tasks_test.dummy", "schedule": "60",
    })
    assert r.status_code == 201
    task_id = r.get_json()["data"]["id"]

    r = client.get(f"/api/admin/tasks/{task_id}")
    assert r.status_code == 200
    assert r.get_json()["data"]["name"] == "Task Teste"


def test_create_task_campo_obrigatorio_faltando(app, client):
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={"name": "Sem tipo"})
    assert r.status_code == 400


def test_pause_e_activate_task(app, client):
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "Pausavel", "task_type": "sql", "target": "SELECT 1", "schedule": "30",
    })
    task_id = r.get_json()["data"]["id"]

    r = client.post(f"/api/admin/tasks/{task_id}/pause")
    assert r.get_json()["data"]["status"] == "paused"

    r = client.post(f"/api/admin/tasks/{task_id}/activate")
    assert r.get_json()["data"]["status"] == "active"


def test_delete_task(app, client):
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "Deletavel", "task_type": "sql", "target": "SELECT 1", "schedule": "30",
    })
    task_id = r.get_json()["data"]["id"]

    r = client.delete(f"/api/admin/tasks/{task_id}")
    assert r.status_code == 200

    r = client.get(f"/api/admin/tasks/{task_id}")
    assert r.status_code == 404


# ── Execução imediata (run_now) ──────────────────────────────────────────────

def test_run_now_python_call_via_task_registry(app):
    with app.app_context():
        register_task("tasks_test.soma_dummy", lambda: 1 + 1)
        assert "tasks_test.soma_dummy" in list_registered_tasks()

        task = ScheduledTask(name="Soma", task_type="python_call",
                              target="tasks_test.soma_dummy", schedule="60")
        db.session.add(task)
        db.session.commit()

        result = TaskService.run_now(task.id)
        assert result["success"] is True
        assert result["result"] == "2"

        log = TaskLog.query.filter_by(task_id=task.id).first()
        assert log.status == "success"


def test_run_now_python_call_funcao_nao_registrada_falha(app):
    with app.app_context():
        task = ScheduledTask(name="Falha", task_type="python_call",
                              target="nao_existe.em_lugar_nenhum", schedule="60")
        db.session.add(task)
        db.session.commit()

        result = TaskService.run_now(task.id)
        assert result["success"] is False

        log = TaskLog.query.filter_by(task_id=task.id).first()
        assert log.status == "failure"


def test_run_now_via_api(app, client):
    with app.app_context():
        register_task("tasks_test.via_api", lambda: "ok-api")
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "Via API", "task_type": "python_call",
        "target": "tasks_test.via_api", "schedule": "60",
    })
    task_id = r.get_json()["data"]["id"]

    r = client.post(f"/api/admin/tasks/{task_id}/run")
    assert r.status_code == 200
    assert r.get_json()["data"]["result"] == "ok-api"


# ── Logs: filtro por task e busca textual ────────────────────────────────────

def test_logs_filtrados_por_task_id(app, client):
    with app.app_context():
        register_task("tasks_test.a", lambda: "A")
        register_task("tasks_test.b", lambda: "B")

    _login_admin(app, client)
    r1 = client.post("/api/admin/tasks/", json={
        "name": "Task A", "task_type": "python_call", "target": "tasks_test.a", "schedule": "60",
    })
    task_a_id = r1.get_json()["data"]["id"]
    r2 = client.post("/api/admin/tasks/", json={
        "name": "Task B", "task_type": "python_call", "target": "tasks_test.b", "schedule": "60",
    })
    task_b_id = r2.get_json()["data"]["id"]

    client.post(f"/api/admin/tasks/{task_a_id}/run")
    client.post(f"/api/admin/tasks/{task_b_id}/run")

    r = client.get(f"/api/admin/tasks/{task_a_id}/logs")
    items = r.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["task_name"] == "Task A"


def test_logs_busca_textual_por_nome_da_task(app, client):
    with app.app_context():
        register_task("tasks_test.x", lambda: "X")

    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "Tarefa Unica XYZ123", "task_type": "python_call",
        "target": "tasks_test.x", "schedule": "60",
    })
    task_id = r.get_json()["data"]["id"]
    client.post(f"/api/admin/tasks/{task_id}/run")

    r = client.get("/api/admin/tasks/logs?q=XYZ123")
    items = r.get_json()["data"]["items"]
    assert len(items) == 1
    assert "XYZ123" in items[0]["task_name"]

    r = client.get("/api/admin/tasks/logs?q=nao-existe-nada-com-isso")
    assert r.get_json()["data"]["items"] == []


# ── Fila de mensagens ─────────────────────────────────────────────────────────

def test_enqueue_e_list_queue(app, client):
    with app.app_context():
        TaskService.enqueue("webhook", {"url": "http://example.invalid", "data": {}})
    _login_admin(app, client)
    r = client.get("/api/admin/tasks/queue")
    assert r.status_code == 200
    assert r.get_json()["data"]["total"] >= 1


def test_cancel_message(app, client):
    with app.app_context():
        msg = TaskService.enqueue("webhook", {"url": "http://x.invalid"})
        msg_id = msg.id
    _login_admin(app, client)
    r = client.post(f"/api/admin/tasks/queue/{msg_id}/cancel")
    assert r.status_code == 200


# ── Stats do monitor ──────────────────────────────────────────────────────────

def test_stats_endpoint(app, client):
    _login_admin(app, client)
    r = client.get("/api/admin/tasks/stats")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert "active_tasks" in data
    assert "daily_chart" in data


# ── Integração com addon_device_manager ──────────────────────────────────────

def test_device_manager_registra_mqtt_reconnect_no_boot(app):
    """
    addon_device_manager.register_routes() registra
    'device_manager.mqtt_reconnect' no TASK_REGISTRY assim que a app
    sobe — confirma a integração Fase D <-> sistema de tasks (Fase 9).
    """
    with app.app_context():
        assert "device_manager.mqtt_reconnect" in list_registered_tasks()


def test_run_now_mqtt_reconnect_sem_cliente_ativo(app, client):
    """
    Sem MQTT_ENABLED=true (padrão em TESTING), mqtt_client_service
    nunca foi iniciado — reconnect() deve retornar False sem lançar
    exceção, e a task ainda é marcada 'success' (False é um retorno
    válido, não um erro).
    """
    _login_admin(app, client)
    r = client.post("/api/admin/tasks/", json={
        "name": "MQTT Reconnect Teste", "task_type": "python_call",
        "target": "device_manager.mqtt_reconnect", "schedule": "60",
    })
    task_id = r.get_json()["data"]["id"]

    r = client.post(f"/api/admin/tasks/{task_id}/run")
    assert r.status_code == 200
    assert r.get_json()["data"]["result"] == "False"


def test_pagina_monitor_carrega(app, client):
    _login_admin(app, client)
    r = client.get("/admin/tasks/")
    assert r.status_code == 200
    assert b"Monitor de Tarefas" in r.data
