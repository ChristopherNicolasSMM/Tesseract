"""
addons/addon_device_manager/root/services/integration_logger.py

Log de integração local em 3 camadas (decisão 2.6, fechada no
documento de arquitetura): eventos de rotina de alto volume (valores
recebidos, comandos enviados) vão só pra um arquivo local do próprio
Addon — nunca pro log global do Core, que ficaria poluído. Erro que
importa (broker inacessível, payload inválido, valor fora de faixa,
falha de fail-safe) continua usando o logger padrão
(`logging.getLogger(__name__)` em mqtt_client_service.py/
device_service.py), que já propaga pro log global do Core por padrão
(core/logging_config.py) — esses dois caminhos nunca se misturam.

Exceção controlada à regra de `core/logging_config.py` ("nenhum
módulo cria seu próprio logging.basicConfig()"): este módulo NÃO
chama `basicConfig()` nem toca no root logger — só adiciona um
`RotatingFileHandler` a um logger NOMEADO
(`addon_device_manager.integration`), com `propagate=False`, então
ele nunca duplica nem interfere no handler global. É uma
customização escopada a um único logger, não uma reconfiguração
global — por isso não conflita com a regra do Core.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger: logging.Logger | None = None


def _load_manifest_logging_config() -> dict:
    addon_root = Path(__file__).resolve().parents[2]  # .../addon_device_manager/
    manifest_path = addon_root / "addon.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return manifest.get("logging") or {}


def get_integration_logger() -> logging.Logger:
    """
    Logger singleton para eventos de rotina do addon_device_manager.
    Se `logging.integration_log_enabled` for `false` no `addon.json`
    (ou a seção `logging` estiver ausente), retorna um logger com
    `NullHandler` — chamadas a `.info()`/`.debug()` continuam seguras,
    só não escrevem nada em disco.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("addon_device_manager.integration")
    logger.propagate = False  # nunca sobe pro log global — só o arquivo local
    logger.setLevel(logging.INFO)

    config = _load_manifest_logging_config()
    if not config.get("integration_log_enabled", True):
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return _logger

    addon_root = Path(__file__).resolve().parents[2]
    log_path_relative = config.get("integration_log_path", "logs/integration.log")
    log_path = addon_root / log_path_relative
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=config.get("integration_log_max_bytes", 5 * 1024 * 1024),
        backupCount=config.get("integration_log_backup_count", 5),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)

    _logger = logger
    return _logger


def reset_for_tests() -> None:
    """
    Só para a suíte de testes: descarta o logger singleton (e seus
    handlers de arquivo) entre execuções, evitando handler duplicado
    ou arquivo de log preso a um diretório temporário de teste
    anterior.
    """
    global _logger
    if _logger is not None:
        for handler in list(_logger.handlers):
            _logger.removeHandler(handler)
            handler.close()
    _logger = None
