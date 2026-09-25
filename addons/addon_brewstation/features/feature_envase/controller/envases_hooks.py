"""
addons/addon_brewstation/features/feature_envase/controller/envases_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""

from flask import current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_envase.controller.envases import envases_bp
from addons.addon_brewstation.features.feature_envase.services import envase_estoque_service


@envases_bp.route("/<int:id>/estornar", methods=["POST"])
@login_required
@permission_required("envases.update")
def estornar(id):
    try:
        envase_estoque_service.estornar_envase(
            id, request.form.get("motivo", ""), usuario_id=current_user.id,
        )
    except envase_estoque_service.EnvaseNaoEstornavelError as exc:
        flash(str(exc), "error")
    except Exception:
        current_app.logger.exception("Falha ao estornar envase %s", id)
        flash("Não foi possível estornar o envase. Nenhuma baixa parcial foi mantida.", "error")
    else:
        flash("Envase cancelado e componentes devolvidos ao estoque.", "success")
    return redirect(url_for("envases.detail", id=id))
