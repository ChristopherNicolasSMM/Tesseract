"""
core/config.py

Configuração por ambiente. Lida via variável de ambiente TESSERACT_ENV
(default: "development").

Regra de ouro (skill 03): segredo e coisa que exige restart vão em .env
(DATABASE_URL, SECRET_KEY). Parâmetro alterável em runtime vai em
system_config (Fase 1, model/core/system_config.py), nunca aqui.
"""
import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Nível de log alto (DEBUG) é o padrão em dev — ver core/logging_config.py
    LOG_LEVEL = "INFO"


class DevelopmentConfig(BaseConfig):
    """
    SQLite local — zero setup, igual aos 3 projetos de origem.

    Caminho relativo de propósito: Flask-SQLAlchemy 3.0+ já resolve
    caminho relativo de SQLite contra app.instance_path automaticamente
    (cria a pasta se não existir) — não prefixar com "instance/" aqui,
    senão duplica o caminho (instance/instance/...).
    """
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///tesseract_dev.db"
    )


class ProductionConfig(BaseConfig):
    """
    Postgres em produção. DATABASE_URL é obrigatória aqui — sem fallback
    silencioso para SQLite, pra nunca subir produção sem banco configurado
    de propósito. A checagem roda em get_config(), não na definição da
    classe, pra não quebrar import em ambiente que nunca vai usar produção.
    """
    DEBUG = False
    LOG_LEVEL = "INFO"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


class TestingConfig(BaseConfig):
    """Usado pela suíte de testes — SQLite em memória, isolado por execução."""
    TESTING = True
    LOG_LEVEL = "DEBUG"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


_CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(env: str | None = None):
    env = env or os.environ.get("TESSERACT_ENV", "development")
    try:
        config_cls = _CONFIG_MAP[env]
    except KeyError:
        raise ValueError(
            f"TESSERACT_ENV={env!r} inválido. Use: {list(_CONFIG_MAP)}"
        )

    if env == "production" and not config_cls.SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "TESSERACT_ENV=production exige DATABASE_URL definida no "
            "ambiente (Postgres). Nenhum fallback silencioso é permitido."
        )

    return config_cls
