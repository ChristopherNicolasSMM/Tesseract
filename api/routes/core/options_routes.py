"""
api/routes/core/options_routes.py

Endpoint genérico de combo de busca (skill 11 —
docs/skills/11-referencia-fraca-e-display-field.md), usado pelos
campos com @weak_ref(..., options=...) nas telas de detalhe geradas
pelo CrudGen. Mesmo formato de resposta do PyTeca original
(compatível com Select2, sem exigir nenhum parsing novo no frontend):

    GET /api/options/<plural>?search=xxx&page=1
    -> {"results": [{"id": ..., "text": ...}], "pagination": {"more": bool}}

Diferenças em relação ao PyTeca (Tesseract tem RBAC, o PyTeca não
tinha essa preocupação neste endpoint):
- Exige @login_required.
- Escopo restrito por design: só modelos com @display_field são
  elegíveis (nunca todo `db.Model.__subclasses__()` livre) — evita
  expor tabela sensível (ex.: tesseract_user) sem querer. Tabela fora
  da whitelist devolve 400.

`plural` é o mesmo valor de @plural do model alvo (não o nome real da
tabela) — já é a chave estável usada em toda a URL/rota gerada pelo
CrudGen, então reaproveitar aqui evita introduzir uma segunda
convenção de identificador só para isto.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.db import db
from annotations import get_model_metadata

options_bp = Blueprint("options", __name__, url_prefix="/api/options")

_PER_PAGE = 20


def _find_display_model(plural: str):
    """
    Varre db.Model.__subclasses__() (mesma técnica do PyTeca original)
    procurando um model cujo @plural bata com o pedido E que tenha
    @display_field declarado explicitamente — sem as duas condições,
    não é uma fonte de opções válida (whitelist implícita).
    """
    for model_cls in db.Model.__subclasses__():
        if not hasattr(model_cls, "__tablename__"):
            continue
        if not hasattr(model_cls, "_display_field"):
            continue
        meta = get_model_metadata(model_cls)
        if meta["plural"] == plural:
            return model_cls, meta
    return None, None


@options_bp.route("/<string:plural>")
@login_required
def get_options(plural: str):
    model_cls, meta = _find_display_model(plural)
    if not model_cls:
        return jsonify({"error": f"'{plural}' não é uma fonte de opções válida."}), 400

    display_field = meta["display_field"]
    search = (request.args.get("search") or "").strip()
    page = request.args.get("page", 1, type=int)

    # Extensão skill 11 §6 (achado real — Dashboard de Brassagem):
    # por padrão o combo devolve o `id` (PK) do alvo, mas o campo que
    # referencia pode guardar outra coluna de negócio (ex.:
    # DashboardWidget.device_function_name guarda DeviceFunction.name,
    # não DeviceFunction.id — skill 02, referência fraca cross-Addon
    # sempre por nome, nunca id interno). `value_field` só é aceito se
    # for uma coluna REAL do model alvo — nunca um atributo arbitrário.
    value_field = request.args.get("value_field") or "id"
    valid_columns = {c.name for c in model_cls.__table__.columns}
    if value_field not in valid_columns:
        value_field = "id"

    query = model_cls.query
    if hasattr(model_cls, "is_deleted"):
        query = query.filter_by(is_deleted=False)

    display_column = getattr(model_cls, display_field, None)
    if search and display_column is not None:
        query = query.filter(display_column.ilike(f"%{search}%"))
    if display_column is not None:
        query = query.order_by(display_column)

    pagination = query.paginate(page=page, per_page=_PER_PAGE, error_out=False)
    results = [
        {
            "id": getattr(obj, value_field, None) if getattr(obj, value_field, None) is not None else obj.id,
            "text": getattr(obj, display_field, None) or f"#{obj.id}",
        }
        for obj in pagination.items
    ]
    return jsonify({"results": results, "pagination": {"more": pagination.has_next}})
