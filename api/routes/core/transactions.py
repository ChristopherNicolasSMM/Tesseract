"""
api/routes/core/transactions.py

Lista de transações disponíveis para o usuário logado — filtrada por
`has_permission()` real (skill 00/RBAC), não por um tier separado
como o `min_profile` do DEVStationFlask original.

Pensado para alimentar um launcher/menu (Fase 7b/7c — Designer ainda
não migrado; por ora é só a API).
"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from model.core.transaction import Transaction

transactions_api_bp = Blueprint("transactions_api", __name__, url_prefix="/api/core/transactions")


@transactions_api_bp.route("/", methods=["GET"])
@login_required
def list_transactions():
    all_tx = Transaction.query.filter_by(is_active=True).order_by(Transaction.group, Transaction.label).all()

    visible = [
        tx for tx in all_tx
        if tx.permission_required is None or current_user.has_permission(tx.permission_required)
    ]

    return jsonify(success=True, transactions=[tx.to_dict() for tx in visible])
