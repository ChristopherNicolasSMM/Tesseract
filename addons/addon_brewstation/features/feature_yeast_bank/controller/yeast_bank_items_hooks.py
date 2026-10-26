"""Hooks específicos do controller de amostras do Yeast Bank.

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""

from flask import flash, redirect, request, url_for
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_integrity_service import operate


_DUPLICATE_FIELDS = (
    "storage_type", "container_id", "location", "storage_slot", "label_text",
    "prepared_date", "expiry_date",
)


def _duplicate_item(source_id, form):
    source = YeastBankItem.query.filter_by(id=source_id, is_deleted=False).first()
    if source is None:
        return None, "A amostra de origem não foi encontrada ou está na lixeira."
    data = {field: form.get(field, "") for field in _DUPLICATE_FIELDS}
    # Cepa sempre vem da origem. Histórico, status, viabilidade e campos
    # administrativos não entram na cópia; a nova amostra começa ativa.
    data.update(strain_id=source.strain_id, status="active")
    result = operate("item", "create", data=data)
    return (result.data, None) if result.success else (None, result.error)


def register_routes(blueprint):
    """Rotas específicas preservadas fora do controller gerado pelo CrudGen."""
    @blueprint.post("/<int:id>/duplicate")
    @login_required
    @permission_required("yeast_bank_items.create")
    def duplicate(id):
        obj, error = _duplicate_item(id, request.form)
        if error:
            flash(error, "error")
        else:
            flash("Amostra duplicada como novo registro ativo.", "success")
        target = request.form.get("return_to")
        if not target or not target.startswith("/brewstation/yeast-bank-items"):
            target = url_for("yeast_bank_items.manage")
        return redirect(target)
