"""
addons/addon_brewstation/features/feature_brew_father/controller/brewfather_syncs_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""
from flask import abort, redirect, url_for, flash, render_template, request
from flask_login import login_required, current_user

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_brew_father.controller.brewfather_syncs import brewfather_syncs_bp
from addons.addon_brewstation.features.feature_brew_father.services import sync_service
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client
from addons.addon_brewstation.features.feature_brew_father.services import inventory_reconciliation_service as reconciliation


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


@brewfather_syncs_bp.route("/disponiveis", methods=["GET"])
@brewfather_syncs_bp.route("/portal", methods=["GET"])
@login_required
@permission_required("brewfather_syncs.list")
def portal():
    """
    Skill 27 — tela de seleção prévia: lista enxuta do BrewFather
    (sem gastar chamada de detalhe por receita) com status de cada
    uma (nova/já importada/apagada-pendente), pra escolher o que
    sincronizar em vez de tudo de uma vez.
    """
    try:
        filtros = {key: request.args.get(key, "").strip() for key in ("q", "estilo", "tipo", "status", "pasta", "tag")}
        dados = sync_service.listar_portal_receitas(filtros, atualizar=request.args.get("refresh") == "1")
        erro = None
    except (brewfather_client.BrewFatherDisabledError, brewfather_client.BrewFatherAPIError) as exc:
        dados = {"receitas": [], "total": 0, "limitado": False, "estilos": [], "tipos": [], "pastas": [], "tags": []}
        erro = str(exc)

    return render_template("brewfather_syncs/portal.html", **dados, filtros=filtros, erro=erro)


@brewfather_syncs_bp.route("/portal/lotes", methods=["GET"])
@login_required
@permission_required("brewfather_syncs.list")
def portal_lotes():
    filtros = {"q": request.args.get("q", "").strip(), "status": request.args.get("status", "").strip()}
    if filtros["status"] not in ("", "Planning", "Brewing", "Fermenting", "Conditioning", "Completed", "Archived"):
        abort(400)
    try:
        dados = sync_service.listar_portal_lotes(filtros, atualizar=request.args.get("refresh") == "1")
        erro = None
    except (brewfather_client.BrewFatherDisabledError, brewfather_client.BrewFatherAPIError) as exc:
        dados = {"lotes": [], "total": 0, "limitado": False}
        erro = str(exc)
    return render_template("brewfather_syncs/portal_lotes.html", **dados, filtros=filtros, erro=erro)


@brewfather_syncs_bp.route("/portal/inventario/<categoria>", methods=["GET"])
@login_required
@permission_required("brewfather_syncs.list")
def portal_inventario(categoria: str):
    if categoria not in ("fermentables", "hops", "yeasts", "miscs"):
        abort(404)
    filtros = {"q": request.args.get("q", "").strip(), "stock": request.args.get("stock", "").strip()}
    if filtros["stock"] not in ("", "positive", "other"):
        abort(400)
    try:
        dados = sync_service.listar_portal_inventario(categoria, filtros, atualizar=request.args.get("refresh") == "1")
        erro = None
    except (brewfather_client.BrewFatherDisabledError, brewfather_client.BrewFatherAPIError) as exc:
        dados = {"itens": [], "total": 0, "limitado": False,
                 "categorias": {"fermentables": "Fermentáveis", "hops": "Lúpulos",
                                "yeasts": "Leveduras", "miscs": "Outros ingredientes"}}
        erro = str(exc)
    if categoria in reconciliation.CATEGORIAS and not erro:
        vinculos = reconciliation.listar_vinculos(categoria)
        for item in dados["itens"]:
            vinculo = vinculos.get(item["id"])
            item["conciliacao"] = reconciliation.visualizar_item(categoria, item, vinculo)
            item["vinculado"] = bool(vinculo)
    return render_template("brewfather_syncs/portal_inventario.html", **dados,
                           categoria=categoria, filtros=filtros, erro=erro)


@brewfather_syncs_bp.route("/portal/inventario/<categoria>/vincular/<remote_id>", methods=["GET", "POST"])
@login_required
@permission_required("brewfather_syncs.create")
def vincular_inventario(categoria: str, remote_id: str):
    if categoria not in reconciliation.CATEGORIAS:
        abort(404)
    try:
        remoto = brewfather_client.get_inventory_item(categoria, remote_id)
    except (brewfather_client.BrewFatherDisabledError, brewfather_client.BrewFatherAPIError):
        flash("Não foi possível confirmar este item no Brewfather. Atualize o inventário e tente novamente.", "error")
        return redirect(url_for("brewfather_syncs.portal_inventario", categoria=categoria))
    if request.method == "POST":
        try:
            material_id = int(request.form.get("material_id", ""))
            reconciliation.vincular(categoria, remote_id, material_id)
            flash("Vínculo de inventário salvo. Confira a prévia de saldo antes de qualquer publicação.", "success")
            return redirect(url_for("brewfather_syncs.portal_inventario", categoria=categoria))
        except (TypeError, ValueError) as exc:
            flash(str(exc) if isinstance(exc, ValueError) and str(exc) else "Selecione um Material.", "error")
    vinculo = reconciliation.listar_vinculos(categoria).get(remote_id)
    preview = reconciliation.visualizar_item(categoria, remoto, vinculo)
    return render_template("brewfather_syncs/vincular_inventario.html", categoria=categoria,
                           remoto=remoto, vinculo=vinculo, preview=preview,
                           sugestao=reconciliation.sugestao_depara(remoto.get("name") or ""))


@brewfather_syncs_bp.route("/disponiveis/sincronizar", methods=["POST"])
@login_required
@permission_required("brewfather_syncs.create")
def sincronizar_selecionadas():
    """Recebe os ids marcados na tela de seleção e importa só esses."""
    origem_ids = request.form.getlist("origem_ids")
    if not origem_ids:
        flash("Selecione ao menos uma receita.", "error")
        return redirect(url_for("brewfather_syncs.portal"))

    try:
        acao = request.form.get("acao", "sincronizar")
        if acao not in ("sincronizar", "ressincronizar", "apagar"):
            abort(400)
        if acao == "apagar":
            if not current_user.has_permission("mash_recipes.trash"):
                abort(403)
            quantidade = sync_service.apagar_receitas_importadas(origem_ids)
            flash(f"{quantidade} receita(s) importada(s) movida(s) para a lixeira.", "success")
            return redirect(url_for("brewfather_syncs.portal"))
        resultado = sync_service.sincronizar_selecionadas(
            origem_ids, ressincronizar=acao == "ressincronizar"
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("brewfather_syncs.portal"))
    status = resultado.get("status", "?")
    processadas = resultado.get("quantidade_processada", 0)
    erros = resultado.get("quantidade_erro", 0)

    if status == "sucesso":
        flash(f"{processadas} receita(s) sincronizada(s) com sucesso.", "success")
    elif status == "parcial":
        flash(f"{processadas} receita(s) sincronizada(s), {erros} com erro.", "warning")
    else:
        flash(f"Erro ao sincronizar: {resultado.get('mensagem_erro') or 'veja o log.'}", "error")

    return redirect(url_for("brewfather_syncs.manage"))


@brewfather_syncs_bp.route("/portal/receitas/em-massa", methods=["POST"])
@login_required
@permission_required("brewfather_syncs.create")
def receitas_em_massa():
    acao = request.form.get("acao")
    try:
        if acao == "ressincronizar_todas":
            resultado = sync_service.ressincronizar_todas_importadas()
            flash(f"{resultado['quantidade_processada']} receita(s) atualizada(s); "
                  f"{resultado['quantidade_erro']} erro(s).", "success" if not resultado["quantidade_erro"] else "warning")
        elif acao == "apagar_todas":
            if not current_user.has_permission("mash_recipes.trash"):
                abort(403)
            quantidade = sync_service.apagar_receitas_importadas()
            flash(f"{quantidade} receita(s) importada(s) movida(s) para a lixeira.", "success")
        else:
            abort(400)
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("brewfather_syncs.portal"))


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
            # Cadastra Material novo em addon_estoque antes de mapear.
            # Mesma resolução de sku/origem_id/tipo_produto_id/categoria_id
            # do autocreate (ingredient_autocreate_service.py) — este é
            # um cadastro rápido pela tela de-para, sem formulário
            # completo, então os campos obrigatórios novos (ampliação de
            # Material, ver BACKLOG.md) também caem no mesmo caminho de
            # sentinela + pendente_revisao=True.
            from addons.addon_estoque.root.model.material import Material
            from addons.addon_estoque.root.services.estoque_seed import (
                get_or_create_origem_a_definir,
                get_or_create_tipo_produto_insumo,
            )
            from addons.addon_brewstation.features.feature_brew_father.services.ingredient_autocreate_service import (
                _gerar_sku,
                _get_ou_criar_categoria,
            )
            from core.db import db
            material_existente = Material.query.filter_by(nome=novo_material_nome, is_deleted=False).first()
            if material_existente:
                mid = material_existente.id
            else:
                origem = get_or_create_origem_a_definir()
                tipo_produto = get_or_create_tipo_produto_insumo()
                categoria_obj = _get_ou_criar_categoria("materia_prima")
                novo = Material(
                    nome=novo_material_nome,
                    sku=_gerar_sku(novo_material_nome, ""),
                    origem_id=origem.id,
                    tipo_produto_id=tipo_produto.id,
                    categoria_id=categoria_obj.id,
                    pendente_revisao=True,
                )
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


@brewfather_syncs_bp.route("/pendentes/cadastrar-todos", methods=["POST"])
@login_required
@permission_required("brewfather_syncs.create")
def cadastrar_todos_automaticamente():
    """Botão 'Cadastrar todos automaticamente' — chama ingredient_autocreate_service."""
    from addons.addon_brewstation.features.feature_brew_father.services import ingredient_autocreate_service

    try:
        resultado = ingredient_autocreate_service.cadastrar_todos_pendentes("BrewFather")
        criados = resultado["criados"]
        reaproveitados = resultado["reaproveitados"]
        erros = resultado["erros"]

        if not erros:
            flash(
                f"{criados} Material(is) criado(s), {reaproveitados} reaproveitado(s). "
                "Todos os ingredientes pendentes foram resolvidos.",
                "success",
            )
        else:
            flash(
                f"{criados} criado(s), {reaproveitados} reaproveitado(s). "
                f"{len(erros)} erro(s): {'; '.join(erros[:3])}",
                "warning",
            )
    except Exception as exc:  # noqa: BLE001
        flash(f"Erro ao cadastrar automaticamente: {exc}", "error")

    return redirect(url_for("brewfather_syncs.pendentes"))
