"""
addons/addon_brewstation/features/feature_brew_father/api/routes/brewfather_syncs_routes_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""
from flask import jsonify, request
from flask_login import login_required

from addons.addon_brewstation.features.feature_brew_father.api.routes.brewfather_syncs_routes import brewfather_syncs_api_bp


@brewfather_syncs_api_bp.route("/buscar-materiais", methods=["GET"])
@login_required
def buscar_materiais():
    """Busca textual de Materiais em addon_estoque — usada pelo autocomplete da
    tela de de-para. Retorna lista de {id, nome, categoria}."""
    from addons.addon_estoque.root.services import material_lookup

    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify([])

    resultados = material_lookup.buscar_material_por_termo(termo, limit=15)
    return jsonify([
        {"id": r["id"], "nome": r["nome"], "categoria": r.get("categoria", "")}
        for r in resultados
    ])
