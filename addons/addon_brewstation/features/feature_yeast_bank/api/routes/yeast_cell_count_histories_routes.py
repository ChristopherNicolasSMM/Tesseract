"""
addons/addon_brewstation/features/feature_yeast_bank/api/routes/yeast_cell_count_histories_routes.py

API JSON — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_cell_count_histories_routes_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_cell_count_history_service import YeastCellCountHistoryService

yeast_cell_count_histories_api_bp = Blueprint(
    "yeast_cell_count_histories_api", __name__, url_prefix="/api/brewstation/yeast-cell-count-histories"
)
_service = YeastCellCountHistoryService()


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


@yeast_cell_count_histories_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_cell_count_histories.list")
def list_items():
    items = _service.list()
    return _ok({"items": [i.to_dict() if hasattr(i, "to_dict") else {"id": i.id} for i in items]})


@yeast_cell_count_histories_api_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_cell_count_histories.detail")
def get_item(id: int):
    item = _service.get_by_id(id)
    if not item:
        return _err("Não encontrado.", 404)
    return _ok({"item": item.to_dict() if hasattr(item, "to_dict") else {"id": item.id}})


@yeast_cell_count_histories_api_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.create")
def create_item():
    data = request.get_json(silent=True) or {}
    result = _service.create(data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok({"item": result.data.to_dict() if hasattr(result.data, "to_dict") else {"id": result.data.id}}, result.code)


@yeast_cell_count_histories_api_bp.route("/<int:id>", methods=["PUT"])
@login_required
@permission_required("yeast_cell_count_histories.update")
def update_item(id: int):
    data = request.get_json(silent=True) or {}
    result = _service.update(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok({"item": result.data.to_dict() if hasattr(result.data, "to_dict") else {"id": result.data.id}})


@yeast_cell_count_histories_api_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.trash")
def trash_item(id: int):
    result = _service.trash(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()


@yeast_cell_count_histories_api_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.restore")
def restore_item(id: int):
    result = _service.restore(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()


@yeast_cell_count_histories_api_bp.route("/<int:id>", methods=["DELETE"])
@login_required
@permission_required("yeast_cell_count_histories.delete_permanent")
def delete_permanent_item(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok()
