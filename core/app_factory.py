"""
core/app_factory.py

Fase 2 — RBAC + Usuários.
create_app() agora também:
- inicializa Flask-Login (core/auth.py)
- registra os Blueprints de autenticação e admin de usuários
- registra o comando CLI `init-admin`

CrudGen/versionamento entram nas Fases 3/4.
"""
from flask import Flask, jsonify

from core.config import get_config
from core.logging_config import configure_logging
from core.db import init_db
from core.event_bus import event_bus, register_example_listener
from core.module_manager import ModuleManager
from core.auth import init_auth
from core.cli import register_cli_commands


def create_app(env: str | None = None) -> Flask:
    app = Flask(__name__)

    config_cls = get_config(env)
    app.config.from_object(config_cls)

    configure_logging(app.config["LOG_LEVEL"])

    init_db(app)
    init_auth(app)
    register_cli_commands(app)

    register_example_listener()

    app.module_manager = ModuleManager(app)

    with app.app_context():
        from model.core import module_state, system_config  # noqa: F401
        from model.core import permission, role, associations, user  # noqa: F401
        app.module_manager.create_all_pending_tables()

    from api.routes.core.auth import auth_api_bp
    from api.routes.core.admin.users import users_api_bp
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(users_api_bp)

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=2,
            active_modules=list(app.module_manager.active_modules.keys()),
            message="Core no ar. ModuleManager, EventBus, DB e RBAC ativos.",
        )

    return app
