"""Heating configuration in the existing Plant workspace; no actuation routes."""
from flask import Blueprint, jsonify, request, redirect, url_for, flash, current_app
from flask_login import login_required
from core.db import db
from core.permissions import permission_required
from ..services import heating_configuration_service as service

heating_workspace_bp = Blueprint("heating_workspace", __name__, url_prefix="/brewstation/plant-workspace")


@heating_workspace_bp.route("/<int:plant_id>/vessels/<int:vessel_id>/heating/<action>", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.update")
def save(plant_id, vessel_id, action):
    payload = request.get_json(silent=True) if request.is_json else request.form
    if not hasattr(payload, "get"):
        return jsonify(ok=False, error="Dados inválidos."), 400
    try:
        vessel = service.scoped_vessel(plant_id, vessel_id)
        if action == "profile":
            service.save_profile(vessel, payload)
        elif action == "source":
            service.save_source(vessel, payload, payload.get("source_id") or None)
        elif action == "remove-source":
            service.remove_source(vessel, payload.get("source_id"), payload)
        else:
            raise service.HeatingError("Operação inválida.")
    except service.HeatingError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), exc.code
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao salvar aquecimento do tanque %s", vessel_id)
        return jsonify(ok=False, error="Não foi possível salvar. Alterações desfeitas."), 500
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(ok=True, message="Configuração salva. Nenhum comando enviado ao equipamento.")
    flash("Configuração de aquecimento salva.", "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="plant") + "#heating-" + str(vessel_id))
