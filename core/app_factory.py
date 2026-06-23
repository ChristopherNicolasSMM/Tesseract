"""
core/app_factory.py

Fase 1 — Core mínimo funcional.
create_app() agora:
- carrega config por ambiente (core/config.py)
- configura logging (core/logging_config.py)
- inicializa o DB factory (core/db.py)
- inicializa o EventBus com o listener de exemplo (core/event_bus.py)
- inicializa o ModuleManager (core/module_manager.py) — nesta fase,
  sem nenhum Addon/Plugin real para descobrir ainda (entra na Fase 5)

RBAC/login entram na Fase 2.
"""
from flask import Flask, jsonify

from core.config import get_config
from core.logging_config import configure_logging
from core.db import init_db
from core.event_bus import event_bus, register_example_listener
from core.module_manager import ModuleManager


def create_app(env: str | None = None) -> Flask:
    app = Flask(__name__)

    config_cls = get_config(env)
    app.config.from_object(config_cls)

    configure_logging(app.config["LOG_LEVEL"])

    init_db(app)

    register_example_listener()

    app.module_manager = ModuleManager(app)

    with app.app_context():
        from model.core import module_state, system_config  # noqa: F401
        app.module_manager.create_all_pending_tables()

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=1,
            active_modules=list(app.module_manager.active_modules.keys()),
            message="Core no ar. ModuleManager, EventBus e DB ativos.",
        )

    return app
