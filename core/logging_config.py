"""
core/logging_config.py

Logging centralizado (skill 08 — Logging, Observabilidade e
Administração de Logs). Em dev (LOG_LEVEL=DEBUG), o ModuleManager e o
EventBus logam cada passo (descoberta, ativação, criação de tabela,
publish/subscribe de evento) — rastreabilidade alta de propósito, pra
facilitar debug. Em produção, cai pra INFO (só o que importa pra operação).

Regra mantida (revisão da skill 08 contra o código real, 2026-07-01):
nenhum módulo (Core, Addon, Plugin) cria seu próprio
logging.basicConfig() — todos usam logging.getLogger(__name__) e
herdam esta configuração, montada uma única vez em create_app(). A
convenção de nome curto de logger cogitada originalmente na skill 08
§1 foi descartada: getLogger(__name__) já é a regra real usada em ~40
módulos do projeto (Core, addon_brewstation, addon_device_manager) e
o nome de origem já aparece no console via %(name)s — migrar tudo pra
nomenclatura nova não trazia ganho que justificasse o refactor.

Duas camadas de saída, sempre as duas juntas (skill 08 §3/§4):
- Console (stdout) — formato HH:MM:SS | LEVEL | logger | mensagem,
  colorido por nível, mas SÓ quando o destino é um terminal de fato
  (sys.stdout.isatty()) — nunca grava código ANSI em arquivo/pipe.
- Arquivo global do Core — <raiz do projeto>/logs/core.log,
  RotatingFileHandler, sem cor (precisa ser grep-ável), timestamp
  completo (não só hora, já que arquivo persiste entre dias).

Em TESTING, o handler de arquivo é desligado por padrão (mesmo padrão
já usado pro cliente MQTT e pro scheduler de tasks — nunca em modo de
teste) — evita escrever centenas de linhas em disco a cada execução da
suíte e evita problema de lock de arquivo no Windows entre app
instâncias sucessivas criadas por testes diferentes.

Nível por logger é ajustável em runtime via system_config (skill 08
§5, chaves logging.level.*) — mas configure_logging() roda ANTES de
init_db() (ver app_factory.py), então não pode consultar o banco.
apply_logging_level_overrides() cobre essa parte, chamada depois que
o banco/system_config já estão prontos.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",       # ciano
    logging.INFO: "\033[32m",        # verde
    logging.WARNING: "\033[33m",     # amarelo
    logging.ERROR: "\033[31m",       # vermelho
    logging.CRITICAL: "\033[1;31m",  # vermelho negrito
}
_RESET = "\033[0m"

# Defaults de rotação do log global — espelham os defaults documentados
# na skill 08 §5 (logging.global_log_max_bytes/backup_count). Esses
# parâmetros ainda não são lidos de system_config em runtime (o
# handler já precisa existir antes do banco estar pronto) — fica
# registrado como próximo passo, não implementado nesta fase.
_GLOBAL_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
_GLOBAL_LOG_BACKUP_COUNT = 5


class _ConsoleFormatter(logging.Formatter):
    """HH:MM:SS | LEVEL | logger.name | mensagem — cor por nível só se for terminal (skill 08 §3)."""

    def __init__(self, use_color: bool):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if not self._use_color:
            return formatted
        color = _LEVEL_COLORS.get(record.levelno, "")
        return f"{color}{formatted}{_RESET}" if color else formatted


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def configure_logging(log_level: str = "INFO", enable_file_handler: bool = True) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    # Fecha handlers antigos antes de descartar — só remover a
    # referência (handlers.clear()) vaza o file descriptor do
    # RotatingFileHandler entre chamadas sucessivas (cada teste que
    # cria um app novo chamaria configure_logging de novo); em
    # Windows isso pode travar a rotação por lock de arquivo.
    for old_handler in root.handlers[:]:
        root.removeHandler(old_handler)
        old_handler.close()
    root.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_ConsoleFormatter(use_color=sys.stdout.isatty()))
    root.addHandler(console_handler)

    if enable_file_handler:
        logs_dir = _project_root() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            logs_dir / "core.log",
            maxBytes=_GLOBAL_LOG_MAX_BYTES,
            backupCount=_GLOBAL_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    # Bibliotecas de terceiros ficam em WARNING mesmo com DEBUG no projeto,
    # senão o log de dev fica inundado de ruído do Werkzeug/SQLAlchemy engine.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if level == logging.DEBUG else logging.WARNING
    )

    logging.getLogger(__name__).debug(
        "Logging configurado — nível=%s, arquivo global=%s",
        logging.getLevelName(level), enable_file_handler,
    )


def apply_logging_level_overrides() -> None:
    """
    Lê logging.level.default e logging.level.<logger_name> de
    system_config (skill 08 §5) e aplica setLevel() por logger.

    Chamada só depois que o banco está pronto (nunca dentro de
    configure_logging(), que roda antes de init_db()) — idempotente,
    pode ser chamada de novo a qualquer momento em runtime (ex.: depois
    que um admin altera a chave). Nenhuma das duas chaves é seedada
    por padrão (core/seed_config.py) — se logging.level.default não
    existir, o nível continua o que configure_logging() já aplicou a
    partir de LOG_LEVEL/TESSERACT_ENV; criar a chave manualmente é o
    único jeito de sobrescrever, evitando que um valor default
    esquecido derrube silenciosamente o DEBUG verboso de dev.
    """
    from model.core.system_config import SystemConfig

    default_level_name = SystemConfig.get("logging.level.default", None)
    if default_level_name:
        default_level = getattr(logging, str(default_level_name).upper(), None)
        if default_level is not None:
            logging.getLogger().setLevel(default_level)

    overrides = SystemConfig.query.filter(
        SystemConfig.key.like("logging.level.%"),
        SystemConfig.key != "logging.level.default",
    ).all()
    for row in overrides:
        logger_name = row.key[len("logging.level."):]
        level = getattr(logging, str(row.value).upper(), None)
        if level is not None:
            logging.getLogger(logger_name).setLevel(level)
