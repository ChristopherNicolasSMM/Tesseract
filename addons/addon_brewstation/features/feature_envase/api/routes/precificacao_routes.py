"""
addons/addon_brewstation/features/feature_envase/api/routes/precificacao_routes.py

API JSON do motor de precificação (precificacao_service.py). Não é
CrudGen — service próprio, sem hooks.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_envase.services import precificacao_service

precificacao_api_bp = Blueprint(
    "precificacao_envase_api", __name__, url_prefix="/api/brewstation/precificacao-envase"
)


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


def _parse_payload(data: dict) -> tuple[dict, str | None]:
    lote_id = data.get("lote_id")
    if not lote_id:
        return {}, "lote_id é obrigatório."
    try:
        return {
            "lote_id": int(lote_id),
            "envase_id": int(data["envase_id"]) if data.get("envase_id") else None,
            "percentual_lucro": float(data.get("percentual_lucro") or 0),
            "percentual_ipi": float(data.get("percentual_ipi") or 0),
            "percentual_icms": float(data.get("percentual_icms") or 0),
        }, None
    except (TypeError, ValueError):
        return {}, "Parâmetros numéricos inválidos."


@precificacao_api_bp.route("/simular", methods=["POST"])
@login_required
@permission_required("envases.list")
def simular():
    payload, erro = _parse_payload(request.get_json(silent=True) or {})
    if erro:
        return _err(erro)
    try:
        resultado = precificacao_service.simular(**payload)
    except ValueError as e:
        return _err(str(e), 404)
    return _ok({"resultado": resultado})


@precificacao_api_bp.route("/calcular", methods=["POST"])
@login_required
@permission_required("envases.create")
def calcular():
    payload, erro = _parse_payload(request.get_json(silent=True) or {})
    if erro:
        return _err(erro)
    try:
        resultado = precificacao_service.calcular_e_salvar(**payload)
    except ValueError as e:
        return _err(str(e), 404)
    return _ok({"resultado": resultado}, 201)


@precificacao_api_bp.route("/<int:calculo_id>/vincular-envase", methods=["POST"])
@login_required
@permission_required("envases.create")
def vincular_envase(calculo_id: int):
    data = request.get_json(silent=True) or {}
    envase_id = data.get("envase_id")
    if not envase_id:
        return _err("envase_id é obrigatório.")
    resultado = precificacao_service.vincular_envase(calculo_id, int(envase_id))
    if not resultado:
        return _err("Cálculo não encontrado.", 404)
    return _ok({"calculo": resultado})
