"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_sessions_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""
from flask import redirect, url_for, flash, request, jsonify
from flask_login import current_user

from flask_login import login_required
from core.permissions import permission_required
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.controller.brew_sessions import brew_sessions_bp
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_consumption_service


def detail_context_extra(item):
    from ..services.production_organization_service import context
    from ..model.production_organization import ProductionConsumption
    from services.core.organization_service import list_organizations
    from datetime import date
    link = context(item.id)
    consumed = db.session.get(ProductionConsumption, item.id)
    return {"production_context": link.snapshot() if link else None,
            "production_cost": consumed.snapshot() if consumed else None,
            "organizations": list_organizations(), "today": date.today().isoformat(),
            "production_values": request.form.to_dict(),
            "conferencia_ingredientes": (
        ingredient_consumption_service.conferir_ingredientes(item.recipe_id, estimate_cost=False)
        if item.recipe_id and item.insumos_baixados_em is None else None
    )}


@brew_sessions_bp.route("/<int:id>/confirmar-ingredientes", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
@permission_required("movimentacaos.create")
def confirmar_ingredientes(id: int):
    """
    Botão "Confirmar Ingredientes" (skill 26, gatilho escolhido: ação
    explícita, não automática na mudança de status) — dá baixa real
    dos insumos da receita vinculada, idempotente
    (`BrewSession.insumos_baixados_em`).
    """
    try:
        resultado = ingredient_consumption_service.confirmar_consumo_ingredientes(id)
    except ingredient_consumption_service.LoteNaoEncontradoError:
        flash("Sessão de brassagem não encontrada.", "error")
        return redirect(url_for("brew_sessions.manage"))
    except ingredient_consumption_service.ReceitaNaoVinculadaError:
        flash("Esta sessão não tem receita vinculada — não há insumo pra confirmar.", "error")
        return redirect(url_for("brew_sessions.detail", id=id))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("brew_sessions.detail", id=id))

    if resultado["ja_confirmado"]:
        flash("Ingredientes já confirmados para este lote.", "warning")
    else:
        flash(f"Ingredientes confirmados — {resultado['custo_total_insumos']} {resultado['currency_code']}.", "success")
    return redirect(url_for("brew_sessions.detail", id=id))


@brew_sessions_bp.route('/<int:id>/organizacao', methods=['POST'])
@login_required
@permission_required('brew_sessions.update')
@permission_required('movimentacaos.create')
def production_organization(id):
    from ..services.production_organization_service import bind
    from addons.addon_estoque.root.controller.organization_stock_hooks import _optional_id
    try:
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        if not isinstance(payload, dict) or set(payload) - {'organization_code', 'operation_date', 'policy_version_id', 'csrf_token'}:
            raise ValueError('Campos inválidos.')
        data = {field: payload.get(field) for field in ('organization_code', 'operation_date', 'policy_version_id')}
        data['policy_version_id'] = _optional_id(data['policy_version_id'])
        result = bind(id, data, actor=current_user.username)
        if request.is_json:
            return jsonify(success=True, data=result)
        flash('Organização do lote vinculada.', 'success')
    except ValueError as exc:
        if request.is_json:
            return jsonify(success=False, error=str(exc)), 422
        flash(str(exc), 'error')
        from .brew_sessions import detail
        return detail(id), 422
    return redirect(url_for('brew_sessions.detail', id=id))
