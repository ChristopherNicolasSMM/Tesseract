"""
services/core/menu_preference_service.py

Resolve o estado de ordem/colapso do menu em ÁRVORE (skill 10): override
do usuário -> padrão global (system_config) -> ordem original
(order_index já persistido no banco pelo sync, skill 10 seção 4).

Schema mudou de "lista de grupos" (skill 07 original) pra:
- order_overrides: dict {parent_code|"__root__": [code_filho, ...]}
  — ordenação é por pai, não uma lista global de um nível só.
- collapsed_nodes: lista de códigos, qualquer nível da árvore.
"""
from __future__ import annotations

from typing import Optional

from core.db import db
from model.core.system_config import SystemConfig
from model.core.user_menu_preference import UserMenuPreference

_KEY_ORDER_OVERRIDES = "core.menu.order_overrides"
_KEY_COLLAPSED_NODES = "core.menu.collapsed_nodes"
_KEY_SIDEBAR_COLLAPSED = "core.menu.default_sidebar_collapsed"

ROOT_KEY = "__root__"  # chave de order_overrides pro nível raiz (parent_id IS NULL)


def list_available_groups() -> list[str]:
    """Mantido por compatibilidade — ver list_full_transaction_tree() (skill 10)."""
    return [node["code"] for node in list_full_transaction_tree()]


def list_full_transaction_tree() -> list[dict]:
    """
    Árvore completa (sem filtro de permissão) — usada pelas telas de
    edição de preferência (admin e pessoal, skill 10), que precisam
    mostrar TODO nó pra poder reordenar/colapsar, independente de quem
    está logado. Não afeta o que a sidebar de fato mostra — isso
    continua filtrado por permissão em controller/core/pages.py.

    TX_GROUP_CORE nunca aparece aqui — mesmo comportamento que já
    existia antes da skill 10 (grupo "Core" nunca editável/visível).
    """
    from model.core.transaction import Transaction

    all_tx = (
        Transaction.query.filter_by(is_active=True)
        .order_by(Transaction.order_index, Transaction.label)
        .all()
    )
    children_by_parent: dict = {}
    for tx in all_tx:
        children_by_parent.setdefault(tx.parent_id, []).append(tx)

    def build(parent_id):
        nodes = []
        for tx in children_by_parent.get(parent_id, []):
            if tx.code == "TX_GROUP_CORE":
                continue
            nodes.append({
                "code": tx.code,
                "label": tx.label,
                "is_folder": tx.route is None,
                "children": build(tx.id),
            })
        return nodes

    return build(None)


# ── Padrão global (admin) ───────────────────────────────────────────────────

def get_global_order_overrides() -> dict:
    return SystemConfig.get(_KEY_ORDER_OVERRIDES, default={}) or {}


def get_global_collapsed_nodes() -> list[str]:
    return SystemConfig.get(_KEY_COLLAPSED_NODES, default=[]) or []


def get_global_default_sidebar_collapsed() -> bool:
    return bool(SystemConfig.get(_KEY_SIDEBAR_COLLAPSED, default=False))


def _set_config(key: str, value, value_type: str) -> None:
    import json

    row = SystemConfig.query.filter_by(key=key).first()
    serialized = json.dumps(value, ensure_ascii=False) if value_type == "json" else str(value)
    if row is None:
        row = SystemConfig(key=key, value=serialized, value_type=value_type)
        db.session.add(row)
    else:
        row.value = serialized
        row.value_type = value_type


def set_global_defaults(*, order_overrides: Optional[dict] = None,
                         collapsed_nodes: Optional[list[str]] = None,
                         default_sidebar_collapsed: Optional[bool] = None) -> None:
    if order_overrides is not None:
        _set_config(_KEY_ORDER_OVERRIDES, order_overrides, "json")
    if collapsed_nodes is not None:
        _set_config(_KEY_COLLAPSED_NODES, collapsed_nodes, "json")
    if default_sidebar_collapsed is not None:
        _set_config(_KEY_SIDEBAR_COLLAPSED, default_sidebar_collapsed, "bool")
    db.session.commit()


# ── Override por usuário ─────────────────────────────────────────────────

def _get_or_create_preference(user_id: int) -> UserMenuPreference:
    pref = UserMenuPreference.query.filter_by(user_id=user_id).first()
    if pref is None:
        pref = UserMenuPreference(user_id=user_id)
        db.session.add(pref)
        db.session.commit()
    return pref


def save_user_preference(user_id: int, *, order_overrides: Optional[dict] = None,
                          collapsed_nodes: Optional[list[str]] = None,
                          sidebar_collapsed: Optional[bool] = None) -> UserMenuPreference:
    pref = _get_or_create_preference(user_id)
    if order_overrides is not None:
        pref.order_overrides_json = order_overrides
    if collapsed_nodes is not None:
        pref.collapsed_nodes_json = collapsed_nodes
    if sidebar_collapsed is not None:
        pref.sidebar_collapsed = sidebar_collapsed
    db.session.commit()
    return pref


# ── Resolução final (usado pelo context_processor / pages.py) ──────────────

def resolve_menu_state(user_id: Optional[int]) -> dict:
    """
    Prioridade: override do usuário -> padrão global -> {} (que, na
    prática, significa "usa a ordem natural do banco", já que
    controller/core/pages.py só aplica um override quando ele existe
    de fato pra aquele parent_code).
    """
    pref = None
    if user_id is not None:
        pref = UserMenuPreference.query.filter_by(user_id=user_id).first()

    order_overrides = (
        (pref.order_overrides_json if pref and pref.order_overrides_json else None)
        or get_global_order_overrides()
        or {}
    )
    collapsed_nodes = set(
        (pref.collapsed_nodes_json if pref and pref.collapsed_nodes_json is not None else None)
        or get_global_collapsed_nodes()
        or []
    )
    sidebar_collapsed = (
        pref.sidebar_collapsed if pref and pref.sidebar_collapsed is not None
        else get_global_default_sidebar_collapsed()
    )

    return {
        "order_overrides": order_overrides,
        "collapsed_nodes": collapsed_nodes,
        "sidebar_collapsed": sidebar_collapsed,
    }
