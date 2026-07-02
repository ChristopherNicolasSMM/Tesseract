"""
core/transactions_sync.py

Sincronização código -> banco de Transaction. "Código lidera, banco
segue" (skill 00/03), mesmo padrão de core/permissions_sync.py:
- Catálogo de Core (core/transactions_catalog.py) é seedado no boot.
- Cada Addon/Feature/Plugin pode contribuir via get_transactions()
  (ModuleBase/FeatureBase) — sincronizado pelo ModuleManager.
- Idempotente: nunca duplica, atualiza metadados (label/rota/ícone)
  se já existir, nunca apaga uma Transaction desativada manualmente
  via is_active (essa flag é da UI, não do sync).

Árvore (skill 10): sync agora é em DUAS passadas — (1) upsert de todo
nó, sem mexer em parent_id ainda; (2) resolve parent_code -> parent_id
por código (estável), pra funcionar independente da ordem de
declaração no catálogo e permitir um Addon apontar parent_code pra um
grupo declarado pelo Core.
"""
import logging

from core.db import db

logger = logging.getLogger(__name__)


def sync_transaction(tx_data: dict, *, source_module: str | None = None, is_standard: bool = False,
                      order_index: int = 0) -> None:
    """
    Passada 1 — upsert sem parent_id (resolvido depois, em
    resolve_transaction_parents, pra não depender de ordem de
    declaração). `route=None` é válido de propósito (skill 10 —
    nó-pasta puro).
    """
    from model.core.transaction import Transaction

    existing = Transaction.query.filter_by(code=tx_data["code"]).first()

    if existing is None:
        tx = Transaction(
            code=tx_data["code"],
            label=tx_data.get("label", tx_data["code"]),
            description=tx_data.get("description"),
            icon=tx_data.get("icon", "bi-app"),
            route=tx_data.get("route"),
            route_params=tx_data.get("route_params") or {},
            order_index=tx_data.get("order_index", order_index),
            permission_required=tx_data.get("permission_required"),
            is_standard=is_standard,
            source_module=source_module,
        )
        db.session.add(tx)
        logger.info("Transação registrada: %s (%s)", tx_data["code"], source_module or "core")
    else:
        # Atualiza metadados descritivos, mas nunca a flag is_active
        # (controlada manualmente via UI, não pelo sync de código).
        existing.label = tx_data.get("label", existing.label)
        existing.description = tx_data.get("description", existing.description)
        existing.icon = tx_data.get("icon", existing.icon)
        existing.route = tx_data.get("route", existing.route)
        existing.route_params = tx_data.get("route_params", existing.route_params)
        existing.order_index = tx_data.get("order_index", order_index)
        existing.permission_required = tx_data.get("permission_required", existing.permission_required)


def resolve_transaction_parents(tx_data_list: list[dict]) -> None:
    """
    Passada 2 (skill 10) — resolve parent_code -> parent_id pra cada
    item da lista que declarar parent_code. Roda depois que TODOS os
    nós já foram upsertados (passada 1), então funciona mesmo se um
    filho aparecer no catálogo antes do próprio pai.
    """
    from model.core.transaction import Transaction

    for tx_data in tx_data_list:
        parent_code = tx_data.get("parent_code")
        if not parent_code:
            continue

        tx = Transaction.query.filter_by(code=tx_data["code"]).first()
        parent = Transaction.query.filter_by(code=parent_code).first()
        if tx is None:
            continue
        if parent is None:
            logger.warning(
                "Transação '%s' declara parent_code='%s', mas esse código "
                "não existe no catálogo — ficando sem pai (raiz).",
                tx_data["code"], parent_code,
            )
            continue
        tx.parent_id = parent.id


def sync_core_transactions() -> None:
    from core.transactions_catalog import CORE_TRANSACTIONS

    for order_index, tx_data in enumerate(CORE_TRANSACTIONS):
        sync_transaction(tx_data, source_module=None, is_standard=True, order_index=order_index)
    db.session.flush()
    resolve_transaction_parents(CORE_TRANSACTIONS)
    db.session.commit()
