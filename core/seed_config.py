"""
core/seed_config.py

Seed idempotente das chaves padrão de system_config (skill 03, seção
5). Chamado no boot (app_factory.py) — nunca sobrescreve um valor já
presente, só cria o que falta.
"""
import logging

from core.db import db
from model.core.system_config import SystemConfig

logger = logging.getLogger(__name__)

# (chave, valor_default, tipo)
_DEFAULT_KEYS = [
    ("versioning.enabled", "true", "bool"),
    ("versioning.trigger", "on_diff", "string"),
    ("versioning.retention_days", "0", "int"),
    ("versioning.retention_max_per_file", "0", "int"),
    ("rbac.session_eager_load", "true", "bool"),
]


def ensure_default_system_config() -> None:
    created = []
    for key, value, value_type in _DEFAULT_KEYS:
        existing = SystemConfig.query.filter_by(key=key).first()
        if existing is None:
            db.session.add(SystemConfig(key=key, value=value, value_type=value_type))
            created.append(key)

    if created:
        db.session.commit()
        logger.info("system_config — chaves padrão criadas: %s", ", ".join(created))
    else:
        logger.debug("system_config — todas as chaves padrão já existem.")
