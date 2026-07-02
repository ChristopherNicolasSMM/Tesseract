"""
controller/core/admin_transactions.py

Tela de gestão do catálogo de Transações. Diferente de Permission
("código lidera, banco segue" — nunca editável pela UI), Transaction
tem duas origens:

- **Vinda do código** (`is_standard=True` ou `source_module`
  preenchido por um Addon/Feature via `get_transactions()`): só
  `is_active` é seguro editar aqui — `sync_transaction()`
  (core/transactions_sync.py) SOBRESCREVE label/rota/ícone/pai a
  partir do código em todo boot. Editar esses campos aqui daria a
  falsa impressão de persistir, quando na verdade se perde no próximo
  restart. Por isso o formulário completo só aparece pra transações
  manuais.
- **Manual** (`source_module="manual"`, criada por aqui): totalmente
  editável e excluível — não existe em nenhum código pra sobrescrever.

Árvore (skill 10): `group` (string) foi substituído por `parent_id` —
o form usa um seletor de pai (qualquer nó-pasta existente, `route IS
NULL`) em vez de texto livre. Deixar `route` em branco na criação cria
um nó-pasta novo, disponível como pai pra próximas transações.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from model.core.transaction import Transaction

admin_transactions_bp = Blueprint("admin_transactions", __name__, url_prefix="/admin/transactions")

_EXPORT_HEADERS = ["code", "label", "caminho", "route", "permission_required", "is_active", "origem"]


def _is_code_sourced(tx: Transaction) -> bool:
    return bool(tx.is_standard or (tx.source_module and tx.source_module != "manual"))


def _breadcrumb(tx: Transaction) -> str:
    parts = [tx.label]
    node = tx.parent
    seen_ids = {tx.id}
    while node is not None and node.id not in seen_ids:
        parts.append(node.label)
        seen_ids.add(node.id)
        node = node.parent
    return " > ".join(reversed(parts))


def _filtered_query(search: str):
    query = Transaction.query.order_by(Transaction.order_index, Transaction.label)
    if search:
        like = f"%{search}%"
        query = query.filter(Transaction.label.ilike(like) | Transaction.code.ilike(like))
    return query


def _folder_options(exclude_id: int | None = None):
    """Nós-pasta (route IS NULL) — únicos candidatos válidos a pai."""
    query = Transaction.query.filter(Transaction.route.is_(None)).order_by(Transaction.label)
    if exclude_id is not None:
        query = query.filter(Transaction.id != exclude_id)
    return query.all()


@admin_transactions_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    transactions, total, pages = paginate(_filtered_query(search), page)
    return render_template(
        "core/admin/transactions_manage.html",
        transactions=transactions, is_code_sourced=_is_code_sourced, breadcrumb=_breadcrumb,
        folder_options=_folder_options(),
        search=search, total=total, page=page, pages=pages,
    )


@admin_transactions_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    rows = [
        [tx.code, tx.label, _breadcrumb(tx), tx.route, tx.permission_required, tx.is_active,
         "Manual" if tx.source_module == "manual" else (tx.source_module or "Core")]
        for tx in _filtered_query(search).all()
    ]
    return export_csv_response(_EXPORT_HEADERS, rows, "transacoes")


@admin_transactions_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    rows = [
        [tx.code, tx.label, _breadcrumb(tx), tx.route, tx.permission_required, tx.is_active,
         "Manual" if tx.source_module == "manual" else (tx.source_module or "Core")]
        for tx in _filtered_query(search).all()
    ]
    return export_xlsx_response(_EXPORT_HEADERS, rows, "transacoes", "Transações")


@admin_transactions_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    code = (request.form.get("code") or "").strip()
    label = (request.form.get("label") or "").strip()
    route = (request.form.get("route") or "").strip() or None  # vazio = nó-pasta novo
    parent_id = request.form.get("parent_id", type=int) or None

    if not code or not label:
        flash("Código e label são obrigatórios.", "error")
        return redirect(url_for("admin_transactions.manage"))

    if Transaction.query.filter_by(code=code).first():
        flash(f"Já existe uma transação com o código '{code}'.", "error")
        return redirect(url_for("admin_transactions.manage"))

    tx = Transaction(
        code=code, label=label, route=route, parent_id=parent_id,
        icon=(request.form.get("icon") or "").strip() or None,
        description=(request.form.get("description") or "").strip() or None,
        permission_required=(request.form.get("permission_required") or "").strip() or None,
        is_active=True, is_standard=False, source_module="manual",
    )
    db.session.add(tx)
    db.session.commit()
    flash(f"Transação '{label}' criada.", "success")
    return redirect(url_for("admin_transactions.manage"))


@admin_transactions_bp.route("/<int:tx_id>", methods=["POST"])
@login_required
@permission_required("admin")
def update(tx_id: int):
    tx = Transaction.query.get(tx_id)
    if not tx:
        flash("Transação não encontrada.", "error")
        return redirect(url_for("admin_transactions.manage"))

    if _is_code_sourced(tx):
        flash(
            "Esta transação vem do código — label/rota/ícone/pai são "
            "sobrescritos a cada boot pelo sync. Só 'Ativa/Inativa' é "
            "editável aqui.",
            "error",
        )
        return redirect(url_for("admin_transactions.manage"))

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("Label é obrigatório.", "error")
        return redirect(url_for("admin_transactions.manage"))

    parent_id = request.form.get("parent_id", type=int) or None
    if parent_id == tx.id:
        flash("Uma Transação não pode ser pai dela mesma.", "error")
        return redirect(url_for("admin_transactions.manage"))

    tx.label = label
    tx.route = (request.form.get("route") or "").strip() or None
    tx.parent_id = parent_id
    tx.icon = (request.form.get("icon") or "").strip() or None
    tx.description = (request.form.get("description") or "").strip() or None
    tx.permission_required = (request.form.get("permission_required") or "").strip() or None
    db.session.commit()
    flash("Transação atualizada.", "success")
    return redirect(url_for("admin_transactions.manage"))


@admin_transactions_bp.route("/<int:tx_id>/toggle", methods=["POST"])
@login_required
@permission_required("admin")
def toggle(tx_id: int):
    tx = Transaction.query.get(tx_id)
    if tx:
        tx.is_active = not tx.is_active
        db.session.commit()
    return redirect(url_for("admin_transactions.manage"))


@admin_transactions_bp.route("/<int:tx_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(tx_id: int):
    tx = Transaction.query.get(tx_id)
    if not tx:
        flash("Transação não encontrada.", "error")
        return redirect(url_for("admin_transactions.manage"))

    if tx.is_standard or (tx.source_module and tx.source_module != "manual"):
        flash(
            "Esta transação vem do código (Core ou Addon/Feature) — "
            "desative em vez de excluir, ou ela volta no próximo boot.",
            "error",
        )
        return redirect(url_for("admin_transactions.manage"))

    if Transaction.query.filter_by(parent_id=tx.id).first():
        flash(
            "Esta transação é pai de outra(s) — mova os filhos antes "
            "de excluir, ou desative em vez de excluir.",
            "error",
        )
        return redirect(url_for("admin_transactions.manage"))

    db.session.delete(tx)
    db.session.commit()
    flash("Transação removida.", "success")
    return redirect(url_for("admin_transactions.manage"))
