"""
addons/addon_brewstation/features/feature_device_manager/controller/emulated_devices.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via emulated_devices_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.emulated_device_service import EmulatedDeviceService
from addons.addon_brewstation.features.feature_device_manager.model.emulated_device import EmulatedDevice

emulated_devices_bp = Blueprint(
    "emulated_devices", __name__, url_prefix="/brewstation/emulated-devices"
)
_service = EmulatedDeviceService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in EmulatedDevice.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)


@emulated_devices_bp.route("/", methods=["GET"])
@login_required
@permission_required("emulated_devices.list")
def manage():
    items = _service.list()
    return render_template(
        "emulated_devices/manage.html",
        items=items, label="Dispositivo Emulado", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
    )


@emulated_devices_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("emulated_devices.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("emulated_devices.manage"))
    return render_template(
        "emulated_devices/detail.html",
        item=item, label="Dispositivo Emulado", fields=_EDITABLE_FIELDS,
    )


@emulated_devices_bp.route("/", methods=["POST"])
@login_required
@permission_required("emulated_devices.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("emulated_devices.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("emulated_devices.detail", id=id))


@emulated_devices_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("emulated_devices.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("emulated_devices.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("emulated_devices.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("emulated_devices.manage"))
