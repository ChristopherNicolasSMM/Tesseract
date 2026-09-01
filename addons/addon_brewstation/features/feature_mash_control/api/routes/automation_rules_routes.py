"""
addons/addon_brewstation/features/feature_mash_control/api/routes/automation_rules_routes.py

API JSON — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via automation_rules_routes_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.automation_rule_service import AutomationRuleService

try:
    from addons.addon_brewstation.features.feature_mash_control.controller import automation_rules_hooks as _hooks
except ImportError:
    _hooks = None


def _noop(*args, **kwargs):
    return None


def _hook(name):
    return getattr(_hooks, name, _noop) if _hooks else _noop


automation_rules_api_bp = Blueprint(
    "automation_rules_api", __name__, url_prefix="/api/brewstation/automation-rules"
)
_service = AutomationRuleService()


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


@automation_rules_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("automation_rules.list")
def list_items():
    items = _service.list()
    return _ok({"items": [i.to_dict() if hasattr(i, "to_dict") else {"id": i.id} for i in items]})


@automation_rules_api_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("automation_rules.detail")
def get_item(id: int):
    item = _service.get_by_id(id)
    if not item:
        return _err("Não encontrado.", 404)
    return _ok({"item": item.to_dict() if hasattr(item, "to_dict") else {"id": item.id}})


@automation_rules_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("automation_rules.create")
def create_item():
    data = request.get_json(silent=True) or {}
    # Hook opcional (skill 21) — mesmo bloqueio de criação direta que
    # o controller web aplica (ver controller.py.j2), pra não deixar
    # a API virar um bypass da regra.
    _block_message = _hook("block_create")(data)
    if _block_message is not None:
        return _err(_block_message, 403)
    result = _service.create(data)
    if not result.success:
        return _err(result.error, result.code)
    # Mesmo hook post_create_redirect do controller web (skill 21) —
    # aqui só pelo efeito colateral (ex.: criar um registro
    # vinculado), o valor de retorno (um redirect() do Flask) não faz
    # sentido pra resposta JSON e é descartado de propósito.
    _hook("post_create_redirect")(result.data)
    return _ok({"item": result.data.to_dict() if hasattr(result.data, "to_dict") else {"id": result.data.id}}, result.code)


@automation_rules_api_bp.route("/<int:id>", methods=["PUT"])
@login_required
@permission_required("automation_rules.update")
def update_item(id: int):
    data = request.get_json(silent=True) or {}
    result = _service.update(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok({"item": result.data.to_dict() if hasattr(result.data, "to_dict") else {"id": result.data.id}})


@automation_rules_api_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("automation_rules.trash")
def trash_item(id: int):
    result = _service.trash(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()


@automation_rules_api_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("automation_rules.restore")
def restore_item(id: int):
    result = _service.restore(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()


@automation_rules_api_bp.route("/<int:id>", methods=["DELETE"])
@login_required
@permission_required("automation_rules.delete_permanent")
def delete_permanent_item(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()
