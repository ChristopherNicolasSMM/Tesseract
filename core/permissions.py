"""
core/permissions.py

permission_required: decorator de rota, único ponto de checagem de
autorização junto com User.has_permission(). 401 se não autenticado,
403 se autenticado mas sem a permissão.
"""
from functools import wraps

from flask import abort
from flask_login import current_user


def permission_required(permission_name: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(permission_name):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
