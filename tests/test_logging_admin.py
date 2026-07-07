"""
tests/test_logging_admin.py

Cobre a skill 08 (Logging, Observabilidade e Administração de Logs):
- formatter de console (cor só quando tty, formato HH:MM:SS);
- LogAdminService (listar fontes, ler conteúdo, apagar);
- tela admin (/admin/logs) — permissão "admin", igual às demais telas
  Core (decisão revisada: sem divisão logs.view/logs.delete).
"""
import logging
from datetime import datetime

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


# ── Item (b): parsing de linha + filtro de data/hora + cor por nível ──

def _criar_log_de_teste(tmp_path, monkeypatch, conteudo: str):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    fake_log = logs_dir / "core.log"
    fake_log.write_text(conteudo, encoding="utf-8")

    import core.log_admin_service as mod
    monkeypatch.setattr(mod, "_project_root", lambda: tmp_path)
    return fake_log


def test_parse_lines_extrai_timestamp_nivel_logger_mensagem(app, tmp_path, monkeypatch):
    conteudo = (
        "2026-07-07 10:00:00 | INFO     | core.module_manager | Boot concluído\n"
        "2026-07-07 10:00:05 | ERROR    | core.some_module | Falha ao conectar\n"
    )
    _criar_log_de_teste(tmp_path, monkeypatch, conteudo)

    with app.app_context():
        result = LogAdminService.read_content("core")

    assert result["error"] is None
    assert len(result["records"]) == 2
    assert result["records"][0]["level"] == "INFO"
    assert result["records"][0]["logger"] == "core.module_manager"
    assert result["records"][0]["message"] == "Boot concluído"
    assert result["records"][1]["level"] == "ERROR"


def test_parse_lines_linha_de_continuacao_anexa_a_mensagem_anterior(app, tmp_path, monkeypatch):
    """Traceback multi-linha (sem o prefixo padrão) não vira registro novo sem nível."""
    conteudo = (
        "2026-07-07 10:00:00 | ERROR    | core.request_error_logging | Exceção não tratada\n"
        "Traceback (most recent call last):\n"
        '  File "app.py", line 10, in <module>\n'
        "ValueError: algo deu errado\n"
    )
    _criar_log_de_teste(tmp_path, monkeypatch, conteudo)

    with app.app_context():
        result = LogAdminService.read_content("core")

    assert len(result["records"]) == 1
    assert "Traceback" in result["records"][0]["message"]
    assert "ValueError" in result["records"][0]["message"]


def test_filtro_desde_ate_ignora_limite_de_max_lines(app, tmp_path, monkeypatch):
    """Filtro ativo varre o arquivo inteiro, mesmo além do tail padrão."""
    linhas = [f"2026-07-07 10:{i:02d}:00 | INFO     | core.x | linha {i}\n" for i in range(5)]
    _criar_log_de_teste(tmp_path, monkeypatch, "".join(linhas))

    with app.app_context():
        # max_lines=2 forçaria tail sem filtro - com filtro, ignora isso.
        result = LogAdminService.read_content(
            "core", max_lines=2,
            desde=datetime(2026, 7, 7, 10, 1, 0),
            ate=datetime(2026, 7, 7, 10, 3, 0),
        )

    assert result["error"] is None
    assert [r["message"] for r in result["records"]] == ["linha 1", "linha 2", "linha 3"]


def test_filtro_sem_correspondencia_devolve_lista_vazia(app, tmp_path, monkeypatch):
    conteudo = "2026-07-07 10:00:00 | INFO     | core.x | linha 0\n"
    _criar_log_de_teste(tmp_path, monkeypatch, conteudo)

    with app.app_context():
        result = LogAdminService.read_content(
            "core", desde=datetime(2026, 7, 8, 0, 0, 0),
        )

    assert result["error"] is None
    assert result["records"] == []


def test_tela_de_detalhe_renderiza_cor_por_nivel(app, client, tmp_path, monkeypatch):
    conteudo = (
        "2026-07-07 10:00:00 | INFO     | core.x | mensagem info\n"
        "2026-07-07 10:00:01 | ERROR    | core.x | mensagem erro\n"
    )
    _criar_log_de_teste(tmp_path, monkeypatch, conteudo)
    _login_admin(app, client)

    resp = client.get("/admin/logs/view/core")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "log-level-info" in html
    assert "log-level-error" in html


def test_tela_de_detalhe_aceita_filtro_via_querystring(app, client, tmp_path, monkeypatch):
    conteudo = (
        "2026-07-07 10:00:00 | INFO     | core.x | fora do filtro\n"
        "2026-07-07 12:00:00 | INFO     | core.x | dentro do filtro\n"
    )
    _criar_log_de_teste(tmp_path, monkeypatch, conteudo)
    _login_admin(app, client)

    resp = client.get("/admin/logs/view/core?desde=2026-07-07T11:00&ate=2026-07-07T13:00")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "dentro do filtro" in html
    assert "fora do filtro" not in html
