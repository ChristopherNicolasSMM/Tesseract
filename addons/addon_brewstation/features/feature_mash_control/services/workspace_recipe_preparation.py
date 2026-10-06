"""Preparação planejada da receita; serviço manual com snapshot atômico."""
from datetime import datetime, timezone
from math import isfinite
from core.db import db
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from services.core.i18n_service import translate as t
from .ingredient_resolution_service import build_recipe_snapshot
from ..model.mash_recipe import MashRecipe
from ..model.brew_session import BrewSession
from ..model.recipe_history import RecipeHistory
from ..model.fermentation_step import FermentationStep
from ..model.water_profile import WaterProfile, CONTEXTOS_WATER_PROFILE

FIELDS = {
    "recipe": ("name", "description", "volume_planejado_litros"),
    "fermentation": ("nome", "temperatura", "tempo_dias", "ordem"),
    "water": ("contexto", "calcio", "magnesio", "sodio", "cloreto", "sulfato", "bicarbonato", "ph"),
}
MODELS = {"fermentation": FermentationStep, "water": WaterProfile}


class PreparationNotFound(ValueError): pass
class PreparationConflict(ValueError): pass


def _error(key):
    return t("brewstation_mashctrl.preparation." + key)


def _number(raw, *, minimum=0, maximum=None, integer=False, required=False):
    if raw is None or str(raw).strip() == "":
        if required: raise ValueError(_error("invalid_number"))
        return None
    try:
        if isinstance(raw, bool): raise ValueError
        value = float(str(raw).replace(",", "."))
    except (ValueError, TypeError):
        raise ValueError(_error("invalid_number")) from None
    if not isfinite(value) or value < minimum or (maximum is not None and value > maximum) or (integer and not value.is_integer()):
        raise ValueError(_error("invalid_number"))
    return int(value) if integer else value


def save_preparation(recipe_id, kind, action, data, *, row_id=None, user_id=None):
    """Não altera versões utilizadas, inclusive por lotes na lixeira."""
    try:
        db.session.execute(update(MashRecipe).where(MashRecipe.id == recipe_id).values(
            updated_at=MashRecipe.updated_at).execution_options(synchronize_session=False))
        recipe = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first()
        if recipe is None: raise PreparationNotFound(_error("not_found"))
        if BrewSession.query.filter_by(recipe_id=recipe_id).first():
            raise PreparationConflict(_error("used"))
        if kind not in FIELDS or action not in ("save", "trash", "restore"):
            raise ValueError(_error("invalid_action"))
        if set(data) - set(FIELDS[kind]): raise ValueError(_error("invalid_action"))
        if kind == "recipe":
            if action != "save" or row_id is not None: raise ValueError(_error("invalid_action"))
            row = recipe
        else:
            model = MODELS[kind]
            row = model.query.filter_by(id=row_id, recipe_id=recipe_id).first() if row_id else None
            if row_id and row is None: raise PreparationNotFound(_error("not_found"))
            if action != "save" and row is None: raise PreparationNotFound(_error("not_found"))
            if row is None: row = model(recipe_id=recipe_id)
        if action == "save":
            if row.is_deleted: raise PreparationConflict(_error("restore_first"))
            clean = {}
            for key in FIELDS[kind]:
                raw = data.get(key)
                if key in ("name", "nome", "description"):
                    value = str(raw or "").strip()
                    if key == "name" and not value: raise ValueError(_error("invalid_name"))
                    if key in ("name", "nome") and len(value) > 100: raise ValueError(_error("invalid_name"))
                    clean[key] = value or None
                elif key == "contexto":
                    if raw not in CONTEXTOS_WATER_PROFILE: raise ValueError(_error("invalid_context"))
                    if row.id and raw != row.contexto: raise PreparationConflict(_error("fixed_context"))
                    clean[key] = raw
                else:
                    clean[key] = _number(raw, minimum=-5 if key == "temperatura" else 0,
                                         maximum=14 if key == "ph" else 2147483647 if key == "ordem" else None,
                                         integer=key == "ordem", required=key == "ordem")
            if kind == "water" and WaterProfile.query.filter(
                    WaterProfile.recipe_id == recipe_id, WaterProfile.contexto == clean["contexto"],
                    WaterProfile.id != (row.id or 0)).first():
                raise PreparationConflict(_error("duplicate_context"))
            if row.id and all(getattr(row, key) == value for key, value in clean.items()):
                db.session.commit()
                return row.to_dict()
            for key, value in clean.items(): setattr(row, key, value)
            db.session.add(row)
        else:
            deleted = action == "trash"
            if row.is_deleted == deleted:
                db.session.commit()
                return row.to_dict()
            row.is_deleted = deleted
            row.deleted_at = datetime.now(timezone.utc) if deleted else None
        db.session.flush()
        history = RecipeHistory(recipe_id=recipe.id, alterado_por=user_id,
                                observacao=_error("history") + f" ({kind}/{action}).")
        snapshot = build_recipe_snapshot(recipe)
        snapshot["preparation_action"] = {"kind": kind, "action": action, "row": row.to_dict()}
        history.set_snapshot(snapshot)
        db.session.add(history)
        db.session.commit()
        return row.to_dict()
    except IntegrityError:
        db.session.rollback()
        raise PreparationConflict(_error("duplicate")) from None
    except Exception:
        db.session.rollback()
        raise
