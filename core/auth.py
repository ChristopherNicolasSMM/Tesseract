"""
core/auth.py

Setup do Flask-Login. user_loader usa joinedload em roles+permissions
(system_config rbac.session_eager_load, skill 03) — evita N+1 a cada
chamada de has_permission() dentro de um único request.
"""
import logging

from flask_login import LoginManager
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

login_manager = LoginManager()


def init_auth(app) -> None:
    login_manager.init_app(app)
    login_manager.login_view = "core_pages.login_page"  # páginas HTML existem desde esta fase

    @login_manager.user_loader
    def load_user(user_id: str):
        from model.core.user import User
        from model.core.role import Role  # noqa: F401 (garante mapper resolvido)

        eager_load = app.config.get("RBAC_SESSION_EAGER_LOAD", True)
        query = User.query
        if eager_load:
            query = query.options(
                joinedload(User.roles).joinedload(Role.permissions)
            )
        return query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import jsonify, request, redirect, url_for

        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Não autenticado."), 401
        return redirect(url_for("core_pages.login_page"))

    logger.debug("Flask-Login configurado (eager_load=%s)", app.config.get(
        "RBAC_SESSION_EAGER_LOAD", True
    ))
