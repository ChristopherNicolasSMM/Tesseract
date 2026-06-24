"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_cell_count_history.py

Histórico de contagem/viabilidade — pode estar vinculado a cepa, item
do banco e/ou starter (todas as FKs são opcionais, de propósito: o
registro pode ser um cálculo livre, não necessariamente atrelado).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural


@label("Histórico de Contagem")
@plural("yeast_cell_count_histories")
class YeastCellCountHistory(db.Model):
    __tablename__ = "cell_count_history"

    id = db.Column(db.Integer, primary_key=True)

    strain_id = db.Column(db.Integer, db.ForeignKey("strain.id"), nullable=True)
    strain = db.relationship("YeastStrain", backref=db.backref("count_history", lazy=True))

    bank_item_id = db.Column(db.Integer, db.ForeignKey("bank_item.id"), nullable=True)
    bank_item = db.relationship("YeastBankItem", backref=db.backref("count_history", lazy=True))

    starter_id = db.Column(db.Integer, db.ForeignKey("starter_log.id"), nullable=True)
    starter = db.relationship("YeastStarterLog", backref=db.backref("count_history", lazy=True))

    sample_date = db.Column(db.Date, nullable=True)
    lot_code = db.Column(db.String(120), nullable=True)
    calc_method_id = db.Column(db.String(80), nullable=True)

    cells_per_ml = db.Column(db.Float, nullable=True)
    viability_percent = db.Column(db.Float, nullable=True)
    viable_cells_per_ml = db.Column(db.Float, nullable=True)
    estimated_viability_percent = db.Column(db.Float, nullable=True)

    contamination_detected = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    raw_inputs = db.Column(db.Text, nullable=True)

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
            "bank_item_id": self.bank_item_id,
            "starter_id": self.starter_id,
            "sample_date": self.sample_date.isoformat() if self.sample_date else None,
            "lot_code": self.lot_code,
            "calc_method_id": self.calc_method_id,
            "cells_per_ml": self.cells_per_ml,
            "viability_percent": self.viability_percent,
            "viable_cells_per_ml": self.viable_cells_per_ml,
            "estimated_viability_percent": self.estimated_viability_percent,
            "contamination_detected": bool(self.contamination_detected),
            "notes": self.notes,
            "raw_inputs": self.raw_inputs,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastCellCountHistory id={self.id}>"
