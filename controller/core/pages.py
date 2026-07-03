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

    Skill 10 §8.1: `order_overrides` deixa de servir só pra ORDEM —
    também define, implicitamente, sob qual pai (real ou "virtual") um
    código aparece: se um code está listado em `order_overrides[X]`,
    ele é exibido sob X mesmo que `Transaction.parent_id` real aponte
    pra outro lugar. É assim que "promover/rebaixar" na tela de
    exibição (pessoal ou padrão global) funciona sem tocar o banco —
    só a estrutura REAL (Transaction.parent_id) muda em
    controller/core/admin_transactions.py (promote/demote).
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
    visible_by_code = {tx.code: tx for tx in visible}

    from services.core.menu_preference_service import resolve_menu_state, ROOT_KEY
    state = resolve_menu_state(user_id)
    order_overrides = state["order_overrides"]

    # Índice reverso: code -> chave de pai (real ou "__root__") sob a qual
    # ele deve aparecer, segundo o override — última menção vence se o
    # mesmo code aparecer em mais de uma lista (dado mal formado não deveria
    # acontecer vindo da própria UI, mas não quebra se acontecer).
    override_parent_of: dict[str, str] = {}
    for parent_key, child_codes in order_overrides.items():
        for child_code in child_codes:
            override_parent_of[child_code] = parent_key

    def _effective_parent_code(tx: Transaction) -> str | None:
        if tx.code in override_parent_of:
            key = override_parent_of[tx.code]
            return None if key == ROOT_KEY else key
        return tx.parent.code if tx.parent_id and tx.parent else None

    children_by_parent_code: dict = {}
    for tx in visible:
        if tx.code == "TX_GROUP_CORE":
            continue
        pcode = _effective_parent_code(tx)
        children_by_parent_code.setdefault(pcode, []).append(tx)

    def _apply_order(txs: list, parent_code: str | None) -> list:
        override = order_overrides.get(parent_code or ROOT_KEY)
        if not override:
            return txs
        by_code = {t.code: t for t in txs}
        ordered = [by_code[c] for c in override if c in by_code]
        ordered += [t for t in txs if t.code not in override]
        return ordered

    def build(parent_code: str | None, ancestors: frozenset) -> list:
        nodes = []
        txs = _apply_order(children_by_parent_code.get(parent_code, []), parent_code)
        for tx in txs:
            if tx.code in ancestors:
                continue  # guarda contra ciclo (override malformado) — nunca deveria acontecer
            if tx.route is None:
                kids = build(tx.code, ancestors | {tx.code})
                if not kids:
                    continue  # pasta vazia não aparece no menu
                nodes.append({"tx": tx, "children": kids})
            else:
                nodes.append({"tx": tx, "children": []})
        return nodes

    tree = build(None, frozenset())
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
