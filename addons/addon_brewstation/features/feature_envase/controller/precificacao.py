"""
addons/addon_brewstation/features/feature_envase/controller/precificacao.py

Tela de simulação/cálculo de precificação (is_workspace=True) — form
(Lote + percentuais) + resultado detalhado por Material (origem do
preço visível) + ação de vincular a um Envase. Não é CrudGen.
"""
from flask import Blueprint, render_template, request, abort
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession

from addons.addon_brewstation.features.feature_envase.model.envase import Envase

precificacao_bp = Blueprint(
    "precificacao_envase", __name__, url_prefix="/brewstation/precificacao-envase"
)


@precificacao_bp.route("/", methods=["GET"])
@login_required
@permission_required("envases.list")
def workspace():
    lote = None
    if "lote_id" in request.args:
        lote = BrewSession.query.filter_by(id=request.args.get("lote_id", type=int), is_deleted=False).first()
        if not lote:
            abort(404)
    envase = None
    if "envase_id" in request.args:
        if lote is None:
            abort(404)
        envase = Envase.query.filter_by(id=request.args.get("envase_id", type=int),
                                      lote_id=lote.id, is_deleted=False, status="registrado").first()
        if envase is None:
            abort(404)
    return render_template("precificacao_envase/shell.html", lote=lote, envase=envase)
