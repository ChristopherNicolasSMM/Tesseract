"""
core/request_error_logging.py

Log estruturado de exceções não tratadas em requisições HTTP —
complementa (não substitui) o traceback que o Werkzeug já mostra em
modo debug. Usa o sinal got_request_exception do Flask, que dispara
ANTES do tratamento da exceção (debugger interativo continua
funcionando normalmente em desenvolvimento).

Motivação: um erro de template/view hoje só aparece no console como
traceback puro — sem indicação rápida de qual Addon/Feature/rota
falhou. Esse log adiciona uma linha ERROR única, fácil de grep,
identificando blueprint (mapeia para a entidade/Feature) e endpoint
(a ação específica que estava sendo executada).

Não substitui a tela de erro do Flask/Werkzeug (debug ou produção) —
só garante que o arquivo de log central (core.log) tenha um registro
claro e buscável de cada falha, mesmo quando ninguém está olhando o
console no momento em que ela acontece.
"""
import logging

from flask import request, got_request_exception

logger = logging.getLogger("core.request_errors")


def _log_request_exception(sender, exception, **extra) -> None:
    blueprint = request.blueprint or "core"
    endpoint = request.endpoint or "?"
    logger.error(
        "[%s] erro não tratado em endpoint=%s path=%s método=%s: %s",
        blueprint, endpoint, request.path, request.method, exception,
        exc_info=exception,
    )


def register_request_error_logging(app) -> None:
    """Conecta o listener ao sinal got_request_exception da app. Chamar
    uma única vez em create_app()."""
    got_request_exception.connect(_log_request_exception, app)
