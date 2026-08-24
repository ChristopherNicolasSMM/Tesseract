"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_cell_count_history.py

Histórico de contagem/viabilidade — redesenhado na skill 21:
bank_item_id passa a ser obrigatório (era opcional), strain_id e
starter_id removidos (decisão do Christopher, 2026-08-24: cepa é
sempre resolvida via bank_item.strain; contagem é sempre do item,
sem distinguir se veio de um starter específico).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, field_labels, weak_ref


@label("Histórico de Contagem")
@plural("yeast_cell_count_histories")
@required("bank_item_id", message="Item do banco é obrigatório")
@field_labels({
    "bank_item_id": "Item do Banco",
    "sample_date": "Data da Amostra",
    "lot_code": "Código do Lote",
    "cells_per_ml": "Células/mL",
    "viability_percent": "Viabilidade Real (%)",
    "viable_cells_per_ml": "Células Viáveis/mL",
    "estimated_viability_percent": "Viabilidade Estimada (%)",
    "contamination_detected": "Contaminação Detectada",
    "notes": "Observações",
})
@weak_ref("bank_item_id",
    resolver=("addons.addon_brewstation.features.feature_yeast_bank.services.yeast_reference_lookup.get_yeast_bank_item"),
    options="yeast_bank_items")
class YeastCellCountHistory(db.Model):
    __tablename__ = "cell_count_history"

    id = db.Column(db.Integer, primary_key=True)

    bank_item_id = db.Column(db.Integer, db.ForeignKey("bank_item.id"), nullable=False)
    bank_item = db.relationship("YeastBankItem", backref=db.backref("count_history", lazy=True))

    sample_date = db.Column(db.Date, nullable=True)
    lot_code = db.Column(db.String(120), nullable=True)

    cells_per_ml = db.Column(db.Float, nullable=True)
    viability_percent = db.Column(db.Float, nullable=True)
    viable_cells_per_ml = db.Column(db.Float, nullable=True)
    estimated_viability_percent = db.Column(db.Float, nullable=True)

    contamination_detected = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)

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
            "bank_item_id": self.bank_item_id,
            "sample_date": self.sample_date.isoformat() if self.sample_date else None,
            "lot_code": self.lot_code,
            "cells_per_ml": self.cells_per_ml,
            "viability_percent": self.viability_percent,
            "viable_cells_per_ml": self.viable_cells_per_ml,
            "estimated_viability_percent": self.estimated_viability_percent,
            "contamination_detected": bool(self.contamination_detected),
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastCellCountHistory id={self.id}>"
