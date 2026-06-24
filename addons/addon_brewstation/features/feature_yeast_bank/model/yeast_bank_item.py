"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_item.py

Item físico do banco (slant, placa, salina, etc.). A viabilidade
ESTIMADA pertence ao item, não à cepa — a cepa só fornece os
parâmetros do modelo (ver yeast_strain.py).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Item do Banco")
@plural("yeast_bank_items")
@required("storage_type", message="Tipo de armazenamento é obrigatório")
class YeastBankItem(db.Model):
    __tablename__ = "bank_item"

    id = db.Column(db.Integer, primary_key=True)

    strain_id = db.Column(db.Integer, db.ForeignKey("strain.id"), nullable=False)
    strain = db.relationship("YeastStrain", backref=db.backref("bank_items", lazy=True))

    storage_type = db.Column(db.String(40), nullable=False)
    location = db.Column(db.String(120), nullable=True)
    storage_device_id = db.Column(db.Integer, db.ForeignKey("storage_device.id"), nullable=True)
    storage_device = db.relationship("YeastStorageDevice", backref=db.backref("bank_items", lazy=True))
    storage_slot = db.Column(db.String(120), nullable=True)
    label_text = db.Column(db.String(120), nullable=True)  # "label" é nome reservado pelo @label

    prepared_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(30), default="ok", nullable=False)
    last_checked = db.Column(db.Date, nullable=True)
    viability_notes = db.Column(db.Text, nullable=True)

    estimated_viability_pct = db.Column(db.Float, nullable=True)
    estimated_viability_updated_at = db.Column(db.DateTime, nullable=True)
    last_viability_reference_type = db.Column(db.String(30), nullable=True)
    last_viability_reference_date = db.Column(db.Date, nullable=True)
    last_viability_reference_value = db.Column(db.Float, nullable=True)

    discarded_at = db.Column(db.DateTime, nullable=True)
    discard_reason = db.Column(db.Text, nullable=True)

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
            "strain_id": self.strain_id,
            "strain": self.strain.to_dict() if self.strain else None,
            "storage_type": self.storage_type,
            "location": self.location,
            "storage_device_id": self.storage_device_id,
            "storage_slot": self.storage_slot,
            "label_text": self.label_text,
            "prepared_date": self.prepared_date.isoformat() if self.prepared_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self.status,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "viability_notes": self.viability_notes,
            "estimated_viability_pct": self.estimated_viability_pct,
            "estimated_viability_updated_at": (
                self.estimated_viability_updated_at.isoformat()
                if self.estimated_viability_updated_at else None
            ),
            "last_viability_reference_type": self.last_viability_reference_type,
            "last_viability_reference_date": (
                self.last_viability_reference_date.isoformat()
                if self.last_viability_reference_date else None
            ),
            "last_viability_reference_value": self.last_viability_reference_value,
            "discarded_at": self.discarded_at.isoformat() if self.discarded_at else None,
            "discard_reason": self.discard_reason,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankItem id={self.id} strain_id={self.strain_id}>"
