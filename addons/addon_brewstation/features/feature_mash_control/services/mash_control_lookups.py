"""
addons/addon_brewstation/features/feature_mash_control/services/mash_control_lookups.py

Pontos de acesso públicos e estáveis pra resolver BrewPlant/
BrewPlantVessel/DashboardLayout/MashRecipe/BrewSession/
BrewSessionStep/RecipeStep/RecipeIngredient/AutomationRule por `id`
— usados por `@weak_ref` (skill 11) de campos que são FK real
DENTRO da própria Feature. A FK real continua a mesma (skill 02
permite FK real dentro da mesma Feature) — isto só acrescenta o
combo de busca na UI, reaproveitando o mesmo mecanismo já usado pra
referência fraca cross-Addon (skill 11), em vez de inventar um
segundo mecanismo só pra FK real.
   
NÃO gerado pelo CrudGen, não sobrescrito por ele — mesmo padrão de
`device_function_lookup.py`/`automation_engine.py`.
"""
from __future__ import annotations

from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule


def _resolve(model_cls, obj_id, *, not_found_label: str) -> dict | None:
    if not obj_id:
        return None
    obj = model_cls.query.filter_by(id=obj_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(model_cls, "_display_field", "id")
    data["display"] = getattr(obj, display_field, None) or f"{not_found_label} #{obj.id}"
    return data


def get_plant(plant_id: int | None) -> dict | None:
    return _resolve(BrewPlant, plant_id, not_found_label="Planta")


def get_vessel(vessel_id: int | None) -> dict | None:
    return _resolve(BrewPlantVessel, vessel_id, not_found_label="Tanque")


def get_layout(layout_id: int | None) -> dict | None:
    return _resolve(DashboardLayout, layout_id, not_found_label="Layout")


def get_recipe(recipe_id: int | None) -> dict | None:
    return _resolve(MashRecipe, recipe_id, not_found_label="Receita")


def get_session(session_id: int | None) -> dict | None:
    return _resolve(BrewSession, session_id, not_found_label="Sessão")


def get_session_step(step_id: int | None) -> dict | None:
    return _resolve(BrewSessionStep, step_id, not_found_label="Passo da Sessão")


def get_recipe_step(recipe_step_id: int | None) -> dict | None:
    return _resolve(RecipeStep, recipe_step_id, not_found_label="Etapa da Receita")


def get_recipe_ingredient(recipe_ingredient_id: int | None) -> dict | None:
    return _resolve(RecipeIngredient, recipe_ingredient_id, not_found_label="Ingrediente da Receita")


def get_rule(rule_id: int | None) -> dict | None:
    return _resolve(AutomationRule, rule_id, not_found_label="Regra de Automação")
