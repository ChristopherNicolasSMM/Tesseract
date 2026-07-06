"""
addons/addon_brewstation/features/feature_brew_father/controller/brewfather_syncs_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""
from flask import redirect, url_for, flash, render_template, request
from flask_login import login_required, current_user

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_brew_father.controller.brewfather_syncs import brewfather_syncs_bp
from addons.addon_brewstation.features.feature_brew_father.services import sync_service
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client


@brewfather_syncs_bp.route("/sincronizar", methods=["POST"])
@login_required
@permission_required("brewfather_syncs.create")
def sincronizar():
    """Dispara sync_service.sync_recipes() e redireciona de volta à lista."""
    try:
        resultado = sync_service.sync_recipes()
        status = resultado.get("status", "?")
        processadas = resultado.get("quantidade_processada", 0)
        erros = resultado.get("quantidade_erro", 0)

        if status == "sucesso":
            flash(
                f"Sincronização concluída: {processadas} receita(s) importada(s).",
                "success",
            )
        elif status == "parcial":
            flash(
                f"Sincronização parcial: {processadas} receita(s) importada(s), {erros} com erro.",
                "warning",
            )
        else:
            msg_erro = resultado.get("mensagem_erro") or "Verifique o log de sincronização."
            flash(f"Erro na sincronização: {msg_erro}", "error")

    except Exception as exc:  # noqa: BLE001
        flash(f"Erro inesperado ao sincronizar: {exc}", "error")

    return redirect(url_for("brewfather_syncs.manage"))


@brewfather_syncs_bp.route("/pendentes", methods=["GET"])
@login_required
@permission_required("brewfather_syncs.list")
def pendentes():
    """Tela de de-para: ingredientes pendentes de resolução, agrupados por
    descricao_origem."""
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
    from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe

    itens = (
        RecipeIngredient.query
        .filter_by(status_resolucao="pendente_depara", is_deleted=False)
        .join(MashRecipe, RecipeIngredient.recipe_id == MashRecipe.id)
        .filter(MashRecipe.origem_receita == "BrewFather")
        .order_by(RecipeIngredient.descricao_origem)
        .all()
    )

    # Agrupa por descricao_origem pra evitar mostrar a mesma string N vezes
    grupos = {}
    for item in itens:
        chave = item.descricao_origem
        if chave not in grupos:
            grupos[chave] = {"descricao_origem": chave, "quantidade_receitas": 0, "ids": []}
        grupos[chave]["quantidade_receitas"] += 1
        grupos[chave]["ids"].append(item.id)

    return render_template(
        "brewfather_syncs/depara.html",
        grupos=list(grupos.values()),
        total_pendentes=len(itens),
    )


@brewfather_syncs_bp.route("/pendentes/resolver", methods=["POST"])
@login_required
@permission_required("brewfather_syncs.create")
def resolver_pendente():
    """Recebe o formulário da tela de-para e confirma o mapeamento."""
    from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service

    descricao_origem = request.form.get("descricao_origem", "").strip()
    material_id = request.form.get("material_id", "").strip()
    novo_material_nome = request.form.get("novo_material_nome", "").strip()

    if not descricao_origem:
        flash("Descrição de origem inválida.", "error")
        return redirect(url_for("brewfather_syncs.pendentes"))

    try:
        if novo_material_nome:
            # Cadastra Material novo em addon_estoque antes de mapear
            from addons.addon_estoque.root.model.material import Material
            from core.db import db
            material_existente = Material.query.filter_by(nome=novo_material_nome, is_deleted=False).first()
            if material_existente:
                mid = material_existente.id
            else:
                novo = Material(nome=novo_material_nome, categoria="materia_prima")
                db.session.add(novo)
                db.session.commit()
                mid = novo.id
        elif material_id:
            mid = int(material_id)
        else:
            flash("Informe um material existente ou um nome para cadastrar.", "error")
            return redirect(url_for("brewfather_syncs.pendentes"))

        resultado = ingredient_resolution_service.confirmar_mapeamento(
            "BrewFather", descricao_origem, mid
        )
        flash(
            f"Mapeamento salvo — {resultado['ingredientes_resolvidos']} ingrediente(s) resolvido(s).",
            "success",
        )
    except Exception as exc:  # noqa: BLE001
        flash(f"Erro ao resolver mapeamento: {exc}", "error")

    return redirect(url_for("brewfather_syncs.pendentes"))
