"""
tests/test_logging_admin.py

Cobre a skill 08 (Logging, Observabilidade e Administração de Logs):
- formatter de console (cor só quando tty, formato HH:MM:SS);
- LogAdminService (listar fontes, ler conteúdo, apagar);
- tela admin (/admin/logs) — permissão "admin", igual às demais telas
  Core (decisão revisada: sem divisão logs.view/logs.delete).
"""
import logging

import pytest

from core.app_factory import create_app
from core.db import db
from core.log_admin_service import LogAdminService
from core.logging_config import _ConsoleFormatter
from model.core.user import User


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client, username="admin"):
    with app.app_context():
        admin = User(
            username=username, email=f"{username}@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()

    client.post("/api/auth/login", json={"username": username, "password": "senha123"})


def _login_sem_permissao(app, client, username="user_comum"):
    with app.app_context():
        user = User(
            username=username, email=f"{username}@test.local",
            nome="Comum", nome_completo="Usuário Comum", celular="11988888888",
            is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()

    client.post("/api/auth/login", json={"username": username, "password": "senha123"})


# ── Formatter de console ─────────────────────────────────────────────

def test_formatter_sem_cor_nao_inclui_codigo_ansi():
    formatter = _ConsoleFormatter(use_color=False)
    record = logging.LogRecord(
        name="device_manager.mqtt", level=logging.INFO, pathname=__file__,
        lineno=1, msg="teste", args=(), exc_info=None,
    )
    formatted = formatter.format(record)
    assert "\033[" not in formatted
    assert "device_manager.mqtt" in formatted
    assert "teste" in formatted


def test_formatter_com_cor_inclui_codigo_ansi_e_reset():
    formatter = _ConsoleFormatter(use_color=True)
    record = logging.LogRecord(
        name="core.module_manager", level=logging.ERROR, pathname=__file__,
        lineno=1, msg="falhou", args=(), exc_info=None,
    )
    formatted = formatter.format(record)
    assert "\033[31m" in formatted  # vermelho, nível ERROR
    assert formatted.endswith("\033[0m")


def test_formatter_usa_apenas_hora_sem_data():
    formatter = _ConsoleFormatter(use_color=False)
    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname=__file__,
        lineno=1, msg="m", args=(), exc_info=None,
    )
    formatted = formatter.format(record)
    # HH:MM:SS tem 8 caracteres antes do primeiro " | "; não deve
    # conter separador de data (skill 08 §3 — só hora, não datetime completo).
    prefix = formatted.split(" | ")[0]
    assert len(prefix) == 8
    assert prefix.count(":") == 2


# ── LogAdminService ───────────────────────────────────────────────────

def test_list_sources_sempre_inclui_log_global_do_core(app):
    with app.app_context():
        sources = LogAdminService.list_sources()
    ids = [s["id"] for s in sources]
    assert "core" in ids


def test_list_sources_inclui_addon_device_manager_com_logging_habilitado(app):
    with app.app_context():
        sources = LogAdminService.list_sources()
    ids = [s["id"] for s in sources]
    assert "addon:device_manager" in ids


def test_read_content_fonte_desconhecida_retorna_erro(app):
    with app.app_context():
        result = LogAdminService.read_content("fonte_que_nao_existe")
    assert result["error"] is not None
    assert result["lines"] == []


def test_read_content_arquivo_inexistente_retorna_erro_amigavel(app, tmp_path):
    with app.app_context():
        result = LogAdminService.read_content("core")
    # Em TESTING o handler de arquivo global é desligado (core/app_factory.py),
    # então o arquivo nunca existe — comportamento esperado, não é bug.
    assert result["error"] is not None
    assert result["lines"] == []


def test_delete_fonte_desconhecida_retorna_erro(app):
    with app.app_context():
        result = LogAdminService.delete("fonte_que_nao_existe")
    assert result["success"] is False


def test_delete_arquivo_real_remove_do_disco(app, tmp_path, monkeypatch):
    # _project_root()/"logs"/"core.log" é o caminho real esperado
    # (mesma estrutura da skill 08 §4) — precisa da subpasta "logs/".
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    fake_log = logs_dir / "core.log"
    fake_log.write_text("linha 1\nlinha 2\n", encoding="utf-8")

    import core.log_admin_service as mod
    monkeypatch.setattr(mod, "_project_root", lambda: tmp_path)

    with app.app_context():
        assert fake_log.exists()
        result = LogAdminService.delete("core")
        assert result["success"] is True
        assert not fake_log.exists()


# ── Tela admin (/admin/logs) ──────────────────────────────────────────

def test_admin_logs_sem_login_redireciona_para_login(client):
    # Rota HTML (não /api/) — unauthorized_handler (core/auth.py)
    # redireciona pra tela de login, não retorna 401 puro (esse
    # comportamento é só pras rotas /api/).
    resp = client.get("/admin/logs/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"] or "login" in resp.headers["Location"]


def test_admin_logs_logado_sem_permissao_retorna_403(app, client):
    _login_sem_permissao(app, client)
    resp = client.get("/admin/logs/")
    assert resp.status_code == 403


def test_admin_logs_admin_acessa_normalmente(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/logs/")
    assert resp.status_code == 200
    assert b"Log Global do Core" in resp.data


def test_tx_admin_logs_aponta_para_rota_html(app):
    from model.core.transaction import Transaction

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_LOGS").first()
        assert tx is not None
        assert tx.route == "/admin/logs"
        assert tx.permission_required == "admin"
