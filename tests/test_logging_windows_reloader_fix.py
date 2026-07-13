"""
tests/test_logging_windows_reloader_fix.py

Achado real (Windows): com o reloader do Werkzeug ativo (debug=True),
o processo "monitor" (que nunca serve requisição de verdade) também
roda configure_logging() uma vez antes do fork, abrindo seu próprio
handle de logs/core.log — nunca mais escreve nele, mas também nunca
libera. Quando o subprocesso filho de fato rotaciona o arquivo, o
Windows recusa o rename porque o monitor ainda está com o arquivo
aberto (PermissionError/WinError 32). Corrigido com
disable_file_handler(), chamado por run.py (comando `start`) só no
processo monitor.
"""
import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.logging_config import configure_logging, disable_file_handler


def test_disable_file_handler_remove_e_fecha_rotating_file_handler():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "core.log"
        handler = RotatingFileHandler(log_path, maxBytes=1024, backupCount=1)
        root = logging.getLogger()
        root.addHandler(handler)

        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)

        disable_file_handler()

        assert not any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        # Handler fechado de verdade — stream não pode mais ser usado
        # (evita o handle ficar aberto no processo monitor).
        assert handler.stream is None or handler.stream.closed


def test_disable_file_handler_nao_falha_sem_nenhum_handler_de_arquivo():
    root = logging.getLogger()
    for h in root.handlers[:]:
        if isinstance(h, RotatingFileHandler):
            root.removeHandler(h)
            h.close()

    disable_file_handler()  # não deve lançar exceção mesmo sem handler nenhum


def test_configure_logging_seguido_de_disable_deixa_so_o_console_handler():
    configure_logging(log_level="INFO", enable_file_handler=True)
    root = logging.getLogger()
    assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    disable_file_handler()

    assert not any(isinstance(h, RotatingFileHandler) for h in root.handlers)
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root.handlers)

    # Limpeza — não deixar o handler de arquivo real (logs/core.log do
    # projeto) vazando pros próximos testes do resto da suíte.
    configure_logging(log_level="INFO", enable_file_handler=False)
