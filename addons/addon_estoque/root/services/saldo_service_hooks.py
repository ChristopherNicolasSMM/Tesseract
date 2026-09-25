"""
addons/addon_estoque/root/services/saldo_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (achado do Christopher): `valor_total_estoque`/
`estoque_minimo` nulos mostravam em branco na tela — decisão de
sessão: tratar como 0 em vez de deixar nulo, resolvido aqui (na
gravação), não espalhado em cada template que exibe Saldo.
"""

from math import isfinite

from core.db import db
from addons.addon_estoque.root.model.saldo import Saldo


def pai_apply_fields(obj, data):
    if obj.valor_total_estoque is None:
        obj.valor_total_estoque = 0.0
    if obj.estoque_minimo is None:
        obj.estoque_minimo = 0.0


def _result(success, *, data=None, error=None, code=200):
    from addons.addon_estoque.root.services.saldo_service import ServiceResult
    return ServiceResult(success=success, data=data, error=error, code=code)


def _immutable(*_args):
    return _result(False, error="O saldo é criado e atualizado pelas movimentações de estoque.", code=409)


create_override = _immutable
trash_override = _immutable
restore_override = _immutable
delete_permanent_override = _immutable


def update_override(id, data):
    """Somente os limites são editáveis sem lançar uma movimentação."""
    saldo = db.session.get(Saldo, id)
    if saldo is None or saldo.is_deleted:
        return _result(False, error="Saldo não encontrado.", code=404)
    if set(data) - {"estoque_minimo", "estoque_maximo"}:
        return _result(False, error="Quantidade e custos do saldo não são editáveis; registre uma movimentação.", code=422)
    try:
        valores = {}
        for key, raw in data.items():
            if raw is None or raw == "":
                valores[key] = None
            else:
                value = float(raw)
                if not isfinite(value) or value < 0:
                    raise ValueError
                valores[key] = value
        minimo = valores.get("estoque_minimo", saldo.estoque_minimo)
        maximo = valores.get("estoque_maximo", saldo.estoque_maximo)
        if minimo is not None and maximo is not None and minimo > maximo:
            return _result(False, error="O estoque mínimo não pode superar o máximo.", code=422)
    except (TypeError, ValueError):
        return _result(False, error="Os limites do estoque devem ser números não negativos e finitos.", code=422)
    for key, value in valores.items():
        setattr(saldo, key, value)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _result(True, data=saldo)
