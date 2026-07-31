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
import os
from pathlib import Path

from flask import Flask, jsonify

from core.config import get_config
from core.logging_config import configure_logging, apply_logging_level_overrides
from core.db import init_db
from core.event_bus import event_bus, register_example_listener
from core.module_manager import ModuleManager
from core.auth import init_auth
from core.cli import register_cli_commands
from core.seed_config import ensure_default_system_config
from core.request_error_logging import register_request_error_logging


def create_app(env: str | None = None) -> Flask:
    # app.root_path resolve para core/ (onde Flask(__name__) é
    # instanciado), não para a raiz do projeto — mesmo problema já
    # visto com instance_path (Fase 1). template_folder explícito
    # evita o Jinja procurar em core/templates/ por engano.
    project_root_guess = Path(__file__).parent.parent.resolve()
    app = Flask(__name__, template_folder=str(project_root_guess / "templates"), static_folder=str(project_root_guess / "static") )

    config_cls = get_config(env)
    app.config.from_object(config_cls)

    # Handler de arquivo global (logs/core.log) desligado em TESTING —
    # mesmo padrão já usado pro cliente MQTT e pro scheduler de tasks
    # (nunca em modo de teste): evita escrever centenas de linhas em
    # disco a cada execução da suíte e evita lock de arquivo no
    # Windows entre apps de teste sucessivos (skill 08).
    configure_logging(
        app.config["LOG_LEVEL"],
        enable_file_handler=not app.config.get("TESTING", False),
    )

    init_db(app)
    init_auth(app)
    register_cli_commands(app)

    # Motor de i18n (skill 00, adendo) — primeiro global Jinja do
    # projeto. Cache em memória é limpo a cada TESTING=True (cada app
    # de teste monta seu próprio conjunto de módulos ativos, e reusar
    # cache entre eles mostraria chave de um módulo que não está ativo
    # no teste seguinte).
    from services.core.i18n_service import translate as _t, reset_cache as _i18n_reset_cache
    if app.config.get("TESTING", False):
        _i18n_reset_cache()
    app.jinja_env.globals["t"] = _t

    # tojson_utf8 (skill 15): o filtro nativo `tojson` do Jinja escapa
    # acentuação como \u00e1 — o JS decodifica isso normalmente, mas
    # deixa de existir texto humano legível em resp.data, quebrando
    # qualquer teste que verifique a mensagem de flash (ex.: "Já
    # existe") direto nos bytes crus da resposta. Escapa só "</" (evita
    # fechar a tag <script> prematuramente).
    import json as _json
    from markupsafe import Markup as _Markup

    def _tojson_utf8(value):
        return _Markup(_json.dumps(value, ensure_ascii=False).replace("</", "<\\/"))

    app.jinja_env.filters["tojson_utf8"] = _tojson_utf8

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
        from model.core import designer_data_action  # noqa: F401
        from model.core import scheduled_task, task_log, message_queue  # noqa: F401
        from model.core import model_definition, model_field_definition  # noqa: F401
        from model.core import user_menu_preference  # noqa: F401
        from model.core import playground_request  # noqa: F401
        from model.core import playground_folder  # noqa: F401
        from model.core import playground_cookie_jar  # noqa: F401

        app.module_manager.discover_and_register_addons(project_root / "addons")
        app.module_manager.apply_template_loader()

        app.module_manager.create_all_pending_tables()
        app.module_manager.sync_all_permissions()
        app.module_manager.sync_all_transactions()

        from core.permissions_sync import sync_core_fixed_permissions
        sync_core_fixed_permissions()

        from core.transactions_sync import sync_core_transactions
        sync_core_transactions()

        ensure_default_system_config()
        apply_logging_level_overrides()

        from core.odata_local_seed import ensure_local_odata_connection
        ensure_local_odata_connection()

        # Lookups padrão de addon_estoque (Origem "A definir" / TipoProduto
        # "Insumo") - usados pela resolução automática do autocreate de
        # feature_brew_father. Import local porque é específico do Addon
        # (skill 00 - core não conhece regra de domínio), mesmo padrão do
        # cliente MQTT de addon_device_manager mais abaixo.
        if "estoque" in app.module_manager.active_modules:
            from addons.addon_estoque.root.services.estoque_seed import ensure_default_estoque_lookups
            ensure_default_estoque_lookups()

    from api.routes.core.auth import auth_api_bp
    from api.routes.core.admin.users import users_api_bp
    from api.routes.core.admin.tasks import tasks_api_bp
    from api.routes.core.transactions import transactions_api_bp
    from api.routes.core.theme import theme_api_bp
    from api.routes.core.menu_preferences import menu_preferences_api_bp
    from api.routes.core.options_routes import options_bp
    from controller.core.pages import core_pages_bp
    from controller.core.admin_users import admin_users_bp
    from controller.core.admin_roles import admin_roles_bp
    from controller.core.admin_versioning import admin_versioning_bp
    from controller.core.admin_field_rules import admin_field_rules_bp
    from controller.core.admin_odata import admin_odata_bp
    from controller.core.admin_tasks import admin_tasks_bp
    from controller.core.designer import designer_bp, designer_view_bp
    from controller.core.admin_transactions import admin_transactions_bp
    from controller.core.admin_logs import admin_logs_bp
    from controller.core.profile import profile_bp
    from controller.core.model_builder import model_builder_bp
    from controller.core.admin_menu_settings import admin_menu_settings_bp
    from controller.core.playground import playground_bp
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(users_api_bp)
    app.register_blueprint(tasks_api_bp)
    app.register_blueprint(transactions_api_bp)
    app.register_blueprint(theme_api_bp)
    app.register_blueprint(menu_preferences_api_bp)
    app.register_blueprint(options_bp)
    app.register_blueprint(core_pages_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_roles_bp)
    app.register_blueprint(admin_versioning_bp)
    app.register_blueprint(admin_field_rules_bp)
    app.register_blueprint(admin_odata_bp)
    app.register_blueprint(admin_tasks_bp)
    app.register_blueprint(designer_bp)
    app.register_blueprint(designer_view_bp)
    app.register_blueprint(admin_transactions_bp)
    app.register_blueprint(admin_logs_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(model_builder_bp)
    app.register_blueprint(admin_menu_settings_bp)
    app.register_blueprint(playground_bp)

    # Scheduler de tasks — opt-in via env (TASK_SCHEDULER_ENABLED=true),
    # nunca em modo de teste (mesmo padrão do cliente MQTT do
    # addon_device_manager — ver core/app_factory.py mais abaixo).
    if not app.config.get("TESTING") and os.environ.get("TASK_SCHEDULER_ENABLED", "false").lower() == "true":
        from services.core.task_service import TaskService
        TaskService.init_scheduler(app)

    @app.context_processor
    def inject_i18n_translations():
        """
        Disponível em TODO template (autenticado ou não — diferente de
        inject_transactions_menu, que só roda logado) porque o diálogo
        de confirmação (skill 15) também pode aparecer em telas sem
        sidebar. `tojson` no template escapa para uso seguro dentro de
        <script>.
        """
        from services.core.i18n_service import all_translations
        return {"i18n_translations": all_translations()}

    @app.context_processor
    def inject_transactions_menu():
        """
        Disponível em TODO template que estenda core/base.html — sem
        isso, cada controller gerado pelo CrudGen precisaria passar
        transactions_tree manualmente em todo render_template(). Só
        roda para usuário autenticado (sidebar não existe na tela de
        login, que estende base_no_login.html).

        menu_collapsed_nodes/menu_sidebar_collapsed (skill 07 + árvore
        skill 10): resolvidos uma vez aqui e usados em core/base.html —
        evita chamar resolve_menu_state() duas vezes.
        """
        from flask_login import current_user
        if not current_user.is_authenticated:
            return {}
        from controller.core.pages import _visible_transactions_tree_and_state
        from model.core.system_config import SystemConfig

        tree, state = _visible_transactions_tree_and_state(current_user.id)
        return {
            "transactions_tree": tree,
            "menu_collapsed_nodes": state["collapsed_nodes"],
            "menu_sidebar_collapsed": state["sidebar_collapsed"],
            # skill 10 secao 5.2 (revisao 2026-07-07) - default -1 = sem
            # corte (todo nivel mostra icone), sentinela explicito por
            # skill 03 (nunca None silencioso).
            "menu_icon_max_depth": SystemConfig.get("core.menu.icon_max_depth", default=-1),
        }

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=7,
            active_modules=list(app.module_manager.active_modules.keys()),
            message="Core no ar. ModuleManager, EventBus, DB, RBAC, Versionamento, Addons e Transações ativos.",
        )

    # Cliente MQTT do addon_device_manager — opt-in explícito via env
    # (MQTT_ENABLED=true), nunca em modo de teste (TESTING=True nunca
    # tem broker disponível, e o cliente roda em thread própria que
    # sobreviveria entre testes se iniciado por engano).
    if not app.config.get("TESTING") and os.environ.get("MQTT_ENABLED", "false").lower() == "true":
        from addons.addon_device_manager.root.services import mqtt_client_service
        mqtt_client_service.start(app)

    # Log estruturado de exceções não tratadas em requisições — tagged por
    # blueprint/endpoint, complementa o traceback do console/debugger.
    register_request_error_logging(app)

    return app
