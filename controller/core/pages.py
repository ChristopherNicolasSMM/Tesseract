"""
controller/core/pages.py

Páginas HTML de Core — login e home. O login em si (POST) continua
sendo a API JSON (api/routes/core/auth.py); aqui é só GET para
renderizar o formulário, e a tela inicial autenticada.

Menu/cards da home vêm do catálogo de Transações (Fase 7a) — nada
hardcoded.
"""
from collections import OrderedDict
#from urllib import request

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from model.core.transaction import Transaction

core_pages_bp = Blueprint("core_pages", __name__)


def _visible_transactions_by_group() -> OrderedDict:
    all_tx = (
        Transaction.query.filter_by(is_active=True)
        .order_by(Transaction.group, Transaction.label)
        .all()
    )
    visible = [
        tx for tx in all_tx
        if tx.permission_required is None or current_user.has_permission(tx.permission_required)
    ]

    grouped: OrderedDict = OrderedDict()
    for tx in visible:
        grouped.setdefault(tx.group, []).append(tx)
    return grouped


@core_pages_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("core_pages.home"))
    return render_template("core/login.html")


@core_pages_bp.route("/", methods=["GET"])
@login_required
def home():
    return render_template(
        "core/home.html",
        transactions_by_group=_visible_transactions_by_group(),
    )

