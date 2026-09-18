"""
addons/addon_brewstation/features/feature_envase/controller/precificacao.py

Tela de simulação/cálculo de precificação (is_workspace=True) — form
(Lote + percentuais) + resultado detalhado por Material (origem do
preço visível) + ação de vincular a um Envase. Não é CrudGen.
"""
from flask import Blueprint, render_template
from flask_login import login_required

from core.permissions import permission_required

precificacao_bp = Blueprint(
    "precificacao_envase", __name__, url_prefix="/brewstation/precificacao-envase"
)


@precificacao_bp.route("/", methods=["GET"])
@login_required
@permission_required("envases.list")
def workspace():
    return render_template("precificacao_envase/shell.html")
