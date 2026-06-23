"""
core/logging_config.py

Logging centralizado. Em dev (LOG_LEVEL=DEBUG), o ModuleManager e o
EventBus logam cada passo (descoberta, ativação, criação de tabela,
publish/subscribe de evento) — rastreabilidade alta de propósito, pra
facilitar debug. Em produção, cai pra INFO (só o que importa pra operação).

Regra: nenhum módulo (Core, Addon, Plugin) cria seu próprio
logging.basicConfig() — todos usam logging.getLogger(__name__) e herdam
esta configuração, montada uma única vez em create_app().
"""
import logging
import sys


def configure_logging(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Bibliotecas de terceiros ficam em WARNING mesmo com DEBUG no projeto,
    # senão o log de dev fica inundado de ruído do Werkzeug/SQLAlchemy engine.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if level == logging.DEBUG else logging.WARNING
    )

    logging.getLogger(__name__).debug(
        "Logging configurado — nível=%s", logging.getLevelName(level)
    )
