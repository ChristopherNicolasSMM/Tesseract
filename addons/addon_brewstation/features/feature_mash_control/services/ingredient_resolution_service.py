"""
addons/addon_brewstation/features/feature_mash_control/services/ingredient_resolution_service.py

Nao e gerado pelo CrudGen (mesmo papel de material_lookup.py em
addon_estoque) - e o ponto de extensao estavel para:

1. Resolucao de ingrediente na importacao de receita (de-para) -
   reaproveitavel por qualquer importador (feature_brew_father hoje,
   futura feature_beersmith/BeerXML), que so precisa fazer o parse do
   formato de origem e chamar resolver_ingrediente() por ingrediente.
2. Versionamento de receita - copia do planejamento ativo em nova versao
   com snapshot em RecipeHistory. A edicao local de ingredientes de uma
   receita sem sessoes fica em ingredient_sanitation_service.py.

Ver addons/addon_brewstation/features/feature_mash_control/docs/technical/03-fluxos.md
para o desenho completo dos dois fluxos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe, ORIGENS_RECEITA
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile


class OrigemInvalidaError(Exception):
    pass


class ReceitaNaoEncontradaError(Exception):
    pass


def _validar_origem(origem_receita: str) -> None:
    if origem_receita not in ORIGENS_RECEITA:
        raise OrigemInvalidaError(f"origem_receita deve ser um de {ORIGENS_RECEITA}, recebido: {origem_receita!r}")


def resolver_ingrediente(
    recipe_id: int,
    origem_receita: str,
    descricao_origem: str,
    *,
    quantidade: float | None = None,
    unidade_medida: str | None = None,
    tempo_adicao_min: int | None = None,
    etapa: str | None = None,
    uso_detalhado: str | None = None,
    tipo_ingrediente: str | None = None,
    cor_ebc: float | None = None,
    rendimento: float | None = None,
    alpha_acidos: float | None = None,
    atenuacao: float | None = None,
    commit: bool = True,
) -> dict:
    """
    Cria um RecipeIngredient para a receita, tentando resolver contra
    o cache de-para (IngredientMapping) primeiro. Se não houver
    mapeamento conhecido, o ingrediente entra como
    status_resolucao="pendente_depara" (material_id nulo) — a busca
    aproximada (material_lookup.buscar_material_por_termo) fica a
    cargo da tela, que apresenta candidatos ao usuário; esta função
    nunca resolve por aproximação sozinha, só por mapeamento já
    confirmado antes.
    """
    _validar_origem(origem_receita)

    mapping = IngredientMapping.query.filter_by(
        origem_receita=origem_receita, descricao_origem=descricao_origem, is_deleted=False,
    ).first()

    if mapping is not None:
        material_id = mapping.material_id
        status = "resolvido"
    else:
        material_id = None
        status = "pendente_depara"

    ingrediente = RecipeIngredient(
        recipe_id=recipe_id,
        material_id=material_id,
        descricao_origem=descricao_origem,
        quantidade=quantidade,
        unidade_medida=unidade_medida,
        tempo_adicao_min=tempo_adicao_min,
        etapa=etapa,
        uso_detalhado=uso_detalhado,
        tipo_ingrediente=tipo_ingrediente,
        cor_ebc=cor_ebc,
        rendimento=rendimento,
        alpha_acidos=alpha_acidos,
        atenuacao=atenuacao,
        status_resolucao=status,
    )
    db.session.add(ingrediente)
    if commit:
        db.session.commit()
    else:
        db.session.flush()

    return ingrediente.to_dict()


def confirmar_mapeamento(origem_receita: str, descricao_origem: str, material_id: int) -> dict:
    """
    Registra (ou atualiza) o de-para no cache e resolve, na mesma
    operação, todos os RecipeIngredient pendentes com a mesma
    origem+descrição — não só o que motivou a confirmação agora.

    Assume que `origem_receita` de um RecipeIngredient é sempre igual
    ao `origem_receita` da MashRecipe que o contém (RecipeIngredient
    não guarda a própria origem — resolvida via join com MashRecipe).
    Isso vale no fluxo real (toda receita importada de uma origem tem
    todos os ingredientes resolvidos com a mesma origem), mas não
    resolve pendências de uma receita cuja origem não bate com a
    origem passada aqui.
    """
    _validar_origem(origem_receita)

    if not material_lookup.material_exists(material_id):
        raise ValueError(f"Material id={material_id} não encontrado em addon_estoque")

    mapping = IngredientMapping.query.filter_by(
        origem_receita=origem_receita, descricao_origem=descricao_origem,
    ).first()
    if mapping is None:
        mapping = IngredientMapping(
            origem_receita=origem_receita, descricao_origem=descricao_origem, material_id=material_id,
        )
        db.session.add(mapping)
    else:
        mapping.material_id = material_id
        mapping.is_deleted = False

    pendentes = RecipeIngredient.query.filter_by(
        descricao_origem=descricao_origem, status_resolucao="pendente_depara",
    ).join(MashRecipe, RecipeIngredient.recipe_id == MashRecipe.id).filter(
        MashRecipe.origem_receita == origem_receita,
    ).all()
    for ingrediente in pendentes:
        ingrediente.material_id = material_id
        ingrediente.status_resolucao = "resolvido"

    db.session.commit()

    return {"mapping": mapping.to_dict(), "ingredientes_resolvidos": len(pendentes)}


def build_recipe_snapshot(receita: MashRecipe) -> dict:
    """Fotografia dos dados planejados ativos; não inclui execuções de lotes."""
    snapshot = {"recipe": receita.to_dict()}
    for key, model in (("ingredientes", RecipeIngredient), ("recipe_steps", RecipeStep),
                       ("fermentation_steps", FermentationStep), ("water_profiles", WaterProfile)):
        snapshot[key] = [row.to_dict() for row in model.query.filter_by(
            recipe_id=receita.id, is_deleted=False).order_by(model.id).all()]
    return snapshot


def _copy_plan_fields(obj, *, exclude=()):
    # Somente colunas escalares, sem identidades, lixeira ou metadados de criação.
    skip = {"id", "recipe_id", "is_deleted", "deleted_at", "created_at", "updated_at",
            "created_by", "versao", *exclude}
    return {column.key: getattr(obj, column.key) for column in obj.__table__.columns
            if column.key not in skip}


def criar_nova_versao(
    recipe_id: int,
    dados_atualizados: dict,
    *,
    usuario_id: int | None = None,
    observacao: str | None = None,
    commit: bool = True,
) -> dict:
    """Copia integralmente o planejamento ativo em uma revisão isolada.

    Remapeia referências de alertas para etapas/ingredientes novos. Não copia
    sessões, custos registrados, envases ou lixeira. O próximo número é maior
    que todas as versões do mesmo nome, inclusive ao revisar versão antiga.
    Conflito concorrente de versão causa rollback, permitindo nova tentativa.
    """
    try:
        if not isinstance(recipe_id, int) or isinstance(recipe_id, bool) or recipe_id <= 0:
            raise ReceitaNaoEncontradaError("Receita não encontrada.")
        receita_atual = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first()
        if receita_atual is None:
            raise ReceitaNaoEncontradaError("Receita não encontrada ou removida.")
        campos_permitidos = {"description", "equipment_mapping", "origem_receita",
                             "origem_receita_id", "is_active"}
        for chave in dados_atualizados:
            if chave not in campos_permitidos:
                raise ValueError(f"Campo não editável em nova versão: {chave!r}")
        if "origem_receita" in dados_atualizados:
            _validar_origem(dados_atualizados["origem_receita"])
        campos = _copy_plan_fields(receita_atual)
        campos.update(dados_atualizados)
        max_versao = db.session.query(db.func.max(MashRecipe.versao)).filter_by(
            name=receita_atual.name).scalar() or 0
        nova_receita = MashRecipe(**campos, versao=max_versao + 1,
                                  created_by=usuario_id if usuario_id is not None else receita_atual.created_by)
        db.session.add(nova_receita)
        db.session.flush()

        ingredientes = RecipeIngredient.query.filter_by(recipe_id=recipe_id, is_deleted=False).order_by(RecipeIngredient.id).all()
        ingredient_map = {}
        for ingrediente in ingredientes:
            novo = RecipeIngredient(recipe_id=nova_receita.id, **_copy_plan_fields(ingrediente))
            db.session.add(novo)
            db.session.flush()
            ingredient_map[ingrediente.id] = novo.id

        steps = RecipeStep.query.filter_by(recipe_id=recipe_id, is_deleted=False).order_by(RecipeStep.id).all()
        step_map = {}
        for step in steps:
            novo = RecipeStep(recipe_id=nova_receita.id, **_copy_plan_fields(
                step, exclude=("parent_step_id", "source_recipe_ingredient_id")))
            db.session.add(novo)
            db.session.flush()
            step_map[step.id] = novo
        for step in steps:
            if step.parent_step_id is not None and step.parent_step_id not in step_map:
                raise ValueError("Uma etapa referencia pai apagado ou de outra receita. Corrija antes de revisar.")
            if step.source_recipe_ingredient_id is not None and step.source_recipe_ingredient_id not in ingredient_map:
                raise ValueError("Um alerta referencia ingrediente apagado ou de outra receita. Corrija antes de revisar.")
            novo = step_map[step.id]
            novo.parent_step_id = step_map[step.parent_step_id].id if step.parent_step_id is not None else None
            novo.source_recipe_ingredient_id = ingredient_map.get(step.source_recipe_ingredient_id)

        for model in (FermentationStep, WaterProfile):
            for row in model.query.filter_by(recipe_id=recipe_id, is_deleted=False).order_by(model.id).all():
                db.session.add(model(recipe_id=nova_receita.id, **_copy_plan_fields(row)))
        db.session.flush()
        snapshot = build_recipe_snapshot(nova_receita)
        snapshot["source_recipe_id"] = recipe_id
        historico = RecipeHistory(recipe_id=nova_receita.id, alterado_por=usuario_id,
                                  alterado_em=datetime.now(timezone.utc), observacao=observacao)
        historico.set_snapshot(snapshot)
        db.session.add(historico)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return {**snapshot, "history_id": historico.id}
    except Exception:
        db.session.rollback()
        raise
