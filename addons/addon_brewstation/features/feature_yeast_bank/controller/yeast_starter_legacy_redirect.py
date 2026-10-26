"""Redireciona favoritos antigos para a tela integrada de eventos."""
from flask import Blueprint, redirect, url_for
from flask_login import login_required

from core.permissions import permission_required

yeast_starter_legacy_bp = Blueprint("yeast_starter_legacy", __name__)


@yeast_starter_legacy_bp.get("/brewstation/yeast-starter-logs")
@yeast_starter_legacy_bp.get("/brewstation/yeast-starter-logs/")
@login_required
@permission_required("yeast_bank_events.list")
def legacy_starter_logs():
    return redirect(url_for("yeast_bank_events.manage", filter_event_type="Starter"), code=302)
