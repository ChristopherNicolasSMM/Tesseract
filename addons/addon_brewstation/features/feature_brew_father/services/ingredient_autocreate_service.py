"""
addons/addon_brewstation/features/feature_brew_father/services/ingredient_autocreate_service.py

Orquestra o fluxo "Cadastrar todos automaticamente": para cada
RecipeIngredient pendente de resolucao (status_resolucao="pendente_depara"
com origem_receita="BrewFather"), cria Material em addon_estoque e, se
tipo_ingrediente for conhecido, cria a spec correspondente em
feature_ingredientes (Malte/Lupulo/Levedura) — depois chama
confirmar_mapeamento() para ligar tudo.

Reaproveitavel por futuras integracoes (feature_beersmith, etc.) —
mesmo principio de ingredient_resolution_service (nao duplicar logica).
"""
from __future__ import annotations

from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.services.material_lookup import material_exists
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.services.ingredient_resolution_service import confirmar_mapeamento


class AutoCadastroError(Exception):
    pass


def _get_ou_criar_material(nome: str, categoria: str) -> Material:
    """Retorna Material existente por nome (unique) ou cria um novo."""
    existente = Material.query.filter_by(nome=nome, is_deleted=False).first()
    if existente:
        return existente
    novo = Material(nome=nome, categoria=categoria)
    db.session.add(novo)
    db.session.flush()
    return novo


def _criar_spec_se_necessario(material: Material, ingrediente: RecipeIngredient) -> None:
    """Cria registro de spec (Malte/Lupulo/Levedura) em feature_ingredientes
    se ainda não existir para este Material e tipo for conhecido."""
    tipo = (ingrediente.tipo_ingrediente or "").lower()

    if tipo == "fermentavel":
        from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
        if not Malte.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Malte(
                material_id=material.id,
                cor_ebc=ingrediente.cor_ebc,
                rendimento=ingrediente.rendimento,
            ))

    elif tipo == "lupulo":
        from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
        if not Lupulo.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Lupulo(
                material_id=material.id,
                alpha_acidos=ingrediente.alpha_acidos,
            ))

    elif tipo == "levedura":
        from addons.addon_brewstation.features.feature_ingredientes.model.levedura import Levedura
        if not Levedura.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Levedura(
                material_id=material.id,
                atenuacao=ingrediente.atenuacao,
            ))


_TIPO_PARA_CATEGORIA = {
    "fermentavel": "materia_prima",
    "lupulo": "materia_prima",
    "levedura": "materia_prima",
}


def cadastrar_todos_pendentes(origem_receita: str = "BrewFather") -> dict:
    """
    Para cada RecipeIngredient pendente da origem dada:
    1. Cria Material em addon_estoque (ou reutiliza se já existir pelo nome)
    2. Cria spec em feature_ingredientes se tipo_ingrediente conhecido
    3. Chama confirmar_mapeamento() — grava cache de-para e resolve todos
       os pendentes com a mesma descricao_origem/origem_receita

    Retorna {"criados": int, "reaproveitados": int, "erros": list[str]}
    """
    pendentes = (
        RecipeIngredient.query
        .filter_by(status_resolucao="pendente_depara", is_deleted=False)
        .join(MashRecipe, RecipeIngredient.recipe_id == MashRecipe.id)
        .filter(MashRecipe.origem_receita == origem_receita)
        .all()
    )

    # Agrupa por descricao_origem pra não processar a mesma descrição N vezes
    grupos: dict[str, RecipeIngredient] = {}
    for ing in pendentes:
        if ing.descricao_origem not in grupos:
            grupos[ing.descricao_origem] = ing

    criados = 0
    reaproveitados = 0
    erros = []

    for descricao, ing in grupos.items():
        try:
            categoria = _TIPO_PARA_CATEGORIA.get(
                (ing.tipo_ingrediente or "").lower(), "materia_prima"
            )
            era_existente = material_exists
            material = _get_ou_criar_material(descricao, categoria)

            if material_exists(material.id) and not db.session.is_modified(material):
                reaproveitados += 1
            else:
                criados += 1

            _criar_spec_se_necessario(material, ing)
            db.session.flush()

            confirmar_mapeamento(origem_receita, descricao, material.id)

        except Exception as exc:  # noqa: BLE001
            erros.append(f"{descricao}: {exc}")
            db.session.rollback()

    return {"criados": criados, "reaproveitados": reaproveitados, "erros": erros}
