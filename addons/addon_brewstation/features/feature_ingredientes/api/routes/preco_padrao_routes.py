"""
addons/addon_brewstation/features/feature_ingredientes/api/routes/preco_padrao_routes.py

API JSON pro card editável (ícone de lápis -> popup) da tela
ingredientes-workspace. Não é gerado pelo CrudGen (PrecoPadraoInsumo
não tem tela CRUD própria, só os 3 cards) — service único, sem hooks.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.permissions import permission_required
from core.db import db
from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import (
    PrecoPadraoInsumo,
    TIPOS_INSUMO,
)

preco_padrao_api_bp = Blueprint(
    "preco_padrao_insumos_api", __name__, url_prefix="/api/brewstation/preco-padrao-insumos"
)


def _ok(data=None, code=200):
    return jsonify({"success": True, **(data or {})}), code


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


@preco_padrao_api_bp.route("/", methods=["GET"])
@login_required
@permission_required("preco_padrao_insumos.list")
def list_items():
    items = PrecoPadraoInsumo.query.order_by(PrecoPadraoInsumo.tipo_insumo).all()
    return _ok({"items": [i.to_dict() for i in items]})


@preco_padrao_api_bp.route("/<string:tipo_insumo>", methods=["PUT"])
@login_required
@permission_required("preco_padrao_insumos.update")
def update_item(tipo_insumo: str):
    if tipo_insumo not in TIPOS_INSUMO:
        return _err(f"Tipo de insumo inválido. Use um de: {', '.join(TIPOS_INSUMO)}.", 400)

    row = PrecoPadraoInsumo.query.filter_by(tipo_insumo=tipo_insumo).first()
    if not row:
        return _err("Preço padrão não encontrado — verifique se o seed inicial rodou.", 404)

    data = request.get_json(silent=True) or {}
    valor_padrao = data.get("valor_padrao")
    if valor_padrao is None:
        return _err("valor_padrao é obrigatório.", 400)
    try:
        valor_padrao = float(valor_padrao)
    except (TypeError, ValueError):
        return _err("valor_padrao precisa ser numérico.", 400)
    if valor_padrao < 0:
        return _err("valor_padrao não pode ser negativo.", 400)

    row.valor_padrao = valor_padrao
    if data.get("unidade"):
        row.unidade = str(data["unidade"])[:10]

    db.session.commit()
    return _ok({"item": row.to_dict()})
