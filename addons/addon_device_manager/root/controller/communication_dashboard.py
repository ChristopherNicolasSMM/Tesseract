"""Painel autenticado para diagnóstico REST, MQTT e Mash Control."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_device_manager.root.services import communication_test_service as diagnostics

communication_dashboard_bp = Blueprint("device_communication", __name__)


@communication_dashboard_bp.get("/device-manager/communication")
@login_required
@permission_required("device_actors.list")
def dashboard():
    return render_template("communication/dashboard.html")


@communication_dashboard_bp.get("/api/device-manager/communication/status")
@login_required
@permission_required("device_actors.list")
def status():
    return jsonify({"broker": diagnostics.broker_settings(),
                    "actors": diagnostics.list_actor_diagnostics()})


@communication_dashboard_bp.post("/api/device-manager/communication/mqtt/probe")
@login_required
@permission_required("device_actors.update")
def mqtt_probe():
    return jsonify(diagnostics.probe_mqtt_broker())


@communication_dashboard_bp.post("/api/device-manager/communication/mqtt/command")
@login_required
@permission_required("device_actors.update")
def mqtt_command():
    payload = request.get_json(silent=True) or {}
    try:
        result = diagnostics.publish_actor_test_command(
            payload.get("actor_id"), payload.get("value"),
            confirmed=payload.get("confirmed") is True,
        )
        return jsonify(result)
    except diagnostics.CommunicationTestError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400


@communication_dashboard_bp.post("/api/device-manager/communication/mqtt/bridge-command")
@login_required
@permission_required("device_actors.update")
def bridge_command():
    payload = request.get_json(silent=True) or {}
    try:
        result = diagnostics.send_bridge_control(
            payload.get("actor_id"), payload.get("action", ""), payload.get("value"),
            confirmed=payload.get("confirmed") is True,
        )
        return jsonify(result)
    except diagnostics.CommunicationTestError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400


@communication_dashboard_bp.post("/api/device-manager/communication/rest/request")
@login_required
@permission_required("device_actors.update")
def rest_request():
    payload = request.get_json(silent=True) or {}
    try:
        result = diagnostics.run_rest_request(
            url=payload.get("url", ""), method=payload.get("method", "GET"),
            headers_json=payload.get("headers", "{}"), body=payload.get("body", ""),
        )
        return jsonify(result)
    except diagnostics.CommunicationTestError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
