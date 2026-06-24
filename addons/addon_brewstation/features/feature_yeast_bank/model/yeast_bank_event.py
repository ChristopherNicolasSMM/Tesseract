"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_event.py

Histórico operacional simples para rastreabilidade de decisões
(ex.: "item movido pra lixeira", "starter resultou em contaminação").
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Evento do Banco")
@plural("yeast_bank_events")
@required("event_type", message="Tipo do evento é obrigatório")
class YeastBankEvent(db.Model):
    __tablename__ = "bank_event"

    id = db.Column(db.Integer, primary_key=True)

    bank_item_id = db.Column(db.Integer, db.ForeignKey("bank_item.id"), nullable=True)
    bank_item = db.relationship("YeastBankItem", backref=db.backref("events", lazy=True))

    strain_id = db.Column(db.Integer, db.ForeignKey("strain.id"), nullable=True)
    strain = db.relationship("YeastStrain", backref=db.backref("events", lazy=True))

    starter_id = db.Column(db.Integer, db.ForeignKey("starter_log.id"), nullable=True)
    starter = db.relationship("YeastStarterLog", backref=db.backref("events", lazy=True))

    event_type = db.Column(db.String(50), nullable=False)
    status_before = db.Column(db.String(30), nullable=True)
    status_after = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)

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
            "strain_id": self.strain_id,
            "starter_id": self.starter_id,
            "event_type": self.event_type,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "notes": self.notes,
            "metadata_json": self.metadata_json,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankEvent id={self.id} event_type={self.event_type}>"
