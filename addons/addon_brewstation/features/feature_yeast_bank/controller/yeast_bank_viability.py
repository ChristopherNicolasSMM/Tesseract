"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_viability.py

Tela/ação de "Recalcular viabilidade" — ação de negócio em lote sobre
todos os YeastBankItem, não um CRUD genérico do CrudGen. Por isso é
escrita à mão, fora do padrão `service.py`/`controller.py` gerado.
"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.viability_engine import recalculate_all

yeast_bank_viability_bp = Blueprint(
    "yeast_bank_viability", __name__, url_prefix="/brewstation/yeast-bank-tools"
)


@yeast_bank_viability_bp.route("/recalculate-viability", methods=["GET"])
@login_required
@permission_required("yeast_bank_items.recalculate_viability")
def recalculate_viability_page():
    return render_template("yeast_bank_tools/recalculate_viability.html")


@yeast_bank_viability_bp.route("/recalculate-viability", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.recalculate_viability")
def recalculate_viability_run():
    result = recalculate_all()
    return jsonify(success=True, **result)
