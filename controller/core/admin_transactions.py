"""
controller/core/admin_transactions.py

Tela de gestão do catálogo de Transações. Diferente de Permission
("código lidera, banco segue" — nunca editável pela UI), Transaction
tem duas origens:

- **Vinda do código** (`is_standard=True` ou `source_module`
  preenchido por um Addon/Feature via `get_transactions()`): só
  `is_active` é seguro editar aqui — `sync_transaction()`
  (core/transactions_sync.py) SOBRESCREVE label/rota/ícone/grupo a
  partir do código em todo boot. Editar esses campos aqui daria a
  falsa impressão de persistir, quando na verdade se perde no próximo
  restart. Por isso o formulário completo só aparece pra transações
  manuais.
- **Manual** (`source_module="manual"`, criada por aqui): totalmente
  editável e excluível — não existe em nenhum código pra sobrescrever.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from model.core.transaction import Transaction

admin_transactions_bp = Blueprint("admin_transactions", __name__, url_prefix="/admin/transactions")


def _is_code_sourced(tx: Transaction) -> bool:
    return bool(tx.is_standard or (tx.source_module and tx.source_module != "manual"))


@admin_transactions_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    transactions = Transaction.query.order_by(Transaction.group, Transaction.label).all()
    return render_template(
        "core/admin/transactions_manage.html",
        transactions=transactions, is_code_sourced=_is_code_sourced,
    )


@admin_transactions_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    code = (request.form.get("code") or "").strip()
    label = (request.form.get("label") or "").strip()
    group = (request.form.get("group") or "Geral").strip()
    route = (request.form.get("route") or "").strip()

    if not code or not label or not route:
        flash("Código, label e rota são obrigatórios.", "error")
        return redirect(url_for("admin_transactions.manage"))

    if Transaction.query.filter_by(code=code).first():
        flash(f"Já existe uma transação com o código '{code}'.", "error")
        return redirect(url_for("admin_transactions.manage"))

    tx = Transaction(
        code=code, label=label, group=group, route=route,
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
            "Esta transação vem do código — label/rota/ícone são "
            "sobrescritos a cada boot pelo sync. Só 'Ativa/Inativa' é "
            "editável aqui.",
            "error",
        )
        return redirect(url_for("admin_transactions.manage"))

    label = (request.form.get("label") or "").strip()
    route = (request.form.get("route") or "").strip()
    if not label or not route:
        flash("Label e rota são obrigatórios.", "error")
        return redirect(url_for("admin_transactions.manage"))

    tx.label = label
    tx.group = (request.form.get("group") or tx.group or "Geral").strip()
    tx.route = route
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

    db.session.delete(tx)
    db.session.commit()
    flash("Transação removida.", "success")
    return redirect(url_for("admin_transactions.manage"))
