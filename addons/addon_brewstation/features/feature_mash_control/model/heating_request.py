"""Internal, append-preserving operator requests; never hardware authorizations."""
from datetime import datetime, timezone
from core.db import db
from annotations import label, plural, readonly_fields


@label("Solicitação de aquecimento")
@plural("heating_requests")
@readonly_fields(["vessel_id", "session_id", "source_id", "status", "created_at", "updated_at",
                  "expires_at", "responded_at", "responded_by", "reason", "context_json"])
class HeatingRequest(db.Model):
    __tablename__ = "heating_request"
    id = db.Column(db.Integer, primary_key=True)
    vessel_id = db.Column(db.Integer, db.ForeignKey("plant_vessel.id"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    source_id = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="requested")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    responded_at = db.Column(db.DateTime)
    responded_by = db.Column(db.Integer)  # Core user identity; historical scalar, no addon FK.
    reason = db.Column(db.String(255))
    context_json = db.Column(db.JSON, nullable=False)


# Preserve audit history through legacy CRUD deletion paths too (including SQLite).
from sqlalchemy import event, select
from .brew_plant_vessel import BrewPlantVessel
from .brew_session import BrewSession


def _protect_audit_delete(mapper, connection, target):
    raise ValueError('A auditoria de aquecimento não pode ser excluída permanentemente.')


def _protect_parent_delete(mapper, connection, target):
    column = HeatingRequest.vessel_id if isinstance(target, BrewPlantVessel) else HeatingRequest.session_id
    if connection.execute(select(HeatingRequest.id).where(column == target.id).limit(1)).first():
        raise ValueError('Registro possui auditoria de aquecimento; preserve o histórico.')


event.listen(HeatingRequest, 'before_delete', _protect_audit_delete)
event.listen(BrewPlantVessel, 'before_delete', _protect_parent_delete)
event.listen(BrewSession, 'before_delete', _protect_parent_delete)
