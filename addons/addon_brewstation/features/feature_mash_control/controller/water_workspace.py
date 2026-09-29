"""Consulta de água agrupada por receita, fora dos arquivos do CrudGen."""
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile

water_workspace_bp = Blueprint("water_workspace", __name__, url_prefix="/brewstation/water-profiles/portal")
CONTEXTS = {"source": "Água de origem", "target": "Perfil alvo", "mash": "Mostura",
            "sparge": "Lavagem", "total": "Mistura total"}
FIELDS = (("calcio", "Cálcio"), ("magnesio", "Magnésio"), ("sodio", "Sódio"),
          ("cloreto", "Cloreto"), ("sulfato", "Sulfato"), ("bicarbonato", "Bicarbonato"))


@water_workspace_bp.before_app_request
def open_grouped_water_view():
    # A lista gerada permanece disponível explicitamente para manutenção.
    # A navegação habitual e os links antigos chegam à consulta agrupada.
    if request.endpoint == "water_profiles.manage" and request.args.get("view") != "records":
        return redirect(url_for("water_workspace.index", q=request.args.get("q", "")))


@water_workspace_bp.route("/", methods=["GET"])
@login_required
@permission_required("water_profiles.list")
def index():
    q = (request.args.get("q") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    query = (db.session.query(MashRecipe, db.func.count(WaterProfile.id))
             .join(WaterProfile, WaterProfile.recipe_id == MashRecipe.id)
             .filter(MashRecipe.is_deleted.is_(False), WaterProfile.is_deleted.is_(False)))
    if q:
        query = query.filter(MashRecipe.name.ilike(f"%{q}%"))
    query = query.group_by(MashRecipe.id).order_by(MashRecipe.name, MashRecipe.versao.desc(), MashRecipe.id)
    rows = query.offset((page - 1) * 24).limit(25).all()
    return render_template("water_workspace/index.html", rows=rows[:24], q=q,
                           page=page, has_next=len(rows) > 24)


@water_workspace_bp.route("/<int:recipe_id>", methods=["GET"])
@login_required
@permission_required("water_profiles.list")
def detail(recipe_id):
    recipe = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first_or_404()
    profiles = WaterProfile.query.filter_by(recipe_id=recipe_id, is_deleted=False).all()
    rank = {key: i for i, key in enumerate(CONTEXTS)}
    profiles.sort(key=lambda item: (rank.get(item.contexto, 99), item.id))
    return render_template("water_workspace/detail.html", recipe=recipe, profiles=profiles,
                           contexts=CONTEXTS, fields=FIELDS)
