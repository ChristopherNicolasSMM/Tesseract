"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_starter_log.py

Starter/propagação — nasce de um item do banco.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural


@label("Starter")
@plural("yeast_starter_logs")
class YeastStarterLog(db.Model):
    __tablename__ = "starter_log"

    id = db.Column(db.Integer, primary_key=True)

    bank_item_id = db.Column(db.Integer, db.ForeignKey("bank_item.id"), nullable=False)
    bank_item = db.relationship("YeastBankItem", backref=db.backref("starters", lazy=True))

    brew_date = db.Column(db.Date, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    target_volume_l = db.Column(db.Float, nullable=True)
    objective = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(30), default="planned", nullable=False)
    result_viability_percent = db.Column(db.Float, nullable=True)
    contamination_detected = db.Column(db.Boolean, nullable=False, default=False)
    action_on_bank_item = db.Column(db.String(30), nullable=True)

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
            "brew_date": self.brew_date.isoformat() if self.brew_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "target_volume_l": self.target_volume_l,
            "objective": self.objective,
            "notes": self.notes,
            "status": self.status,
            "result_viability_percent": self.result_viability_percent,
            "contamination_detected": bool(self.contamination_detected),
            "action_on_bank_item": self.action_on_bank_item,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastStarterLog id={self.id} bank_item_id={self.bank_item_id}>"
