"""
core/app_factory.py

Fase 5 — primeiro Addon real (addon_brewstation/feature_yeast_bank).
create_app() agora também:
- descobre e registra Addons automaticamente a partir de addons/
  (core/module_manager.discover_and_register_addons), ANTES de criar
  as tabelas — assim o prefixo de tabela (skill 02) é aplicado em todo
  boot normal, não só durante `generate` (CrudGen, Fase 4)
"""
from pathlib import Path

from flask import Flask, jsonify

from core.config import get_config
from core.logging_config import configure_logging
from core.db import init_db
from core.event_bus import event_bus, register_example_listener
from core.module_manager import ModuleManager
from core.auth import init_auth
from core.cli import register_cli_commands
from core.seed_config import ensure_default_system_config


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

    project_root = Path(app.root_path).parent.resolve()

    with app.app_context():
        from model.core import module_state, system_config  # noqa: F401
        from model.core import permission, role, associations, user  # noqa: F401
        from model.core import code_snapshot  # noqa: F401

        app.module_manager.discover_and_register_addons(project_root / "addons")

        app.module_manager.create_all_pending_tables()
        app.module_manager.sync_all_permissions()
        ensure_default_system_config()

    from api.routes.core.auth import auth_api_bp
    from api.routes.core.admin.users import users_api_bp
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(users_api_bp)

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=5,
            active_modules=list(app.module_manager.active_modules.keys()),
            message="Core no ar. ModuleManager, EventBus, DB, RBAC, Versionamento e Addons ativos.",
        )

    return app
