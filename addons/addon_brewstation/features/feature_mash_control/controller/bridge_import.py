"""
addons/addon_brewstation/features/feature_mash_control/controller/bridge_import.py

Tela do "cadastro primário" (conversa — arquitetura de dashboard
consolidada): sobe devices.yml (+ recipe.yml opcional) no formato do
tesseract-device-bridge e monta o cadastro inicial de Devices/Functions/
Actors + Planta/Vasilhames/Mapeamentos + Dashboard, sem precisar
cadastrar tudo na mão pelas telas de CRUD.

NÃO gerado pelo CrudGen — mesmo padrão de dashboard_runtime.py.
"""
from __future__ import annotations

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services import bridge_import_service as svc

bridge_import_bp = Blueprint(
    "bridge_import", __name__, url_prefix="/brewstation/bridge-import"
)


def _read_upload_or_textarea(file_field: str, text_field: str) -> str:
    uploaded = request.files.get(file_field)
    if uploaded and uploaded.filename:
        return uploaded.read().decode("utf-8")
    return (request.form.get(text_field) or "").strip()


@bridge_import_bp.route("/", methods=["GET"])
@login_required
@permission_required("device_actors.create")
def form():
    return render_template("bridge_import/form.html", result=None)


@bridge_import_bp.route("/", methods=["POST"])
@login_required
@permission_required("device_actors.create")
def run_import():
    devices_text = _read_upload_or_textarea("devices_file", "devices_text")
    recipe_text = _read_upload_or_textarea("recipe_file", "recipe_text")

    if not devices_text:
        flash("Cole ou envie o devices.yml — é obrigatório.", "error")
        return redirect(url_for("bridge_import.form"))

    bridge_device_name = (request.form.get("bridge_device_name") or "").strip() or "Bridge Principal"
    plant_name = (request.form.get("plant_name") or "").strip() or None
    layout_name = (request.form.get("layout_name") or "").strip() or "Painel de Mostura"

    try:
        result = svc.import_bridge_config(
            devices_text, recipe_text or None,
            bridge_device_name=bridge_device_name, plant_name=plant_name, layout_name=layout_name,
        )
    except svc.BridgeImportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("bridge_import.form"))

    flash("Importação concluída — confira o resumo abaixo.", "success")
    return render_template("bridge_import/form.html", result=result)
