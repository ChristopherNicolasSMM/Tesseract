"""
addons/addon_brewstation/features/feature_mash_control/model/automation_rule_log.py

Histórico de disparo de uma AutomationRule.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural


@label("Log de Automação")
@plural("automation_rule_logs")
class AutomationRuleLog(db.Model):
    __tablename__ = "rule_log"

    id = db.Column(db.Integer, primary_key=True)

    rule_id = db.Column(db.Integer, db.ForeignKey("rule.id"), nullable=False)
    rule = db.relationship("AutomationRule", backref=db.backref("logs", lazy=True, cascade="all, delete-orphan"))

    triggered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    sensor_value_at_trigger = db.Column(db.Float, nullable=True)
    action_taken = db.Column(db.String(100), nullable=True)
    success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.String(500), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "sensor_value_at_trigger": self.sensor_value_at_trigger,
            "action_taken": self.action_taken,
            "success": self.success,
            "error_message": self.error_message,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<AutomationRuleLog rule_id={self.rule_id} success={self.success}>"
