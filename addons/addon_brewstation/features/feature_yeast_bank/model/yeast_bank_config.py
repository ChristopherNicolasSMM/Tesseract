"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_config.py

Configuração de validade padrão por tipo de armazenamento. Sem FK —
é configuração, não dado transacional. Pensado como linha única
(singleton), mas modelado como tabela normal (CrudGen não tem conceito
de singleton ainda) — a aplicação decide usar só o primeiro registro.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, enum_field, required


@label("Configuração do Banco de Levedura")
@plural("yeast_bank_configs")
@required("storage_type", message="Tipo de armazenamento é obrigatório")
@enum_field("storage_type", options=["Agar Inclinado", "Óleo", "Agar Inc. + Óleo" , "Solu. NaCl 0.9%", "Gligerina", "Seca","Lama"])
class YeastBankConfig(db.Model):
    __tablename__ = "bank_config"

    id = db.Column(db.Integer, primary_key=True)

    expiry_master_days = db.Column(db.Integer, nullable=True)
    expiry_work_days = db.Column(db.Integer, nullable=True)
    expiry_plate_days = db.Column(db.Integer, nullable=True)
    expiry_saline_days = db.Column(db.Integer, nullable=True)
    storage_type = db.Column(db.String(40), nullable=False)

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
            "expiry_master_days": self.expiry_master_days,
            "expiry_work_days": self.expiry_work_days,
            "expiry_plate_days": self.expiry_plate_days,
            "expiry_saline_days": self.expiry_saline_days,
            "is_deleted": self.is_deleted,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankConfig id={self.id}>"
