from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from core.permissions import permission_required
from core.db import db

brew_dashboard_new_bp = Blueprint(
    "brew_dash_new", __name__, url_prefix="/brewstation/dashboard-new"
)



#@brew_dashboard_new_bp.route("/login", methods=["GET"])
#def login_page():
#    if current_user.is_authenticated:
#        return redirect(url_for("core_pages.home"))
#    return render_template("core/login.html")


@brew_dashboard_new_bp.route("/", methods=["GET"])
@login_required
def home():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    #query = _apply_filters(BrewSessionAlarm.query.filter(BrewSessionAlarm.is_deleted.is_(False)))
    #total = query.count()
    #items = query.order_by(BrewSessionAlarm.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    #pages = max(1, (total + per_page - 1) // per_page)    
    return render_template("brew_dashboard_new/dashboard.html", page=page)#, pages=pages, total=total, per_page=per_page, search=search,)

#    return render_template(
#        "brew_session_logs/manage.html",
#        items=items, label="Log da Sessão", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
#        page=page, pages=pages, total=total, per_page=per_page, search=search,
#        visible_columns=_get_column_prefs(),
#        boolean_fields=_BOOLEAN_FIELDS, choices_fields=_CHOICES_FIELDS,
#        choices_options=_choices_options(), request_args=request.args,
#        field_rules=_get_field_rules(),
#    )

#/brewstation/dashboard-new