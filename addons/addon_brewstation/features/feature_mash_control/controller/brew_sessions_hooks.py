"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_sessions_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""
from flask import redirect, url_for, flash

from flask_login import login_required
from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.controller.brew_sessions import brew_sessions_bp
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_consumption_service


@brew_sessions_bp.route("/<int:id>/confirmar-ingredientes", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
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

    if resultado["ja_confirmado"]:
        flash("Ingredientes já tinham sido confirmados pra este lote.", "warning")
    else:
        falhas = [r for r in resultado["resultados"] if not r["sucesso"]]
        if falhas:
            flash(
                f"Ingredientes confirmados com {len(falhas)} falha(s) — custo total: "
                f"R$ {resultado['custo_total_insumos']:.2f}. Veja o detalhe no log.",
                "warning",
            )
        else:
            flash(f"Ingredientes confirmados — custo total: R$ {resultado['custo_total_insumos']:.2f}.", "success")

    return redirect(url_for("brew_sessions.detail", id=id))
