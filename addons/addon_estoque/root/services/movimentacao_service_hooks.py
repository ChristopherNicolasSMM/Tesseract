"""
addons/addon_estoque/root/services/movimentacao_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos
"""

from datetime import date
from math import isfinite

from core.db import db
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.services import estoque_service


def _result(success, *, data=None, error=None, code=200):
    # Import tardio: o CrudGen carrega este hook ao importar o service.
    from addons.addon_estoque.root.services.movimentacao_service import ServiceResult
    return ServiceResult(success=success, data=data, error=error, code=code)


def _number(value, name, *, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{name} é obrigatório.")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser numérico.") from exc
    if not isfinite(number):
        raise ValueError(f"{name} deve ser finito.")
    return number


def _id(value, name, *, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{name} é obrigatório.")
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser um identificador válido.") from exc
    if result <= 0:
        raise ValueError(f"{name} deve ser um identificador válido.")
    return result


def create_override(data):
    """Toda entrada manual usa o mesmo lançamento atômico das integrações."""
    try:
        validade = data.get("data_validade") or None
        if isinstance(validade, str):
            validade = date.fromisoformat(validade)
        if validade is not None and not isinstance(validade, date):
            raise ValueError("Data de validade inválida.")

        usuario_id = None
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                usuario_id = current_user.id
        except RuntimeError:  # Uso do service fora de uma requisição web.
            pass

        resultado = estoque_service.registrar_movimentacao(
            material_id=_id(data.get("material_id"), "Material", required=True),
            tipo_movimentacao=data.get("tipo_movimentacao"),
            quantidade=_number(data.get("quantidade"), "Quantidade", required=True),
            custo_unitario=_number(data.get("custo_unitario"), "Custo unitário"),
            lote_fornecedor=data.get("lote_fornecedor") or None,
            data_validade=validade,
            usuario_id=usuario_id,
            observacoes=data.get("observacoes") or None,
            fornecedor_id=_id(data.get("fornecedor_id"), "Fornecedor"),
        )
        mov = db.session.get(Movimentacao, resultado["movimentacao"]["id"])
        return _result(True, data=mov, code=201)
    except (ValueError, estoque_service.MaterialNaoEncontradoError,
            estoque_service.TipoMovimentacaoInvalidoError) as exc:
        db.session.rollback()
        return _result(False, error=str(exc), code=422)
    except Exception:
        db.session.rollback()
        raise


def _immutable(*_args):
    return _result(False, error="Movimentações já registradas são imutáveis. Registre um novo ajuste para corrigir o saldo.", code=409)


update_override = _immutable
trash_override = _immutable
restore_override = _immutable
delete_permanent_override = _immutable
