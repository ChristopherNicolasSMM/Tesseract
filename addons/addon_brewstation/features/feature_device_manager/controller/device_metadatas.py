"""
addons/addon_brewstation/features/feature_device_manager/controller/device_metadatas.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via device_metadatas_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.device_metadata_service import DeviceMetadataService
from addons.addon_brewstation.features.feature_device_manager.model.device_metadata import DeviceMetadata

device_metadatas_bp = Blueprint(
    "device_metadatas", __name__, url_prefix="/brewstation/device-metadatas"
)
_service = DeviceMetadataService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in DeviceMetadata.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)


@device_metadatas_bp.route("/", methods=["GET"])
@login_required
@permission_required("device_metadatas.list")
def manage():
    items = _service.list()
    return render_template(
        "device_metadatas/manage.html",
        items=items, label="Dispositivo IoT", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
    )


@device_metadatas_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("device_metadatas.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("device_metadatas.manage"))
    return render_template(
        "device_metadatas/detail.html",
        item=item, label="Dispositivo IoT", fields=_EDITABLE_FIELDS,
    )


@device_metadatas_bp.route("/", methods=["POST"])
@login_required
@permission_required("device_metadatas.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("device_metadatas.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("device_metadatas.detail", id=id))


@device_metadatas_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("device_metadatas.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("device_metadatas.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("device_metadatas.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_metadatas.manage"))
