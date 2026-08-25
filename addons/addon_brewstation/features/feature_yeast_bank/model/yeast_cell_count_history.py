"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_cell_count_history.py

Histórico de contagem/viabilidade — redesenhado na skill 21:
bank_item_id passa a ser obrigatório (era opcional), strain_id e
starter_id removidos (decisão do Christopher, 2026-08-24: cepa é
sempre resolvida via bank_item.strain; contagem é sempre do item,
sem distinguir se veio de um starter específico).

Skill 22 (2026-08-24): `bank_event_id` novo — rastreia qual Evento
originou esta contagem (preenchido automaticamente pelo
post_create_redirect, nunca escolhido manualmente). Campos brutos de
entrada da câmara de Neubauer (`cells_counted_live`/`_dead`,
`squares_counted`, `dilution_factor`) — um hook calcula
`cells_per_ml`/`viability_percent`/`viable_cells_per_ml`
automaticamente a partir deles quando presentes, ver
`yeast_cell_count_history_service_hooks.py`.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, field_labels, weak_ref, readonly_fields


@label("Histórico de Contagem")
@plural("yeast_cell_count_histories")
@required("bank_item_id", message="Item do banco é obrigatório")
@readonly_fields(["bank_event_id"])
@field_labels({
    "bank_item_id": "Item do Banco",
    "bank_event_id": "Evento de Origem",
    "sample_date": "Data da Amostra",
    "lot_code": "Código do Lote",
    "cells_counted_live": "Células Vivas Contadas",
    "cells_counted_dead": "Células Mortas Contadas",
    "squares_counted": "Quadrados Contados",
    "dilution_factor": "Fator de Diluição",
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

    # Preenchido só pelo fluxo automático de criação (skill 22) —
    # nunca escolhido manualmente (@readonly_fields acima).
    bank_event_id = db.Column(db.Integer, db.ForeignKey("bank_event.id"), nullable=True)

    sample_date = db.Column(db.Date, nullable=True)
    lot_code = db.Column(db.String(120), nullable=True)

    # ── Entrada bruta da câmara de Neubauer (skill 22) — opcional;
    # quando preenchidos, um hook calcula os 3 campos de resultado
    # abaixo automaticamente (só se eles ainda estiverem vazios).
    cells_counted_live = db.Column(db.Integer, nullable=True)
    cells_counted_dead = db.Column(db.Integer, nullable=True)
    squares_counted = db.Column(db.Integer, nullable=True, default=5)
    dilution_factor = db.Column(db.Float, nullable=True, default=1.0)

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
            "bank_event_id": self.bank_event_id,
            "sample_date": self.sample_date.isoformat() if self.sample_date else None,
            "lot_code": self.lot_code,
            "cells_counted_live": self.cells_counted_live,
            "cells_counted_dead": self.cells_counted_dead,
            "squares_counted": self.squares_counted,
            "dilution_factor": self.dilution_factor,
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
