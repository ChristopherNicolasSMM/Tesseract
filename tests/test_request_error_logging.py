"""
tests/test_request_error_logging.py

Confirma que got_request_exception loga com blueprint/endpoint,
sem interferir no fluxo normal de exceção (debugger continua
funcionando; a exceção ainda propaga em TESTING).
"""
import logging

import pytest

from core.app_factory import create_app


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_log_de_erro_capturado_com_blueprint_e_endpoint(app, client, caplog):
    # Rota real que existe mas vamos forçar erro passando id inexistente
    # não gera exceção (retorna flash) — usamos uma rota que sabemos que
    # pode ser induzida a erro: detail de receita inexistente redireciona,
    # não gera exceção real. Para testar o hook em si, disparamos
    # manualmente via um endpoint de teste.
    from flask import Blueprint

    test_bp = Blueprint("test_error_logging", __name__, url_prefix="/__test_error")

    @test_bp.route("/boom")
    def boom():
        raise ValueError("erro proposital para testar o log")

    app.register_blueprint(test_bp)

    with caplog.at_level(logging.ERROR, logger="core.request_errors"):
        with pytest.raises(ValueError):
            client.get("/__test_error/boom")

    mensagens = [r.message for r in caplog.records if r.name == "core.request_errors"]
    assert any("test_error_logging" in m and "boom" in m for m in mensagens)
