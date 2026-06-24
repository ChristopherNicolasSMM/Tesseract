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
"""
import logging

from core.db import db

logger = logging.getLogger(__name__)


def sync_transaction(tx_data: dict, *, source_module: str | None = None, is_standard: bool = False) -> None:
    from model.core.transaction import Transaction

    existing = Transaction.query.filter_by(code=tx_data["code"]).first()

    if existing is None:
        tx = Transaction(
            code=tx_data["code"],
            label=tx_data.get("label", tx_data["code"]),
            group=tx_data.get("group", "Plugin"),
            description=tx_data.get("description"),
            icon=tx_data.get("icon", "bi-app"),
            route=tx_data.get("route", "#"),
            route_params=tx_data.get("route_params") or {},
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
        existing.group = tx_data.get("group", existing.group)
        existing.description = tx_data.get("description", existing.description)
        existing.icon = tx_data.get("icon", existing.icon)
        existing.route = tx_data.get("route", existing.route)
        existing.route_params = tx_data.get("route_params", existing.route_params)
        existing.permission_required = tx_data.get("permission_required", existing.permission_required)


def sync_core_transactions() -> None:
    from core.transactions_catalog import CORE_TRANSACTIONS

    for tx_data in CORE_TRANSACTIONS:
        sync_transaction(tx_data, source_module=None, is_standard=True)
    db.session.commit()
