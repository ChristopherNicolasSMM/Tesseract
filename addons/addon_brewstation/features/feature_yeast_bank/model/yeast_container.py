"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_container.py

Container — unidade física de armazenamento (caixa, estante, prateleira)
dentro de um Dispositivo (freezer/geladeira/câmara fria). Introduzido na
skill 19 (docs/skills/19-proposta-reestruturacao-yeast-bank-container.md)
para dar um nível intermediário entre Dispositivo e Item do Banco — hoje
um item aponta direto pro dispositivo inteiro, sem noção de "em qual
caixa/estante". Sempre físico (device_id obrigatório) — sem variante
virtual, decisão fechada na skill 19, seção 6.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, enum_field, display_field, weak_ref, field_labels


@label("Container")
@display_field("name")
@plural("yeast_containers")
@required("name", message="Nome do container é obrigatório")
@max_length("name", 120)
@enum_field("container_type", options=["Caixa", "Estante", "Prateleira", "Outro"])
@field_labels({
    "name": "Nome",
    "container_type": "Tipo",
    "device_id": "Dispositivo",
    "description": "Descrição",
})
@weak_ref(
    "device_id",
    resolver=(
        "addons.addon_brewstation.features.feature_yeast_bank.services."
        "yeast_reference_lookup.get_yeast_storage_device"
    ),
    options="yeast_storage_devices",
)
class YeastContainer(db.Model):
    __tablename__ = "container"  # nome curto — CrudGen/ModuleManager aplicam o prefixo

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    container_type = db.Column(db.String(40), nullable=False, default="Caixa")

    device_id = db.Column(db.Integer, db.ForeignKey("storage_device.id"), nullable=False)
    device = db.relationship("YeastStorageDevice", backref=db.backref("containers", lazy=True))

    description = db.Column(db.Text, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "container_type": self.container_type,
            "device_id": self.device_id,
            "device": self.device.to_dict() if self.device else None,
            "description": self.description,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastContainer {self.name}>"
