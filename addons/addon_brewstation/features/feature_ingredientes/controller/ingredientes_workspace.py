"""
addons/addon_brewstation/features/feature_ingredientes/controller/ingredientes_workspace.py

Tela consolidada (is_workspace=True) — abas Malte/Lúpulo/Levedura
reaproveitando as telas CRUD já existentes (embutidas via iframe, sem
duplicar grid/formulário/hooks) + cards de preço padrão por tipo no
topo, editáveis via popup (JS chama a API preco_padrao_routes.py).
Não é gerado pelo CrudGen.
"""
from flask import Blueprint, render_template
from flask_login import login_required

from core.permissions import permission_required

ingredientes_workspace_bp = Blueprint(
    "ingredientes_workspace", __name__, url_prefix="/brewstation/ingredientes-workspace"
)

_TABS = [
    {"key": "malte", "label": "Malte", "icon": "bi-grain", "endpoint": "maltes.manage"},
    {"key": "lupulo", "label": "Lúpulo", "icon": "bi-flower1", "endpoint": "lupulos.manage"},
    {"key": "levedura", "label": "Levedura", "icon": "bi-moisture", "endpoint": "leveduras.manage"},
]


@ingredientes_workspace_bp.route("/", methods=["GET"])
@login_required
@permission_required("maltes.list")
def workspace():
    return render_template("ingredientes_workspace/shell.html", tabs=_TABS)
