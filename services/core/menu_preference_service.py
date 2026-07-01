"""
services/core/menu_preference_service.py

Resolve o estado de ordem/colapso do menu (skill 07): override do
usuário -> padrão global (system_config) -> ordem alfabética original
(o que já era o comportamento antes desta skill).

Nível de item dentro do grupo não é coberto aqui (skill 07 §0 —
v1 só reordena grupos inteiros).
"""
from __future__ import annotations

from typing import Optional

from core.db import db
from model.core.system_config import SystemConfig
from model.core.user_menu_preference import UserMenuPreference

_KEY_GROUP_ORDER = "core.menu.group_order"
_KEY_DEFAULT_COLLAPSED = "core.menu.default_collapsed_groups"
_KEY_SIDEBAR_COLLAPSED = "core.menu.default_sidebar_collapsed"


# ── Padrão global (admin) ───────────────────────────────────────────────────

def get_global_group_order() -> list[str]:
    return SystemConfig.get(_KEY_GROUP_ORDER, default=[]) or []


def get_global_default_collapsed_groups() -> list[str]:
    return SystemConfig.get(_KEY_DEFAULT_COLLAPSED, default=[]) or []


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


def set_global_defaults(*, group_order: Optional[list[str]] = None,
                         default_collapsed_groups: Optional[list[str]] = None,
                         default_sidebar_collapsed: Optional[bool] = None) -> None:
    if group_order is not None:
        _set_config(_KEY_GROUP_ORDER, group_order, "json")
    if default_collapsed_groups is not None:
        _set_config(_KEY_DEFAULT_COLLAPSED, default_collapsed_groups, "json")
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


def save_user_preference(user_id: int, *, group_order: Optional[list[str]] = None,
                          collapsed_groups: Optional[list[str]] = None,
                          sidebar_collapsed: Optional[bool] = None) -> UserMenuPreference:
    pref = _get_or_create_preference(user_id)
    if group_order is not None:
        pref.group_order_json = group_order
    if collapsed_groups is not None:
        pref.collapsed_groups_json = collapsed_groups
    if sidebar_collapsed is not None:
        pref.sidebar_collapsed = sidebar_collapsed
    db.session.commit()
    return pref


# ── Resolução final (usado pelo context_processor / pages.py) ──────────────

def resolve_menu_state(user_id: Optional[int], available_groups: list[str]) -> dict:
    """
    Prioridade: override do usuário -> padrão global -> ordem original
    (a lista de grupos como veio, tipicamente alfabética via ORDER BY
    já existente em pages.py).
    """
    pref = None
    if user_id is not None:
        pref = UserMenuPreference.query.filter_by(user_id=user_id).first()

    group_order = (
        (pref.group_order_json if pref and pref.group_order_json else None)
        or get_global_group_order()
        or []
    )
    collapsed_groups = set(
        (pref.collapsed_groups_json if pref and pref.collapsed_groups_json is not None else None)
        or get_global_default_collapsed_groups()
        or []
    )
    sidebar_collapsed = (
        pref.sidebar_collapsed if pref and pref.sidebar_collapsed is not None
        else get_global_default_sidebar_collapsed()
    )

    def sort_key(group_name: str):
        try:
            return (0, group_order.index(group_name))
        except ValueError:
            return (1, available_groups.index(group_name))

    ordered_groups = sorted(available_groups, key=sort_key)

    return {
        "ordered_groups": ordered_groups,
        "collapsed_groups": collapsed_groups,
        "sidebar_collapsed": sidebar_collapsed,
    }
