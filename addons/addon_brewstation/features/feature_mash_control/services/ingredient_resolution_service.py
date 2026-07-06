"""
addons/addon_brewstation/features/feature_mash_control/services/ingredient_resolution_service.py

Nao e gerado pelo CrudGen (mesmo papel de material_lookup.py em
addon_estoque) - e o ponto de extensao estavel para:

1. Resolucao de ingrediente na importacao de receita (de-para) -
   reaproveitavel por qualquer importador (feature_brew_father hoje,
   futura feature_beersmith/BeerXML), que so precisa fazer o parse do
   formato de origem e chamar resolver_ingrediente() por ingrediente.
2. Versionamento de receita - toda edicao salva cria uma nova versao
   (nunca UPDATE de uma versao existente), com snapshot em
   RecipeHistory.

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
    db.session.commit()

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


def criar_nova_versao(
    recipe_id: int,
    dados_atualizados: dict,
    *,
    usuario_id: int | None = None,
    observacao: str | None = None,
) -> dict:
    """
    Cria uma nova MashRecipe (mesma name, versao+1) a partir de uma
    receita existente, copiando os RecipeIngredient atuais (o
    chamador pode sobrescrever campos específicos via
    dados_atualizados, ex.: {"description": "novo texto"}) e grava um
    snapshot completo em RecipeHistory. A versão anterior nunca é
    alterada.
    """
    receita_atual = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first()
    if receita_atual is None:
        raise ReceitaNaoEncontradaError(f"MashRecipe id={recipe_id} não encontrada ou removida")

    campos_permitidos = {"description", "equipment_mapping", "origem_receita", "origem_receita_id", "is_active"}
    nova_receita = MashRecipe(
        name=receita_atual.name,
        versao=receita_atual.versao + 1,
        description=dados_atualizados.get("description", receita_atual.description),
        equipment_mapping=dados_atualizados.get("equipment_mapping", receita_atual.equipment_mapping),
        origem_receita=dados_atualizados.get("origem_receita", receita_atual.origem_receita),
        origem_receita_id=dados_atualizados.get("origem_receita_id", receita_atual.origem_receita_id),
        created_by=usuario_id or receita_atual.created_by,
        is_active=dados_atualizados.get("is_active", receita_atual.is_active),
    )
    for chave in dados_atualizados:
        if chave not in campos_permitidos:
            raise ValueError(f"Campo não editável em nova versão: {chave!r}")

    db.session.add(nova_receita)
    db.session.flush()  # garante nova_receita.id sem commitar ainda

    ingredientes_novos = []
    for ingrediente_atual in receita_atual.ingredientes:
        novo = RecipeIngredient(
            recipe_id=nova_receita.id,
            material_id=ingrediente_atual.material_id,
            descricao_origem=ingrediente_atual.descricao_origem,
            quantidade=ingrediente_atual.quantidade,
            unidade_medida=ingrediente_atual.unidade_medida,
            tempo_adicao_min=ingrediente_atual.tempo_adicao_min,
            etapa=ingrediente_atual.etapa,
            status_resolucao=ingrediente_atual.status_resolucao,
        )
        db.session.add(novo)
        ingredientes_novos.append(novo)

    db.session.flush()

    snapshot = {
        "recipe": nova_receita.to_dict(),
        "ingredientes": [i.to_dict() for i in ingredientes_novos],
    }
    historico = RecipeHistory(
        recipe_id=nova_receita.id,
        alterado_por=usuario_id,
        alterado_em=datetime.now(timezone.utc),
        observacao=observacao,
    )
    historico.set_snapshot(snapshot)
    db.session.add(historico)

    db.session.commit()

    return {
        "recipe": nova_receita.to_dict(),
        "ingredientes": [i.to_dict() for i in ingredientes_novos],
        "history_id": historico.id,
    }
