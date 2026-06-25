"""
core/app_factory.py

Fase 7a — Catálogo de Transações (backend, sem UI ainda).
create_app() agora também:
- importa o model Transaction (tesseract_transaction)
- seeda o catálogo de Core (core/transactions_catalog.py)
- sincroniza as transações contribuídas por Addons/Features
  (ModuleManager.sync_all_transactions(), depois de create_all e do
  sync de permissões — mesma ordem, mesma razão: precisa de tabela
  já criada)
- registra /api/core/transactions (lista filtrada por permissão)
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
    # app.root_path resolve para core/ (onde Flask(__name__) é
    # instanciado), não para a raiz do projeto — mesmo problema já
    # visto com instance_path (Fase 1). template_folder explícito
    # evita o Jinja procurar em core/templates/ por engano.
    project_root_guess = Path(__file__).parent.parent.resolve()
    app = Flask(__name__, template_folder=str(project_root_guess / "templates"), static_folder=str(project_root_guess / "static") )

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
        from model.core import transaction  # noqa: F401
        from model.core import user_list_preference  # noqa: F401
        from model.core import field_rule  # noqa: F401
        from model.core import odata_connection  # noqa: F401
        from model.core import designer_page, designer_component  # noqa: F401

        app.module_manager.discover_and_register_addons(project_root / "addons")
        app.module_manager.apply_template_loader()

        app.module_manager.create_all_pending_tables()
        app.module_manager.sync_all_permissions()
        app.module_manager.sync_all_transactions()

        from core.transactions_sync import sync_core_transactions
        sync_core_transactions()

        ensure_default_system_config()

    from api.routes.core.auth import auth_api_bp
    from api.routes.core.admin.users import users_api_bp
    from api.routes.core.transactions import transactions_api_bp
    from api.routes.core.theme import theme_api_bp
    from controller.core.pages import core_pages_bp
    from controller.core.admin_users import admin_users_bp
    from controller.core.admin_roles import admin_roles_bp
    from controller.core.admin_versioning import admin_versioning_bp
    from controller.core.admin_field_rules import admin_field_rules_bp
    from controller.core.admin_odata import admin_odata_bp
    from controller.core.designer import designer_bp, designer_view_bp
    from controller.core.profile import profile_bp
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(users_api_bp)
    app.register_blueprint(transactions_api_bp)
    app.register_blueprint(theme_api_bp)
    app.register_blueprint(core_pages_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_roles_bp)
    app.register_blueprint(admin_versioning_bp)
    app.register_blueprint(admin_field_rules_bp)
    app.register_blueprint(admin_odata_bp)
    app.register_blueprint(designer_bp)
    app.register_blueprint(designer_view_bp)
    app.register_blueprint(profile_bp)

    @app.context_processor
    def inject_transactions_menu():
        """
        Disponível em TODO template que estenda core/base.html — sem
        isso, cada controller gerado pelo CrudGen precisaria passar
        transactions_by_group manualmente em todo render_template().
        Só roda para usuário autenticado (sidebar não existe na tela
        de login, que estende base_no_login.html).
        """
        from flask_login import current_user
        if not current_user.is_authenticated:
            return {}
        from controller.core.pages import _visible_transactions_by_group
        return {"transactions_by_group": _visible_transactions_by_group()}

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=7,
            active_modules=list(app.module_manager.active_modules.keys()),
            message="Core no ar. ModuleManager, EventBus, DB, RBAC, Versionamento, Addons e Transações ativos.",
        )

    return app
