"""
controller/core/pages.py

Páginas HTML de Core — login e home. O login em si (POST) continua
sendo a API JSON (api/routes/core/auth.py); aqui é só GET para
renderizar o formulário, e a tela inicial autenticada.

Menu/cards da home vêm do catálogo de Transações (Fase 7a) — nada
hardcoded. Árvore de profundidade arbitrária desde a skill 10.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from model.core.transaction import Transaction

core_pages_bp = Blueprint("core_pages", __name__)


def _visible_transactions_tree_and_state(user_id: int | None = None) -> tuple[list, dict]:
    """
    Retorna (árvore de nós visíveis, estado resolvido de colapso/
    sidebar) — usado tanto por home() quanto pelo context_processor de
    core/app_factory.py, que também precisa do estado de colapso
    (skill 07) sem chamar resolve_menu_state() de novo.

    Skill 10: cada nó é {"tx": Transaction, "children": [...]} — pasta
    (route=None) só entra na árvore se tiver ao menos 1 filho visível
    depois do filtro de permissão (pasta vazia não aparece). TX_GROUP_CORE
    nunca aparece (mesmo comportamento de antes da skill 10, quando o
    grupo "Core" era pulado explicitamente nos templates).
    """
    all_tx = (
        Transaction.query.filter_by(is_active=True)
        .order_by(Transaction.order_index, Transaction.label)
        .all()
    )
    visible = [
        tx for tx in all_tx
        if tx.permission_required is None or current_user.has_permission(tx.permission_required)
    ]

    children_by_parent: dict = {}
    for tx in visible:
        children_by_parent.setdefault(tx.parent_id, []).append(tx)

    from services.core.menu_preference_service import resolve_menu_state, ROOT_KEY
    state = resolve_menu_state(user_id)
    order_overrides = state["order_overrides"]

    def _apply_order(nodes: list, parent_code: str | None) -> list:
        override = order_overrides.get(parent_code or ROOT_KEY)
        if not override:
            return nodes
        by_code = {n["tx"].code: n for n in nodes}
        ordered = [by_code[c] for c in override if c in by_code]
        ordered += [n for n in nodes if n["tx"].code not in override]
        return ordered

    def build(parent_id: int | None, parent_code: str | None) -> list:
        nodes = []
        for tx in children_by_parent.get(parent_id, []):
            if tx.code == "TX_GROUP_CORE":
                continue
            if tx.route is None:
                kids = build(tx.id, tx.code)
                if not kids:
                    continue  # pasta vazia não aparece no menu
                nodes.append({"tx": tx, "children": kids})
            else:
                nodes.append({"tx": tx, "children": []})
        return _apply_order(nodes, parent_code)

    tree = build(None, None)
    return tree, state


@core_pages_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("core_pages.home"))
    return render_template("core/login.html")


@core_pages_bp.route("/", methods=["GET"])
@login_required
def home():
    return render_template("core/home.html")
